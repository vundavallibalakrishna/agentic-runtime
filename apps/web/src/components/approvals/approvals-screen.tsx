"use client";

import { RefreshCw } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ActionStatus, DetailState, ErrorMessage } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import type { DisplayError } from "@/lib/api";
import { api } from "@/lib/api";
import { formatCount, formatDateTime } from "@/lib/format";
import { loadSession } from "@/lib/session";
import { confirmStepUp } from "@/lib/step-up";

type Row = Record<string, unknown>;

const MODE_KEY = "ar-settings-mode";

export function ApprovalsScreen() {
  const t = useTranslations("approvals");
  const confirmation = useTranslations("detail");
  const locale = useLocale();
  const [rows, setRows] = useState<Row[]>([]);
  const [standing, setStanding] = useState<Row[]>([]);
  const [scope, setScope] = useState("to_decide");
  const [risk, setRisk] = useState("");
  const [error, setError] = useState<DisplayError>("");
  const [loading, setLoading] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [comment, setComment] = useState("");
  const [phase, setPhase] = useState<
    "preparing" | "confirming" | "approving" | "rejecting" | "revoking" | "refreshing" | null
  >(null);
  const busy = phase !== null;
  const [target, setTarget] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState<DisplayError>("");
  const [recovery, setRecovery] = useState<DisplayError>("");
  const [recorded, setRecorded] = useState<Set<string>>(() => new Set());
  const readRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const loadedContext = useRef("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [standingQuery, setStandingQuery] = useState("");
  const [standingError, setStandingError] = useState<DisplayError>("");
  const [canReadAll, setCanReadAll] = useState(false);
  const [canManageStanding, setCanManageStanding] = useState(false);
  const pickedIds = useMemo(() => new Set(picked), [picked]);
  const locked = busy || loading || Boolean(error) || Boolean(recovery);
  const hasHash = (row: Row) => typeof row.argsHash === "string" && Boolean(row.argsHash);
  const canDecide = (row: Row) =>
    scope === "to_decide" &&
    row.status === "pending" &&
    hasHash(row) &&
    !recorded.has(String(row.id));
  const filtered = rows.filter(
    (row) =>
      (!status || row.status === status) &&
      [
        row.id,
        row.qualifiedName,
        (row.preview as Row | undefined)?.title,
        (row.preview as Row | undefined)?.summary,
        (row.agent as Row | undefined)?.name,
      ].some((value) =>
        String(value ?? "")
          .toLocaleLowerCase()
          .includes(query.trim().toLocaleLowerCase()),
      ),
  );
  const pagination = usePagedRows(filtered, `${scope}::${risk}::${status}::${query}`);
  const standingFiltered = standing.filter((row) =>
    [row.id, (row.tool as Row | undefined)?.name, (row.routine as Row | undefined)?.name].some(
      (value) =>
        String(value ?? "")
          .toLocaleLowerCase()
          .includes(standingQuery.trim().toLocaleLowerCase()),
    ),
  );
  const standingPagination = usePagedRows(standingFiltered, standingQuery);
  const statuses = [...new Set(rows.map((row) => String(row.status ?? "")).filter(Boolean))].sort();

  useEffect(() => {
    try {
      setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
    } catch {
      setAdvanced(false);
    }
  }, []);

  const load = useCallback(async () => {
    readRequest.current?.abort();
    const request = new AbortController();
    readRequest.current = request;
    const context = `${scope}:${risk}`;
    if (loadedContext.current !== context) {
      setRows([]);
      setPicked([]);
    }
    loadedContext.current = context;
    setLoading(true);
    setError("");
    setStandingError("");
    let standingOkay = true;
    try {
      const params = new URLSearchParams({ scope });
      if (risk) params.set("risk_class", risk);
      const [page, session] = await Promise.all([
        api<{ items: Row[] }>(`/api/v1/approvals?${params.toString()}`, { signal: request.signal }),
        loadSession(),
      ]);
      if (request.signal.aborted) return false;
      if (!Array.isArray(page?.items)) throw new Error(t("queueUnconfirmed"));
      setRows(page.items);
      const pendingIds = new Set(
        page.items.filter((row) => row.status === "pending").map((row) => String(row.id)),
      );
      setPicked((current) => current.filter((id) => pendingIds.has(id)));
      setCanReadAll(session.permissions?.includes("approvals:read_all") ?? false);
      const manageStanding = session.permissions?.includes("approvals:grant_standing") ?? false;
      setCanManageStanding(manageStanding);
      if (advanced && manageStanding) {
        try {
          const grants = await api<{ items: Row[] }>("/api/v1/standing-approvals", {
            signal: request.signal,
          });
          if (request.signal.aborted) return false;
          if (!Array.isArray(grants?.items)) throw new Error(t("queueUnconfirmed"));
          setStanding(grants.items);
        } catch (caught) {
          if (!request.signal.aborted)
            setStandingError(caught instanceof Error ? caught : t("error"));
          standingOkay = false;
        }
      }
      return !request.signal.aborted && standingOkay;
    } catch (caught) {
      if (!request.signal.aborted) setError(caught instanceof Error ? caught : t("error"));
      return false;
    } finally {
      if (readRequest.current === request) {
        readRequest.current = null;
        setLoading(false);
      }
    }
  }, [advanced, risk, scope, t]);

  useEffect(() => {
    void load();
    return () => {
      readRequest.current?.abort();
      actionRequest.current?.abort();
    };
  }, [load]);

  async function refresh() {
    if (actionRequest.current) return;
    if (await load()) {
      setRecovery("");
      setActionError("");
    }
  }
  function chooseMode(next: boolean) {
    if (actionRequest.current || recovery) return;
    setAdvanced(next);
    try {
      window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
    } catch {
      /* Keep the chosen mode for this view. */
    }
  }
  function rowLabel(row: Row) {
    return `${String(row.qualifiedName || t("unavailableTool"))} · ${String(row.id).slice(-8)}`;
  }

  async function decide(selected: Row[], decision: "approve" | "reject") {
    if (actionRequest.current || locked || !selected.length || !selected.every(canDecide)) return;
    const request = new AbortController();
    actionRequest.current = request;
    const submittedComment = comment;
    const receipts: Row[] = [];
    let posted = false;
    let complete = false;
    setActionError("");
    setNotice("");
    setPhase("preparing");
    try {
      for (const row of selected) {
        posted = false;
        setTarget(rowLabel(row));
        setPhase("preparing");
        const id = String(row.id);
        const detail = await api<Row>(`/api/v1/approvals/${encodeURIComponent(id)}`, {
          signal: request.signal,
        });
        if (request.signal.aborted) return;
        if (
          detail?.id !== id ||
          detail.status !== "pending" ||
          detail.canDecide !== true ||
          typeof detail.argsHash !== "string" ||
          !detail.argsHash ||
          detail.argsHash !== row.argsHash
        )
          throw new Error(t("queueEligibility"));
        if (detail.stepUpRequired) {
          setPhase("confirming");
          await confirmStepUp(confirmation("stepUpUnconfirmed"), request.signal);
          if (request.signal.aborted) return;
        }
        setPhase(decision === "approve" ? "approving" : "rejecting");
        posted = true;
        const result = await api<Row>(`/api/v1/approvals/${encodeURIComponent(id)}:decide`, {
          method: "POST",
          signal: request.signal,
          body: JSON.stringify({ decision, argsHash: detail.argsHash, comment: submittedComment }),
        });
        if (request.signal.aborted) return;
        if (
          result?.id !== id ||
          result.argsHash !== detail.argsHash ||
          !(decision === "reject"
            ? result.status === "rejected"
            : result.status === "approved" || result.status === "pending")
        )
          throw new Error(t("decisionUnconfirmed"));
        receipts.push(result);
        setNotice(
          t("queueRecorded", {
            count: formatCount(receipts.length),
            total: formatCount(selected.length),
          }),
        );
      }
      complete = true;
      setComment((current) => (current === submittedComment ? "" : current));
    } catch (caught) {
      if (!request.signal.aborted) {
        const detail = caught instanceof Error ? caught : t("error");
        if (posted || receipts.length) setRecovery(detail);
        else setActionError(detail);
      }
    } finally {
      if (!request.signal.aborted) {
        if (receipts.length) {
          const byId = new Map(receipts.map((row) => [String(row.id), row]));
          setRows((current) =>
            current.map((row) =>
              byId.has(String(row.id)) ? { ...row, ...byId.get(String(row.id)) } : row,
            ),
          );
          setRecorded((current) => new Set([...current, ...byId.keys()]));
          setPicked((current) => current.filter((id) => !byId.has(id)));
        }
        if (complete) {
          setPhase("refreshing");
          if (!(await load()) && !request.signal.aborted) setRecovery(t("queueAcceptedRecovery"));
        }
      }
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setPhase(null);
      }
    }
  }
  async function revoke(row: Row) {
    if (actionRequest.current || locked || standingError || !canManageStanding || row.revokedAt)
      return;
    const request = new AbortController();
    actionRequest.current = request;
    const id = String(row.id);
    setPhase("revoking");
    setTarget(String((row.tool as Row | undefined)?.name || id));
    setActionError("");
    setNotice("");
    try {
      const result = await api<Row>(`/api/v1/standing-approvals/${encodeURIComponent(id)}:revoke`, {
        method: "POST",
        signal: request.signal,
      });
      if (request.signal.aborted) return;
      if (
        result?.id !== id ||
        typeof result.revokedAt !== "string" ||
        !Number.isFinite(Date.parse(result.revokedAt))
      )
        throw new Error(t("revokeUnconfirmed"));
      setStanding((current) =>
        current.map((item) => (item.id === id ? { ...item, ...result } : item)),
      );
      setNotice(t("revokeRecorded"));
      setPhase("refreshing");
      if (!(await load()) && !request.signal.aborted) setRecovery(t("queueAcceptedRecovery"));
    } catch (caught) {
      if (!request.signal.aborted) setRecovery(caught instanceof Error ? caught : t("error"));
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setPhase(null);
      }
    }
  }

  return (
    <AppShell>
      <PageHeader
        title={t("title")}
        body={t("body")}
        actions={
          <>
            <fieldset disabled={busy || Boolean(recovery)}>
              <SettingsMode advanced={advanced} onChange={chooseMode} />
            </fieldset>
            <Button
              aria-label={t("refreshQueue")}
              title={t("refreshQueue")}
              type="button"
              variant="outline"
              className="size-9 p-0"
              disabled={busy || loading}
              onClick={() => void refresh()}
            >
              <RefreshCw size={16} aria-hidden="true" />
            </Button>
          </>
        }
      />

      <ActionStatus
        busy={busy || loading}
        notice={notice}
        busyLabel={
          phase ? t(`queueProgress.${phase}`, { name: target }) : t("queueProgress.refreshing")
        }
      />
      {actionError ? (
        <div role="alert" className="mb-4 break-words text-sm text-[var(--destructive)]">
          <ErrorMessage error={actionError} />
        </div>
      ) : null}
      {recovery ? (
        <div role="alert" className="mb-5 rounded-lg border border-[var(--border)] p-4 text-sm">
          <p>{t("queueRecovery")}</p>
          <p className="mt-2 font-medium">{t("queueTarget", { name: target })}</p>
          <div className="mt-2 break-words text-[var(--muted-foreground)]">
            <ErrorMessage error={recovery} />
          </div>
        </div>
      ) : null}
      <fieldset disabled={busy} className="min-w-0">
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <Button asChild variant="outline">
            <a href="/reviews">{t("reviews")}</a>
          </Button>
          <Button asChild variant="ghost">
            <a href="/admin/policies">{t("policies")}</a>
          </Button>
        </div>
        <fieldset
          disabled={Boolean(recovery)}
          className="mb-5 flex flex-wrap items-center justify-between gap-3"
        >
          <legend className="sr-only">{t("scopeLabel")}</legend>
          <div className="flex gap-1 rounded-lg bg-[var(--muted)] p-1">
            {(
              [
                ["to_decide", t("toDecide")],
                ["requested", t("requested")],
                ["all", t("all")],
              ] as const
            ).map(([value, label]) => (
              <Button
                key={value}
                type="button"
                variant="ghost"
                disabled={value === "all" && !canReadAll}
                aria-pressed={scope === value}
                className={
                  scope === value
                    ? "h-9 bg-[var(--card)] shadow-[var(--shadow-xs)]"
                    : "h-9 text-[var(--muted-foreground)]"
                }
                onClick={() => {
                  setScope(value);
                  setStatus("");
                }}
              >
                {label}
              </Button>
            ))}
          </div>
          <label className="sr-only" htmlFor="risk-filter">
            {t("risk")}
          </label>
          <select
            id="risk-filter"
            className="h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
            value={risk}
            onChange={(event) => {
              setRisk(event.target.value);
              setStatus("");
            }}
          >
            <option value="">{t("allRisks")}</option>
            {(["R0", "R1", "W1", "W2", "W3"] as const).map((value) => (
              <option value={value} key={value}>
                {value} · {t(`riskOptions.${value}`)}
              </option>
            ))}
          </select>
        </fieldset>
        {scope !== "to_decide" ? (
          <p className="mb-5 text-sm text-[var(--muted-foreground)]">
            {t("queueViewOnly", { scope: t("toDecide") })}
          </p>
        ) : null}
        {!loading && (rows.length > 0 || query || status) ? (
          <div className="mb-4 flex flex-wrap gap-3">
            <Input
              aria-label={t("search")}
              placeholder={t("search")}
              type="search"
              className="min-w-0 flex-1"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setPicked([]);
              }}
            />
            <select
              aria-label={t("status")}
              className="h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPicked([]);
              }}
            >
              <option value="">{t("allStatuses")}</option>
              {statuses.map((value) => (
                <option value={value} key={value}>
                  {value}
                </option>
              ))}
            </select>
            {query || status ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setQuery("");
                  setStatus("");
                  setPicked([]);
                }}
              >
                {t("clearLocalFilters")}
              </Button>
            ) : null}
          </div>
        ) : null}
        <DetailState loading={false} error={error} onRetry={() => void refresh()} />
        {loading && rows.length === 0 ? (
          <div aria-busy="true" className="space-y-3">
            <span className="sr-only">{t("loading")}</span>
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : null}
        {!loading && !error && rows.length === 0 ? (
          <EmptyState title={query.trim() || status || risk ? t("noMatches") : t("empty")}>
            <p className="mb-4 max-w-sm text-sm text-[var(--muted-foreground)]">{t("emptyHelp")}</p>
            <Button variant="outline" onClick={() => void refresh()}>
              {t("refresh")}
            </Button>
          </EmptyState>
        ) : null}
        {!loading && rows.length > 0 && filtered.length === 0 ? (
          <EmptyState title={t("noMatches")} />
        ) : null}
        <ul className="row-list">
          {pagination.rows.map((row) => {
            const id = String(row.id);
            const preview = row.preview as { title?: string; summary?: string } | undefined;
            return (
              <li key={id} className="p-4">
                <div className="flex items-start gap-3">
                  {scope === "to_decide" ? (
                    <input
                      aria-label={t("selectRequest", {
                        name: String(row.qualifiedName || t("unavailableTool")),
                        id: id.slice(-8),
                      })}
                      disabled={locked || !canDecide(row)}
                      checked={pickedIds.has(id)}
                      type="checkbox"
                      onChange={(event) =>
                        setPicked((current) =>
                          event.target.checked
                            ? [...current, id]
                            : current.filter((item) => item !== id),
                        )
                      }
                    />
                  ) : null}
                  <div className="min-w-0 flex-1">
                    <a className="font-medium underline" href={`/approvals/${id}`}>
                      {String(row.qualifiedName || t("unavailableTool"))}{" "}
                      <span
                        className="ml-2 font-mono text-xs text-[var(--muted-foreground)]"
                        title={id}
                      >
                        {id.slice(-8)}
                      </span>
                    </a>
                    <p className="text-sm text-[var(--muted-foreground)]">
                      <Badge>{String(row.riskClass ?? "")}</Badge>{" "}
                      <Badge tone={statusTone(String(row.status ?? ""))}>
                        {String(row.status ?? "")}
                      </Badge>
                    </p>
                    <p className="mt-1 break-words text-sm">
                      {preview?.title || preview?.summary || ""}
                    </p>
                    {canDecide(row) ? (
                      <div className="mt-3 flex gap-2">
                        <Button
                          disabled={locked}
                          type="button"
                          onClick={() => void decide([row], "approve")}
                        >
                          {t("approve")}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          disabled={locked}
                          onClick={() => void decide([row], "reject")}
                        >
                          {t("reject")}
                        </Button>
                      </div>
                    ) : null}
                    {scope === "to_decide" && row.status === "pending" && !hasHash(row) ? (
                      <p className="mt-3 text-sm text-[var(--muted-foreground)]">
                        {t("queueHashUnavailable")}
                      </p>
                    ) : null}
                    {row.status === "pending" && recorded.has(id) ? (
                      <p className="mt-3 text-sm text-[var(--muted-foreground)]">
                        {t("decisionWaiting")}
                      </p>
                    ) : null}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
        {!loading && rows.length > 0 ? <ListPagination {...pagination} label={t("title")} /> : null}
        {picked.length > 0 ? (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <p className="text-sm" role="status">
              {t("selectionCount", { count: picked.length })}
            </p>
            <Button
              disabled={locked}
              type="button"
              variant="outline"
              onClick={() =>
                void decide(
                  rows.filter((row) => pickedIds.has(String(row.id))),
                  "reject",
                )
              }
            >
              {t("rejectSelected")}
            </Button>
            <Button disabled={busy} type="button" variant="ghost" onClick={() => setPicked([])}>
              {t("clearSelection")}
            </Button>
            <p className="w-full text-xs text-[var(--muted-foreground)]">{t("queueBulkHelp")}</p>
          </div>
        ) : null}
        {!loading && (picked.length > 0 || pagination.rows.some(canDecide)) ? (
          <div className="mt-6 block rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 text-sm">
            <label htmlFor="approval-comment">{t("comment")}</label>
            <p id="approval-comment-help" className="mt-1 text-xs text-[var(--muted-foreground)]">
              {t("queueCommentHelp")}
            </p>
            <textarea
              id="approval-comment"
              aria-describedby="approval-comment-help"
              disabled={busy}
              className="mt-1 h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
          </div>
        ) : null}
        {advanced && canManageStanding ? (
          <section className="mt-8 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
            <h2 className="text-lg font-medium">{t("standing")}</h2>
            {standingError ? (
              <div role="alert" className="mt-3 text-sm">
                <ErrorMessage error={standingError} />{" "}
                <Button type="button" variant="outline" onClick={() => void refresh()}>
                  {t("retry")}
                </Button>
              </div>
            ) : null}
            {!loading && !standingError && standing.length === 0 ? (
              <p className="mt-2">{t("noStanding")}</p>
            ) : null}
            {!standingError && standing.length > 0 ? (
              <Input
                type="search"
                className="mt-4 max-w-xl"
                aria-label={t("searchStanding")}
                placeholder={t("searchStanding")}
                value={standingQuery}
                onChange={(event) => setStandingQuery(event.target.value)}
              />
            ) : null}
            {!standingError && standing.length > 0 && standingFiltered.length === 0 ? (
              <p className="mt-3 text-sm">{t("noMatches")}</p>
            ) : null}
            <ul className="mt-3 space-y-2">
              {standingPagination.rows.map((row) => (
                <li
                  key={String(row.id)}
                  className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] py-3"
                >
                  <div className="min-w-0 space-y-1 break-words text-sm">
                    <p className="font-medium">
                      {String((row.tool as Row | undefined)?.name || t("unavailableTool"))}
                    </p>
                    {row.expiresAt ? (
                      <p className="text-xs text-[var(--muted-foreground)]">
                        {t(
                          new Date(String(row.expiresAt)).getTime() <= Date.now()
                            ? "standingExpired"
                            : "standingExpires",
                          {
                            date: Number.isFinite(new Date(String(row.expiresAt)).getTime())
                              ? formatDateTime(String(row.expiresAt), locale)
                              : t("standingTimeUnavailable"),
                          },
                        )}
                      </p>
                    ) : null}
                    {(row.routine as Row | undefined)?.id ? (
                      <a
                        className="inline-block underline underline-offset-4"
                        href={`/routines/${String((row.routine as Row).id)}`}
                      >
                        {t("viewRoutine")}
                      </a>
                    ) : null}
                  </div>
                  {row.revokedAt ? (
                    <span className="text-xs text-[var(--muted-foreground)]">{t("revoked")}</span>
                  ) : (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={locked || Boolean(standingError)}
                      onClick={() => void revoke(row)}
                    >
                      {t("revoke")}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
            {!standingError && standing.length > 0 ? (
              <ListPagination {...standingPagination} label={t("standing")} />
            ) : null}
          </section>
        ) : null}
      </fieldset>
    </AppShell>
  );
}
