"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DetailState } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { TableScroll } from "@/components/ui/table";
import { ApiError, api, type DisplayError, type Session } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { loadSession } from "@/lib/session";

import { factsMet, JudgedFindings, type JudgedScores } from "./eval-results";

type EvalRun = {
  id: string;
  suiteId: string;
  agentId?: string;
  status: string;
  createdAt?: string | null;
  summary?: { cases?: number; passed?: number; passRate?: number | null } | null;
};
type Result = {
  passed: boolean;
  outputText?: string | null;
  runId?: string | null;
  case: { id: string; name?: string | null };
  scores?: JudgedScores;
};
const selectClass =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm";
const text = (value: unknown): value is string =>
  typeof value === "string" && Boolean(value.trim());
const sessionScope = (session: Session) =>
  JSON.stringify([
    session.tenant?.id ?? session.tenant?.slug ?? null,
    session.user?.id ?? session.user?.email ?? null,
  ]);
const accessLost = (error: unknown) =>
  error instanceof ApiError && (error.status === 401 || error.status === 403);
function runValid(value: unknown, agentId?: string): value is EvalRun {
  if (!value || typeof value !== "object") return false;
  const run = value as EvalRun;
  const rate = run.summary?.passRate;
  return (
    text(run.id) &&
    text(run.suiteId) &&
    text(run.status) &&
    (!agentId || run.agentId === agentId) &&
    (run.createdAt == null ||
      (text(run.createdAt) &&
        /(?:Z|[+-]\d{2}:\d{2})$/i.test(run.createdAt) &&
        Number.isFinite(new Date(run.createdAt).getTime()))) &&
    (run.summary == null || (typeof run.summary === "object" && !Array.isArray(run.summary))) &&
    (rate == null || (typeof rate === "number" && Number.isFinite(rate) && rate >= 0 && rate <= 1))
  );
}
function resultValid(value: unknown): value is Result {
  if (!value || typeof value !== "object") return false;
  const result = value as Result;
  return (
    typeof result.passed === "boolean" &&
    Boolean(result.case && text(result.case.id)) &&
    (result.case.name == null || typeof result.case.name === "string") &&
    (result.outputText == null || typeof result.outputText === "string") &&
    (result.runId == null || text(result.runId))
  );
}
function pageRows<T>(
  value: { items?: unknown },
  valid: (row: unknown) => row is T,
  key: (row: T) => string,
  message: string,
): T[] {
  if (!Array.isArray(value?.items) || !value.items.every(valid)) throw new Error(message);
  const rows = value.items as T[];
  if (new Set(rows.map(key)).size !== rows.length) throw new Error(message);
  return rows;
}
function RecordedOutput({ value }: { value: string }) {
  const t = useTranslations("evals");
  const [open, setOpen] = useState(false);
  return (
    <details className="mt-2" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="cursor-pointer">{t("output")}</summary>
      {open ? (
        <TableScroll
          label={t("output")}
          className="mt-2 max-h-64 rounded-lg border border-[var(--border)] p-3 text-xs"
        >
          <pre className="whitespace-pre-wrap break-words">{value}</pre>
        </TableScroll>
      ) : null}
    </details>
  );
}

function RunResults({
  runId,
  agentId,
  suiteNames,
  onAccessLost,
}: {
  runId: string;
  agentId?: string;
  suiteNames: ReadonlyMap<string, string>;
  onAccessLost: (error: DisplayError) => void;
}) {
  const t = useTranslations("evals"),
    locale = useLocale();
  const [run, setRun] = useState<EvalRun | null>(null);
  const [results, setResults] = useState<Result[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [runError, setRunError] = useState<DisplayError>("");
  const [resultsError, setResultsError] = useState<DisplayError>("");
  const [query, setQuery] = useState("");
  const [outcome, setOutcome] = useState("");
  const request = useRef<AbortController | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const owner = useRef<string | null>(null);
  const read = useCallback(async () => {
    if (request.current) return;
    if (timer.current) clearTimeout(timer.current);
    const controller = new AbortController();
    request.current = controller;
    const active = () => request.current === controller && !controller.signal.aborted;
    const options = { signal: controller.signal };
    setLoading(true);
    try {
      const session = await loadSession();
      if (!active()) return;
      const scope = sessionScope(session);
      if (owner.current && owner.current !== scope) {
        setRun(null);
        setResults(null);
        onAccessLost(t("sessionChanged"));
        return;
      }
      owner.current = scope;
      if (!session.permissions?.includes("evals:manage")) {
        setRun(null);
        setResults(null);
        onAccessLost(t("denied"));
        return;
      }
      const [detail, cases] = await Promise.allSettled([
        api<unknown>(`/api/v1/eval-runs/${encodeURIComponent(runId)}`, options).then((value) => {
          if (!runValid(value, agentId) || value.id !== runId) throw new Error(t("runMetadata"));
          return value;
        }),
        api<{ items?: unknown }>(
          `/api/v1/eval-runs/${encodeURIComponent(runId)}/results`,
          options,
        ).then((value) => pageRows(value, resultValid, (row) => row.case.id, t("resultMetadata"))),
      ]);
      if (!active()) return;
      if (
        [detail, cases].some((value) => value.status === "rejected" && accessLost(value.reason))
      ) {
        setRun(null);
        setResults(null);
        const rejected = [detail, cases].find(
          (value) => value.status === "rejected" && accessLost(value.reason),
        );
        onAccessLost(rejected?.status === "rejected" ? rejected.reason : t("denied"));
        return;
      }
      if (detail.status === "fulfilled") {
        setRun(detail.value);
        setRunError("");
        if (cases.status === "fulfilled") {
          setResults(cases.value);
          setResultsError("");
          if (detail.value.status === "queued" || detail.value.status === "running")
            timer.current = setTimeout(() => void read(), 1000);
        } else setResultsError(cases.reason instanceof Error ? cases.reason : t("error"));
      } else {
        // Results belong to this endpoint, but never display them beside an unverified run identity.
        setRunError(detail.reason instanceof Error ? detail.reason : t("error"));
        if (cases.status === "rejected")
          setResultsError(cases.reason instanceof Error ? cases.reason : t("error"));
      }
    } catch (caught) {
      if (!active()) return;
      if (accessLost(caught)) {
        setRun(null);
        setResults(null);
        onAccessLost(caught instanceof Error ? caught : t("denied"));
        return;
      }
      setRunError(caught instanceof Error ? caught : t("error"));
    } finally {
      if (active()) {
        request.current = null;
        setLoading(false);
      }
    }
  }, [agentId, runId, onAccessLost, t]);
  useEffect(() => {
    void read();
    return () => {
      request.current?.abort();
      request.current = null;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [read]);
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const matching = useMemo(
    () =>
      (results ?? []).filter(
        (row) =>
          (!outcome || row.passed === (outcome === "passed")) &&
          (!normalizedQuery ||
            [row.case.id, row.case.name, row.outputText, row.runId].some((value) =>
              value?.toLocaleLowerCase().includes(normalizedQuery),
            )),
      ),
    [results, outcome, normalizedQuery],
  );
  const pagination = usePagedRows(matching, `${runId}::${query}::${outcome}`);
  const search = useRef<HTMLInputElement>(null);
  const ongoing = run?.status === "queued" || run?.status === "running";
  const filtered = Boolean(query || outcome);
  return (
    <div className="mt-4 space-y-4">
      {run ? (
        <p className="break-words text-sm font-medium">
          {suiteNames.get(run.suiteId) || t("suiteReference", { id: run.suiteId })}
        </p>
      ) : null}
      <p className="break-all text-xs text-[var(--muted-foreground)]">
        {t("runReference", { id: runId })}
      </p>
      <div className="flex flex-wrap items-center justify-between gap-3">
        {run ? (
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={statusTone(run.status)}>
              {t.has(`statuses.${run.status}`) ? t(`statuses.${run.status}`) : run.status}
            </Badge>
            {run.summary?.passRate != null ? (
              <span className="text-sm">
                {t("rateSummary", {
                  rate: new Intl.NumberFormat(locale, {
                    style: "percent",
                    maximumFractionDigits: 20,
                  }).format(run.summary.passRate),
                })}
              </span>
            ) : null}
          </div>
        ) : null}
        <Button type="button" variant="outline" disabled={loading} onClick={() => void read()}>
          {t("refresh")}
        </Button>
      </div>
      {ongoing ? (
        <p className="text-sm text-[var(--muted-foreground)]">{t("runOngoing")}</p>
      ) : run && run.status !== "completed" ? (
        <p className="text-sm text-[var(--muted-foreground)]">
          {t("runEnded", {
            status: t.has(`statuses.${run.status}`) ? t(`statuses.${run.status}`) : run.status,
          })}
        </p>
      ) : null}
      {(runError || resultsError) && run ? (
        <p className="text-sm text-[var(--muted-foreground)]">{t("resultsRetained")}</p>
      ) : null}
      {loading && run ? (
        <p role="status" className="text-sm text-[var(--muted-foreground)]">
          {t("refreshing")}
        </p>
      ) : null}
      <DetailState
        loading={loading && !run}
        error={runError || resultsError}
        onRetry={() => void read()}
      />
      {run && results !== null ? (
        <>
          <fieldset
            aria-label={t("resultFilters")}
            className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem]"
          >
            <Input
              ref={search}
              type="search"
              aria-label={t("resultSearch")}
              placeholder={t("resultSearch")}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <label className="space-y-1 text-sm">
              <span className="sr-only">{t("outcome")}</span>
              <select
                aria-label={t("outcome")}
                className={selectClass}
                value={outcome}
                onChange={(event) => setOutcome(event.target.value)}
              >
                <option value="">{t("allOutcomes")}</option>
                <option value="passed">{t("passed")}</option>
                <option value="failed">{t("failed")}</option>
              </select>
            </label>
          </fieldset>
          {filtered ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setQuery("");
                setOutcome("");
                search.current?.focus();
              }}
            >
              {t("clearFilters")}
            </Button>
          ) : null}
          {matching.length === 0 ? (
            <EmptyState compact title={t(results.length ? "noResultMatches" : "noCaseResults")} />
          ) : null}
          <ul className="space-y-3">
            {pagination.rows.map((row) => (
              <li
                key={row.case.id}
                className="rounded-lg border border-[var(--border)] p-3 text-sm"
              >
                <p className="break-words font-medium">
                  {row.case.name || row.case.id} · {row.passed ? t("passed") : t("failed")}
                  {factsMet(row.scores) ? ` · ${t("factsMet", factsMet(row.scores) ?? {})}` : ""}
                </p>
                <JudgedFindings scores={row.scores} />
                {row.outputText ? <RecordedOutput value={row.outputText} /> : null}
                {row.runId ? (
                  <Link
                    className="mt-2 inline-block underline"
                    href={`/runs/${encodeURIComponent(row.runId)}`}
                  >
                    {t("openCaseRun")}
                  </Link>
                ) : null}
              </li>
            ))}
          </ul>
          {results.length > 0 ? <ListPagination {...pagination} label={t("results")} /> : null}
        </>
      ) : null}
    </div>
  );
}

export function EvalRunHistory(props: {
  agentId?: string;
  selectedId: string;
  onSelect: (id: string) => void;
  suiteNames: ReadonlyMap<string, string>;
}) {
  return <RunHistory key={props.agentId ?? "workspace"} {...props} />;
}
function RunHistory({
  agentId,
  selectedId,
  onSelect,
  suiteNames,
}: {
  agentId?: string;
  selectedId: string;
  onSelect: (id: string) => void;
  suiteNames: ReadonlyMap<string, string>;
}) {
  const t = useTranslations("evals"),
    locale = useLocale();
  const [rows, setRows] = useState<EvalRun[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [allowed, setAllowed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<DisplayError>("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const opener = useRef<HTMLButtonElement>(null),
    search = useRef<HTMLInputElement>(null);
  const request = useRef<AbortController | null>(null);
  const owner = useRef<string | null>(null);
  const select = useRef(onSelect);
  select.current = onSelect;
  const clearProtected = useCallback((message: DisplayError) => {
    request.current?.abort();
    request.current = null;
    setLoading(false);
    setRows([]);
    setLoaded(false);
    setAllowed(false);
    setError(message);
    select.current("");
  }, []);
  const load = useCallback(async () => {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    const active = () => request.current === controller && !controller.signal.aborted;
    setLoading(true);
    try {
      const session = await loadSession();
      if (!active()) return;
      const scope = sessionScope(session);
      if (owner.current && owner.current !== scope) {
        setRows([]);
        setLoaded(false);
        select.current("");
      }
      owner.current = scope;
      const permitted = session.permissions?.includes("evals:manage") ?? false;
      setAllowed(permitted);
      if (!permitted) {
        setRows([]);
        setLoaded(false);
        setError(t("denied"));
        return;
      }
      const params = new URLSearchParams();
      if (agentId) params.set("agent_id", agentId);
      const page = await api<{ items?: unknown }>(`/api/v1/eval-runs?${params}`, {
        signal: controller.signal,
      });
      if (!active()) return;
      setRows(
        pageRows(
          page,
          (row): row is EvalRun => runValid(row, agentId),
          (row) => row.id,
          t("runMetadata"),
        ),
      );
      setLoaded(true);
      setError("");
    } catch (caught) {
      if (!active()) return;
      if (accessLost(caught)) {
        setRows([]);
        setLoaded(false);
        setAllowed(false);
      }
      setError(caught instanceof Error ? caught : t("error"));
    } finally {
      if (active()) {
        request.current = null;
        setLoading(false);
      }
    }
  }, [agentId, t]);
  useEffect(() => {
    void load();
    return () => {
      request.current?.abort();
      request.current = null;
    };
  }, [load]);
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const filtered = useMemo(
    () =>
      rows.filter(
        (row) =>
          (!status || row.status === status) &&
          (!normalizedQuery ||
            [row.id, row.suiteId, suiteNames.get(row.suiteId)].some((value) =>
              value?.toLocaleLowerCase().includes(normalizedQuery),
            )),
      ),
    [rows, normalizedQuery, status, suiteNames],
  );
  const statuses = useMemo(() => [...new Set(rows.map((row) => row.status))].sort(), [rows]);
  const options = status && !statuses.includes(status) ? [...statuses, status].sort() : statuses;
  const pagination = usePagedRows(filtered, `${query}::${status}`);
  function close() {
    onSelect("");
  }
  return (
    <section aria-label={t("runHistory")}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-[var(--muted-foreground)]">{t("runHistoryHelp")}</p>
        <Button type="button" variant="outline" disabled={loading} onClick={() => void load()}>
          {t("refresh")}
        </Button>
      </div>
      <fieldset
        aria-label={t("runFilters")}
        className="mb-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem]"
      >
        <Input
          ref={search}
          type="search"
          aria-label={t("runSearch")}
          placeholder={t("runSearch")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <label className="space-y-1 text-sm">
          <span className="sr-only">{t("status")}</span>
          <select
            aria-label={t("status")}
            className={selectClass}
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">{t("allStatuses")}</option>
            {options.map((value) => (
              <option key={value} value={value}>
                {t.has(`statuses.${value}`) ? t(`statuses.${value}`) : value}
              </option>
            ))}
          </select>
        </label>
      </fieldset>
      {query || status ? (
        <Button
          className="mb-4"
          type="button"
          variant="outline"
          onClick={() => {
            setQuery("");
            setStatus("");
            search.current?.focus();
          }}
        >
          {t("clearFilters")}
        </Button>
      ) : null}
      {loaded && (loading || error) ? (
        <p role="status" className="mb-3 text-sm text-[var(--muted-foreground)]">
          {t(loading ? "refreshing" : "historyRetained")}
        </p>
      ) : null}
      <DetailState loading={loading && !loaded} error={error} onRetry={() => void load()} />
      {loaded && filtered.length === 0 ? (
        <EmptyState compact title={t(rows.length ? "noRunMatches" : "noRuns")} />
      ) : null}
      <ul className="row-list">
        {loaded
          ? pagination.rows.map((row) => (
              <li key={row.id} className="space-y-2 p-4 text-sm">
                <p className="break-words font-medium">
                  {suiteNames.get(row.suiteId) || t("suiteReference", { id: row.suiteId })}
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={statusTone(row.status)}>
                    {t.has(`statuses.${row.status}`) ? t(`statuses.${row.status}`) : row.status}
                  </Badge>
                  {row.createdAt ? (
                    <time dateTime={row.createdAt}>{formatDateTime(row.createdAt, locale)}</time>
                  ) : null}
                </div>
                <p title={row.id} className="break-all text-xs text-[var(--muted-foreground)]">
                  {t("reference", { id: row.id.slice(-8) })}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  aria-label={t("viewRun", { id: row.id })}
                  onClick={(event) => {
                    opener.current = event.currentTarget;
                    onSelect(row.id);
                  }}
                >
                  {t("viewResults")}
                </Button>
              </li>
            ))
          : null}
      </ul>
      {loaded && rows.length > 0 ? (
        <ListPagination {...pagination} label={t("runHistory")} />
      ) : null}
      <Dialog
        open={Boolean(selectedId) && allowed}
        onOpenChange={(open) => {
          if (!open) close();
        }}
      >
        <DialogContent
          title={t("results")}
          footer={
            <div className="flex justify-end">
              <Button type="button" variant="outline" onClick={close}>
                {t("close")}
              </Button>
            </div>
          }
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (opener.current?.isConnected) opener.current.focus();
            else search.current?.focus();
          }}
        >
          <RunResults
            key={`${agentId ?? "workspace"}:${selectedId}`}
            runId={selectedId}
            agentId={agentId}
            suiteNames={suiteNames}
            onAccessLost={clearProtected}
          />
        </DialogContent>
      </Dialog>
    </section>
  );
}
