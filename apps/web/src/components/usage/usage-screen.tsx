"use client";

import { RefreshCw } from "lucide-react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, DetailState, ErrorMessage } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableScroll,
} from "@/components/ui/table";
import { ApiError, api, type DisplayError, readApiError } from "@/lib/api";
import { formatCost, formatCount } from "@/lib/format";
import { loadSession } from "@/lib/session";

const UsageChart = dynamic(
  () => import("@/components/usage/usage-chart").then((mod) => mod.UsageChart),
  { ssr: false, loading: () => <Skeleton className="h-56 w-full" /> },
);
type Row = { keys: Record<string, string>; quantity: number; costMicros: number };
type Summary = { currency?: string; rows: Row[]; totals: { quantity: number; costMicros: number } };
type Overview = { runs: { total: number }; feedback: { up: number; down: number } };
type Filters = { from: string; to: string; group: string };
type Snapshot = { data: Summary; filters: Filters };
const groups = ["day", "agent", "user", "team", "model", "metric", "tenant"];
const defaults: Filters = { from: "", to: "", group: "day" };
const field =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)]";
const same = (a: Filters, b: Filters) => a.from === b.from && a.to === b.to && a.group === b.group;
function dateValid(value: string) {
  if (!value) return true;
  const date = new Date(`${value}T00:00:00Z`);
  return (
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(date.getTime()) &&
    date.toISOString().slice(0, 10) === value
  );
}
function summaryValid(data: Summary, group: string): boolean {
  return Boolean(
    data &&
      (data.currency === undefined || typeof data.currency === "string") &&
      Number.isFinite(data.totals?.quantity) &&
      Number.isFinite(data.totals?.costMicros) &&
      Array.isArray(data.rows) &&
      data.rows.every(
        (row) =>
          row?.keys &&
          typeof row.keys === "object" &&
          !Array.isArray(row.keys) &&
          typeof row.keys[group] === "string" &&
          Object.values(row.keys).every((value) => typeof value === "string") &&
          Number.isFinite(row.quantity) &&
          Number.isFinite(row.costMicros),
      ),
  );
}

export function UsageScreen() {
  const t = useTranslations("usage");
  const [draft, setDraft] = useState<Filters>(defaults);
  const [filters, setFilters] = useState<Filters>(defaults);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<DisplayError>("");
  const [formError, setFormError] = useState("");
  const [query, setQuery] = useState("");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<DisplayError>("");
  const [exportNotice, setExportNotice] = useState("");
  const readRequest = useRef<AbortController | null>(null);
  const exportRequest = useRef<AbortController | null>(null);
  const downloadUrl = useRef<string | null>(null);
  const downloadTimer = useRef<number | undefined>(undefined);
  const exportFeedback = useRef<HTMLDivElement>(null);
  const deny = useCallback(() => {
    setAllowed(false);
    setSnapshot(null);
  }, []);
  const load = useCallback(async () => {
    if (readRequest.current || exportRequest.current) return;
    const request = new AbortController();
    readRequest.current = request;
    setLoading(true);
    setError("");
    try {
      const session = await loadSession();
      if (request.signal.aborted) return;
      const canRead = (session.permissions ?? []).includes("usage:read");
      setAllowed(canRead);
      if (!canRead) {
        setSnapshot(null);
        return;
      }
      const params = new URLSearchParams({ group_by: filters.group });
      if (filters.from) params.set("from", filters.from);
      if (filters.to) params.set("to", filters.to);
      const data = await api<Summary>(`/api/v1/usage/summary?${params}`, {
        signal: request.signal,
      });
      if (request.signal.aborted) return;
      if (!summaryValid(data, filters.group)) throw new Error(t("metadataError"));
      setSnapshot({ data, filters });
    } catch (caught) {
      if (!request.signal.aborted) {
        setError(caught instanceof Error ? caught : t("error"));
        if (caught instanceof ApiError && [401, 403].includes(caught.status)) deny();
      }
    } finally {
      if (readRequest.current === request) {
        readRequest.current = null;
        setLoading(false);
      }
    }
  }, [filters, t, deny]);
  useEffect(() => {
    void load();
    return () => {
      readRequest.current?.abort();
      readRequest.current = null;
    };
  }, [load]);
  useEffect(
    () => () => {
      exportRequest.current?.abort();
      exportRequest.current = null;
      window.clearTimeout(downloadTimer.current);
      if (downloadUrl.current) URL.revokeObjectURL(downloadUrl.current);
    },
    [],
  );
  useEffect(() => {
    if (exportError) exportFeedback.current?.focus();
  }, [exportError]);

  function apply(event: FormEvent) {
    event.preventDefault();
    if (exportRequest.current) return;
    if (
      !dateValid(draft.from) ||
      !dateValid(draft.to) ||
      (draft.from && draft.to && draft.from > draft.to) ||
      !groups.includes(draft.group)
    ) {
      setFormError(t("invalidRange"));
      return;
    }
    setFormError("");
    setExportNotice("");
    setExportError("");
    if (same(draft, filters)) void load();
    else setFilters({ ...draft });
  }
  async function download() {
    if (
      exportRequest.current ||
      loading ||
      error ||
      !allowed ||
      !snapshot ||
      !same(snapshot.filters, filters)
    )
      return;
    const request = new AbortController();
    exportRequest.current = request;
    setExporting(true);
    setExportError("");
    setExportNotice("");
    const selected = snapshot.filters;
    try {
      const params = new URLSearchParams({ group_by: selected.group });
      if (selected.from) params.set("from", selected.from);
      if (selected.to) params.set("to", selected.to);
      const response = await fetch(`/api/v1/usage/export?${params}`, {
        credentials: "include",
        signal: request.signal,
      });
      if (!response.ok) throw await readApiError(response);
      const mime = response.headers.get("content-type")?.split(";")[0]?.trim().toLowerCase();
      if (mime !== "text/csv" && mime !== "application/csv")
        throw new Error(t("exportFormatError"));
      const blob = await response.blob();
      if (request.signal.aborted) return;
      window.clearTimeout(downloadTimer.current);
      if (downloadUrl.current) URL.revokeObjectURL(downloadUrl.current);
      const url = URL.createObjectURL(blob);
      downloadUrl.current = url;
      const link = document.createElement("a");
      link.href = url;
      link.download = "usage.csv";
      document.body.append(link);
      link.click();
      link.remove();
      downloadTimer.current = window.setTimeout(() => {
        if (downloadUrl.current === url) {
          URL.revokeObjectURL(url);
          downloadUrl.current = null;
        }
      }, 1000);
      setExportNotice(t("exportStarted"));
    } catch (caught) {
      if (!request.signal.aborted) {
        setExportError(caught instanceof Error ? caught : t("exportFailed"));
        if (caught instanceof ApiError && [401, 403].includes(caught.status)) deny();
      }
    } finally {
      if (exportRequest.current === request) {
        exportRequest.current = null;
        setExporting(false);
      }
    }
  }

  const rows = useMemo(
    () =>
      (snapshot?.data.rows ?? []).map((row, index) => ({
        ...row,
        index,
        label: Object.values(row.keys).filter(Boolean).join(" · ") || t("ungrouped"),
      })),
    [snapshot, t],
  );
  const matching = useMemo(
    () =>
      rows.filter((row) =>
        row.label.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
      ),
    [rows, query],
  );
  const pagination = usePagedRows(matching, `${JSON.stringify(snapshot?.filters)}::${query}`);
  const points = useMemo(
    () => pagination.rows.map((row) => ({ label: row.label, quantity: row.quantity })),
    [pagination.rows],
  );
  const unapplied = !same(draft, filters);
  const stale = Boolean(snapshot && !same(snapshot.filters, filters));
  function edit(next: Partial<Filters>) {
    setDraft((current) => ({ ...current, ...next }));
    setFormError("");
  }

  return (
    <AppShell>
      <PageHeader
        title={t("title")}
        body={t("body")}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={loading || exporting}
              aria-label={t("refresh")}
              onClick={() => void load()}
            >
              <RefreshCw size={16} aria-hidden="true" />
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={loading || exporting || !snapshot || !allowed || Boolean(error) || stale}
              onClick={() => void download()}
            >
              {t(exporting ? "exporting" : "export")}
            </Button>
          </div>
        }
      />
      <form
        className="mb-6 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
        onSubmit={apply}
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="text-sm" htmlFor="usage-from">
            {t("from")}
            <Input
              className="mt-1"
              id="usage-from"
              type="date"
              max={draft.to || undefined}
              aria-describedby="usage-filter-help usage-range-error"
              aria-invalid={Boolean(formError)}
              value={draft.from}
              onChange={(event) => edit({ from: event.target.value })}
            />
          </label>
          <label className="text-sm" htmlFor="usage-to">
            {t("to")}
            <Input
              className="mt-1"
              id="usage-to"
              type="date"
              min={draft.from || undefined}
              aria-describedby="usage-filter-help usage-range-error"
              aria-invalid={Boolean(formError)}
              value={draft.to}
              onChange={(event) => edit({ to: event.target.value })}
            />
          </label>
          <div className="text-sm">
            <label htmlFor="usage-group">{t("group")}</label>
            <select
              className={`mt-1 ${field}`}
              id="usage-group"
              value={draft.group}
              onChange={(event) => edit({ group: event.target.value })}
            >
              {groups.map((value) => (
                <option key={value} value={value}>
                  {t(`groups.${value}`)}
                </option>
              ))}
            </select>
          </div>
        </div>
        <p
          id="usage-filter-help"
          className="mt-3 text-xs leading-relaxed text-[var(--muted-foreground)]"
        >
          {t("filterHelp")}
        </p>
        <p
          id="usage-range-error"
          className={formError ? "mt-3 text-sm text-[var(--destructive)]" : "sr-only"}
          role={formError ? "alert" : undefined}
        >
          {formError}
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={exporting || allowed === false}>
            {t("apply")}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={exporting}
            onClick={() => {
              if (exportRequest.current) return;
              setDraft(defaults);
              setFilters(defaults);
              setFormError("");
              setExportNotice("");
              setExportError("");
              if (same(filters, defaults)) void load();
            }}
          >
            {t("reset")}
          </Button>
          {unapplied ? (
            <p className="text-xs text-[var(--muted-foreground)]">{t("unapplied")}</p>
          ) : null}
        </div>
      </form>
      {allowed === false ? <p className="mb-5 text-sm">{t("readDenied")}</p> : null}
      <DetailState
        loading={loading && snapshot === null}
        error={error}
        onRetry={loading ? undefined : () => void load()}
      />
      {loading && snapshot ? (
        <p className="mb-4 text-sm" role="status">
          {t("refreshing")}
        </p>
      ) : null}
      {exportError ? (
        <div
          ref={exportFeedback}
          tabIndex={-1}
          role="alert"
          className="mb-5 space-y-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-sm"
        >
          <p>{t("exportFailed")}</p>
          <ErrorMessage error={exportError} />
        </div>
      ) : null}
      <ActionStatus busy={exporting} busyLabel={t("exporting")} notice={exportNotice} />
      {snapshot && allowed ? (
        <section
          aria-labelledby="usage-report"
          className="mb-6 space-y-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
        >
          <h2 id="usage-report" className="text-base font-semibold">
            {t("reportTitle")}
          </h2>
          <p className="break-words text-sm text-[var(--muted-foreground)]">
            {t("loadedFilters", {
              from: snapshot.filters.from || t("defaultStart"),
              to: snapshot.filters.to || t("defaultEnd"),
              group: t(`groups.${snapshot.filters.group}`),
            })}
          </p>
          {stale ? <p className="text-sm">{t("stale")}</p> : null}
          <Facts
            items={[
              {
                label: t("currency"),
                value: snapshot.data.currency?.trim() || t("currencyUnavailable"),
              },
              { label: t("quantity"), value: formatCount(snapshot.data.totals.quantity) },
              {
                label: snapshot.data.currency?.trim() ? t("cost") : t("costUnset"),
                value: formatCost(snapshot.data.totals.costMicros, snapshot.data.currency),
              },
            ]}
          />
          <p className="text-xs leading-relaxed text-[var(--muted-foreground)]">
            {t("exportScope")}
          </p>
          {rows.length ? (
            <>
              <label className="block text-sm" htmlFor="usage-search">
                {t("search")}
                <Input
                  className="mt-1"
                  id="usage-search"
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              {query ? (
                <Button type="button" variant="outline" onClick={() => setQuery("")}>
                  {t("clearSearch")}
                </Button>
              ) : null}
              {matching.length ? (
                <>
                  <section aria-label={t("chartTitle")} className="min-w-0 overflow-hidden">
                    <p className="mb-2 text-xs text-[var(--muted-foreground)]">{t("chartScope")}</p>
                    <UsageChart points={points} />
                  </section>
                  <TableScroll
                    label={t("rowsTitle")}
                    className="rounded-lg border border-[var(--border)]"
                  >
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead scope="col">{t(`groups.${snapshot.filters.group}`)}</TableHead>
                          <TableHead scope="col">{t("quantity")}</TableHead>
                          <TableHead scope="col">{t("cost")}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {pagination.rows.map((row) => (
                          <TableRow key={row.index}>
                            <TableCell className="max-w-sm break-words">{row.label}</TableCell>
                            <TableCell>{formatCount(row.quantity)}</TableCell>
                            <TableCell>
                              {formatCost(row.costMicros, snapshot.data.currency)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableScroll>
                </>
              ) : (
                <EmptyState title={t("noMatches")} />
              )}
              <ListPagination {...pagination} label={t("rowsTitle")} />
            </>
          ) : (
            <EmptyState title={t("empty")} />
          )}
        </section>
      ) : null}
      {allowed ? <Operations onDenied={deny} /> : null}
    </AppShell>
  );
}

function Operations({ onDenied }: { onDenied: () => void }) {
  const t = useTranslations("usage");
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<DisplayError>("");
  const request = useRef<AbortController | null>(null);
  const load = useCallback(async () => {
    if (request.current) return;
    const active = new AbortController();
    request.current = active;
    setLoading(true);
    setError("");
    try {
      const session = await loadSession();
      if (active.signal.aborted) return;
      if (!(session.permissions ?? []).includes("usage:read")) {
        onDenied();
        return;
      }
      const result = await api<Overview>("/api/v1/observability/overview", {
        signal: active.signal,
      });
      if (active.signal.aborted) return;
      if (
        !result ||
        ![result.runs?.total, result.feedback?.up, result.feedback?.down].every(
          (value) => Number.isFinite(value) && value >= 0,
        )
      )
        throw new Error(t("overviewMetadataError"));
      setData(result);
    } catch (caught) {
      if (!active.signal.aborted) {
        setError(caught instanceof Error ? caught : t("overviewError"));
        if (caught instanceof ApiError && [401, 403].includes(caught.status)) onDenied();
        else if (caught instanceof ApiError && caught.status === 404) setData(null);
      }
    } finally {
      if (request.current === active) {
        request.current = null;
        setLoading(false);
      }
    }
  }, [t, onDenied]);
  useEffect(() => {
    void load();
    return () => {
      request.current?.abort();
      request.current = null;
    };
  }, [load]);
  return (
    <section
      aria-labelledby="usage-overview"
      className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 id="usage-overview" className="text-base font-semibold">
          {t("overview")}
        </h2>
        <Button
          type="button"
          variant="outline"
          disabled={loading}
          aria-label={t("refreshOverview")}
          onClick={() => void load()}
        >
          <RefreshCw size={16} aria-hidden="true" />
        </Button>
      </div>
      <p className="mb-4 text-sm text-[var(--muted-foreground)]">{t("overviewScope")}</p>
      <DetailState
        loading={loading && data === null}
        error={error}
        onRetry={loading ? undefined : () => void load()}
      />
      {data ? (
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            ["runs", data.runs.total],
            ["feedbackUp", data.feedback.up],
            ["feedbackDown", data.feedback.down],
          ].map(([label, value]) => (
            <article className="rounded-lg border border-[var(--border)] p-4" key={String(label)}>
              <p className="text-sm text-[var(--muted-foreground)]">{t(String(label))}</p>
              <p className="mt-2 text-2xl font-medium">{formatCount(Number(value))}</p>
            </article>
          ))}
        </div>
      ) : null}
      {data && !loading && !error && data.runs.total === 0 ? (
        <p className="mt-3 text-sm text-[var(--muted-foreground)]">{t("overviewEmpty")}</p>
      ) : null}
    </section>
  );
}
