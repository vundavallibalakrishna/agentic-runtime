"use client";

import { RefreshCw } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ActionStatus, DetailState, ErrorMessage } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { ReferencePicker } from "@/components/common/reference-picker";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Meter } from "@/components/usage/meter";
import { ApiError, api, type DisplayError } from "@/lib/api";
import {
  CURRENCY_AMOUNT_PATTERN,
  formatCount,
  formatDateTime,
  fromMicros,
  toMicros,
} from "@/lib/format";
import { loadSession } from "@/lib/session";

type Scope = { id: string; name?: string } | null;
type Quota = {
  id: string;
  scopeType: string;
  scope: Scope;
  metric: string;
  period: string;
  limitValue: number;
  action: string;
  warnAtPct: number;
  used: number;
  implicit: boolean;
  resetsAt?: string;
};
type Operation = { controller: AbortController; kind: "read" | "save" | "remove" };
const MODE_KEY = "ar-settings-mode";
const field =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)]";
const metricsAvailable = [
  "model_tokens",
  "runs",
  "tool_calls",
  "sandbox_cpu_seconds",
  "cost_micros",
];
const whole = (value: unknown): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const text = (value: unknown): value is string =>
  typeof value === "string" && Boolean(value.trim());
function quotaValid(value: unknown): value is Quota {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  const scope = row.scope as Record<string, unknown> | null | undefined;
  return (
    text(row.id) &&
    text(row.scopeType) &&
    text(row.metric) &&
    text(row.period) &&
    text(row.action) &&
    whole(row.limitValue) &&
    whole(row.used) &&
    whole(row.warnAtPct) &&
    row.warnAtPct >= 1 &&
    row.warnAtPct <= 100 &&
    typeof row.implicit === "boolean" &&
    (scope === null ||
      Boolean(
        scope &&
          typeof scope === "object" &&
          text(scope.id) &&
          (scope.name === undefined || typeof scope.name === "string"),
      )) &&
    (row.resetsAt === undefined ||
      (text(row.resetsAt) &&
        /(?:Z|[+-]\d{2}:\d{2})$/i.test(row.resetsAt) &&
        Number.isFinite(new Date(row.resetsAt).getTime())))
  );
}
const identity = (row: Pick<Quota, "scopeType" | "scope" | "metric" | "period">) =>
  JSON.stringify([row.scopeType, row.scope?.id ?? null, row.metric, row.period]);
const accessLost = (error: unknown) =>
  error instanceof ApiError &&
  (error.status === 401 || (error.status === 403 && error.code !== "csrf_failed"));

export function QuotasScreen() {
  const t = useTranslations("quotas"),
    locale = useLocale();
  const [rows, setRows] = useState<Quota[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<DisplayError>("");
  const [actionError, setActionError] = useState<{ target: string; message: DisplayError } | null>(
    null,
  );
  const [notice, setNotice] = useState("");
  const [noticeTarget, setNoticeTarget] = useState("form");
  const [metric, setMetric] = useState("model_tokens");
  const [period, setPeriod] = useState("day");
  const [scope, setScope] = useState("user");
  const [limit, setLimit] = useState("");
  const [attempted, setAttempted] = useState(false);
  const [action, setAction] = useState("");
  const [warn, setWarn] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [pending, setPending] = useState<Operation["kind"] | null>("read");
  const [needsCheck, setNeedsCheck] = useState(false);
  const [canRead, setCanRead] = useState<boolean | null>(null);
  const [canManage, setCanManage] = useState(false);
  const [canPickPeople, setCanPickPeople] = useState(false);
  const [canPickAgents, setCanPickAgents] = useState(false);
  const [scopeId, setScopeId] = useState("");
  const [editing, setEditing] = useState<Quota | null>(null);
  const [removing, setRemoving] = useState<Quota | null>(null);
  const operation = useRef<Operation | null>(null);
  const limitInput = useRef<HTMLInputElement>(null);
  const metricInput = useRef<HTMLSelectElement>(null);
  const editButton = useRef<HTMLButtonElement | null>(null);
  const removeButton = useRef<HTMLButtonElement | null>(null);
  const refreshButton = useRef<HTMLButtonElement>(null);
  const cancelRemove = useRef<HTMLButtonElement>(null);
  const feedback = useRef<HTMLDivElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [metricFilter, setMetricFilter] = useState("");
  const [scopeFilter, setScopeFilter] = useState("");
  const [periodFilter, setPeriodFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const busy = Boolean(pending);
  const money = metric === "cost_micros";
  const parsedLimit = money
    ? toMicros(limit)
    : limit.trim() && whole(Number(limit))
      ? Number(limit)
      : null;
  const warningValid = !warn.trim()
    ? !editing
    : Number.isInteger(Number(warn)) && Number(warn) >= 1 && Number(warn) <= 100;
  const actionValid =
    ["block", "warn"].includes(action) || (!editing && !action) || editing?.action === action;
  const needsTarget = scope === "team" || scope === "agent" || scope === "person";
  const targetLabel = t(scope === "person" ? "person" : scope === "team" ? "team" : "agent");
  const targetEndpoint =
    scope === "person" ? "/api/v1/users" : scope === "team" ? "/api/v1/teams" : "/api/v1/agents";
  const metricLabel = useCallback(
    (value: string) => (t.has(`metrics.${value}`) ? t(`metrics.${value}`) : value),
    [t],
  );
  const scopeLabel = useCallback(
    (row: Quota) =>
      row.scope?.name?.trim() ||
      row.scope?.id ||
      (t.has(row.scopeType) ? t(row.scopeType) : row.scopeType),
    [t],
  );
  const behaviorLabel = (value: string) =>
    value === "block"
      ? t("block")
      : value === "warn"
        ? t("warnOnly")
        : value || t("serviceDefault");
  const amount = (row: Quota, value: number) =>
    row.metric === "cost_micros" ? fromMicros(value) : formatCount(value);
  const rowIndex = useMemo(() => new Map(rows.map((row) => [row.id, row])), [rows]);
  const currentEdit = editing ? rowIndex.get(editing.id) : null;
  const currentRemove = removing ? rowIndex.get(removing.id) : null;
  const searchRows = useMemo(
    () =>
      rows.map((row) => ({
        row,
        text: [row.id, row.scope?.id, row.scope?.name, scopeLabel(row), metricLabel(row.metric)]
          .join("\n")
          .toLocaleLowerCase(),
      })),
    [rows, scopeLabel, metricLabel],
  );
  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return searchRows
      .filter(
        (item) =>
          (!metricFilter || item.row.metric === metricFilter) &&
          (!scopeFilter || item.row.scopeType === scopeFilter) &&
          (!periodFilter || item.row.period === periodFilter) &&
          (!actionFilter || item.row.action === actionFilter) &&
          item.text.includes(term),
      )
      .map((item) => item.row);
  }, [searchRows, query, metricFilter, scopeFilter, periodFilter, actionFilter]);
  const pagination = usePagedRows(
    filtered,
    JSON.stringify([query, metricFilter, scopeFilter, periodFilter, actionFilter]),
  );
  const choices = useMemo(
    () => ({
      metrics: [...new Set([metricFilter, ...rows.map((row) => row.metric)])]
        .filter(Boolean)
        .sort(),
      scopes: [...new Set([scopeFilter, ...rows.map((row) => row.scopeType)])]
        .filter(Boolean)
        .sort(),
      periods: [...new Set([periodFilter, ...rows.map((row) => row.period)])]
        .filter(Boolean)
        .sort(),
      actions: [...new Set([actionFilter, ...rows.map((row) => row.action)])]
        .filter(Boolean)
        .sort(),
    }),
    [rows, metricFilter, scopeFilter, periodFilter, actionFilter],
  );

  const deny = useCallback(() => {
    setCanRead(false);
    setCanManage(false);
    setRows([]);
    setLoaded(false);
    setEditing(null);
    setRemoving(null);
  }, []);
  const permissions = useCallback(
    async (active: Operation, write = false) => {
      const session = await loadSession();
      if (active.controller.signal.aborted) return false;
      const grants = session.permissions ?? [],
        allowed = grants.includes("usage:read");
      setCanRead(allowed);
      setCanManage(grants.includes("quotas:manage"));
      setCanPickPeople(grants.includes("users:read"));
      setCanPickAgents(grants.includes("agents:read"));
      if (!allowed) {
        deny();
        return false;
      }
      if (write && !grants.includes("quotas:manage")) throw new Error(t("readOnly"));
      return true;
    },
    [deny, t],
  );
  const read = useCallback(
    async (active: Operation) => {
      setLoading(true);
      setError("");
      try {
        if (!(await permissions(active))) return null;
        const page = await api<{ items: unknown[] }>("/api/v1/quotas", {
          signal: active.controller.signal,
        });
        if (active.controller.signal.aborted) return null;
        if (!Array.isArray(page?.items) || !page.items.every(quotaValid))
          throw new Error(t("metadataError"));
        setRows(page.items);
        setLoaded(true);
        return page.items;
      } catch (caught) {
        if (!active.controller.signal.aborted) {
          setError(caught instanceof Error ? caught : t("error"));
          if (accessLost(caught)) deny();
        }
        return null;
      } finally {
        if (!active.controller.signal.aborted) setLoading(false);
      }
    },
    [permissions, deny, t],
  );
  useEffect(() => {
    const active: Operation = { controller: new AbortController(), kind: "read" };
    operation.current = active;
    void read(active).finally(() => {
      if (operation.current === active) {
        operation.current = null;
        setPending(null);
      }
    });
    return () => {
      operation.current?.controller.abort();
      operation.current = null;
    };
  }, [read]);
  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);
  useEffect(() => {
    if (editing) limitInput.current?.focus();
  }, [editing]);
  useEffect(() => {
    if (actionError) feedback.current?.focus();
  }, [actionError]);
  async function refresh() {
    if (operation.current) return;
    const active: Operation = { controller: new AbortController(), kind: "read" };
    operation.current = active;
    setPending("read");
    try {
      const saved = await read(active);
      if (saved && !active.controller.signal.aborted && needsCheck) {
        setNeedsCheck(false);
        setActionError(null);
        setNotice(t("checked"));
      }
    } finally {
      if (operation.current === active) {
        operation.current = null;
        setPending(null);
      }
    }
  }
  function chooseMode(next: boolean) {
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }
  function resetForm() {
    setEditing(null);
    setScopeId("");
    setScope("user");
    setMetric("model_tokens");
    setPeriod("day");
    setLimit("");
    setAttempted(false);
    setAction("");
    setWarn("");
    if (!needsCheck) setActionError(null);
  }
  function edit(row: Quota, trigger: HTMLButtonElement) {
    if (!canManage || busy || needsCheck || error || row.implicit) return;
    editButton.current = trigger;
    setAttempted(false);
    setEditing(row);
    setMetric(row.metric);
    setPeriod(row.period);
    setScope(row.scopeType === "user" && row.scope?.id ? "person" : row.scopeType);
    setScopeId(row.scope?.id ?? "");
    setLimit(row.metric === "cost_micros" ? fromMicros(row.limitValue) : String(row.limitValue));
    setAction(row.action);
    setWarn(String(row.warnAtPct));
    setActionError(null);
    setNotice("");
  }
  function changes() {
    const body: Record<string, unknown> = {};
    if (!editing || parsedLimit !== editing.limitValue) body.limitValue = parsedLimit;
    if (action && (!editing || action !== editing.action)) body.action = action;
    if (warn.trim() && (!editing || Number(warn) !== editing.warnAtPct))
      body.warnAtPct = Number(warn);
    return body;
  }
  const hasChanges = !editing || Object.keys(changes()).length > 0;
  const writable = canManage && canRead && loaded && !busy && !needsCheck && !error;
  async function save() {
    if (operation.current || !writable || editing?.implicit) return;
    if (parsedLimit === null) {
      setAttempted(true);
      limitInput.current?.focus();
      return;
    }
    if (!warningValid) return;
    const validation = !actionValid
      ? t("invalidForm")
      : !editing &&
          needsTarget &&
          (!scopeId || (scope === "agent" ? !canPickAgents : !canPickPeople))
        ? t("targetRequired")
        : !editing &&
            (!metricsAvailable.includes(metric) ||
              !["day", "month"].includes(period) ||
              !["tenant", "user", "person", "team", "agent"].includes(scope))
          ? t("invalidForm")
          : editing &&
              (!currentEdit || currentEdit.implicit || identity(currentEdit) !== identity(editing))
            ? t("missingEdit")
            : "";
    if (validation) {
      setActionError({ target: "form", message: validation });
      return;
    }
    const change = changes();
    if (!Object.keys(change).length) return;
    const target = editing;
    const expected = {
      scopeType: target?.scopeType ?? (scope === "person" ? "user" : scope),
      scope: target?.scope ?? (needsTarget ? { id: scopeId } : null),
      metric: target?.metric ?? metric,
      period: target?.period ?? period,
    };
    const body = target
      ? change
      : {
          ...change,
          scopeType: expected.scopeType,
          scopeId: expected.scope?.id ?? null,
          metric,
          period,
        };
    const active: Operation = { controller: new AbortController(), kind: "save" };
    operation.current = active;
    setPending("save");
    setNoticeTarget("form");
    setActionError(null);
    setNotice("");
    try {
      if (!(await permissions(active, true))) return;
      const receipt = await api<unknown>(
        target ? `/api/v1/quotas/${encodeURIComponent(target.id)}` : "/api/v1/quotas",
        {
          method: target ? "PATCH" : "POST",
          body: JSON.stringify(body),
          signal: active.controller.signal,
        },
      );
      if (active.controller.signal.aborted) return;
      if (
        !quotaValid(receipt) ||
        receipt.implicit ||
        (target && receipt.id !== target.id) ||
        identity(receipt) !== identity(expected) ||
        Object.entries(change).some(
          ([key, value]) => (receipt as unknown as Record<string, unknown>)[key] !== value,
        )
      )
        throw new Error(t("saveUnconfirmed"));
      setNotice(t("saved"));
      resetForm();
      const saved = await read(active);
      if (active.controller.signal.aborted) return;
      if (
        saved &&
        !saved.some(
          (row) =>
            row.id === receipt.id &&
            identity(row) === identity(receipt) &&
            Object.entries(change).every(
              ([key, value]) => (row as unknown as Record<string, unknown>)[key] === value,
            ),
        )
      )
        setNotice(t("savedNotListed"));
    } catch (caught) {
      if (!active.controller.signal.aborted) {
        setActionError({ target: "form", message: caught instanceof Error ? caught : t("error") });
        setNeedsCheck(true);
        if (accessLost(caught)) deny();
      }
    } finally {
      if (operation.current === active) {
        operation.current = null;
        setPending(null);
      }
    }
  }
  async function remove() {
    const row = currentRemove;
    if (
      operation.current ||
      !writable ||
      !row ||
      row.implicit ||
      !removing ||
      identity(row) !== identity(removing)
    )
      return;
    const active: Operation = { controller: new AbortController(), kind: "remove" };
    operation.current = active;
    setPending("remove");
    setNoticeTarget(row.id);
    setActionError(null);
    setNotice("");
    try {
      if (!(await permissions(active, true))) return;
      const response = await api<unknown>(`/api/v1/quotas/${encodeURIComponent(row.id)}`, {
        method: "DELETE",
        signal: active.controller.signal,
      });
      if (active.controller.signal.aborted) return;
      if (response !== undefined) throw new Error(t("removeUnconfirmed"));
      const saved = await read(active);
      if (active.controller.signal.aborted) return;
      if (saved === null) {
        setNotice(t("removalReadFailed"));
        setNeedsCheck(true);
      } else if (saved.some((item) => item.id === row.id)) {
        setNotice(t("removeNotReflected"));
        setNeedsCheck(true);
      } else {
        setNotice(t("removed"));
        if (editing?.id === row.id) resetForm();
      }
      setRemoving(null);
    } catch (caught) {
      if (!active.controller.signal.aborted) {
        setActionError({ target: row.id, message: caught instanceof Error ? caught : t("error") });
        setNeedsCheck(true);
        if (accessLost(caught)) deny();
      }
    } finally {
      if (operation.current === active) {
        operation.current = null;
        setPending(null);
      }
    }
  }
  const problem = actionError ? (
    <div
      ref={feedback}
      role="alert"
      tabIndex={-1}
      className="mb-3 space-y-2 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 text-sm"
    >
      {canRead && actionError.target !== "form" ? (
        <p className="break-all font-medium">{t("removeNamed", { id: actionError.target })}</p>
      ) : null}
      <ErrorMessage error={actionError.message} />
      {needsCheck ? (
        <>
          <p>{t("checkBeforeRetry")}</p>
          <Button type="button" variant="outline" disabled={busy} onClick={() => void refresh()}>
            {t("refresh")}
          </Button>
        </>
      ) : null}
    </div>
  ) : null;
  const valueInvalid = parsedLimit === null && (limit !== "" || attempted);
  const editUnavailable = Boolean(
    editing &&
      (!currentEdit || currentEdit.implicit || identity(currentEdit) !== identity(editing)),
  );
  const clearFilters = () => {
    setQuery("");
    setMetricFilter("");
    setScopeFilter("");
    setPeriodFilter("");
    setActionFilter("");
    search.current?.focus();
  };

  return (
    <AppShell>
      <PageHeader
        title={t("title")}
        body={t("body")}
        actions={
          <div className="flex flex-wrap gap-2">
            {canManage && canRead ? (
              <Button
                type="button"
                className="xl:hidden"
                disabled={busy}
                onClick={() =>
                  editing ? limitInput.current?.focus() : metricInput.current?.focus()
                }
              >
                {t(editing ? "editTitle" : "createTitle")}
              </Button>
            ) : null}
            <Button asChild variant="outline">
              <button
                ref={refreshButton}
                aria-label={t("refresh")}
                className="inline-flex items-center gap-2"
                type="button"
                disabled={busy}
                onClick={() => void refresh()}
              >
                <RefreshCw size={16} aria-hidden="true" />
                <span className="hidden sm:inline">{t("refresh")}</span>
              </button>
            </Button>
            <SettingsMode advanced={advanced} onChange={chooseMode} />
          </div>
        }
      />
      <DetailState
        loading={loading && !loaded}
        error={error}
        onRetry={busy ? undefined : () => void refresh()}
      />
      {canRead === false ? <p className="mb-4 text-sm">{t("denied")}</p> : null}
      {(!canRead || !canManage) && actionError?.target === "form" ? problem : null}
      {canRead ? (
        <ManagementLayout
          title={t("listTitle")}
          formTitle={t(editing ? "editTitle" : "createTitle")}
          form={
            canManage ? (
              <form
                className="grid gap-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void save();
                }}
              >
                <p className="text-sm leading-relaxed text-[var(--muted-foreground)]">
                  {t(editing ? "editBehavior" : "formHelp")}
                </p>
                <ActionStatus
                  busy={pending === "save"}
                  busyLabel={t("saving")}
                  notice={noticeTarget === "form" ? notice : ""}
                />
                {actionError?.target === "form" ? problem : null}
                <fieldset disabled={busy} className="grid min-w-0 gap-4">
                  {editing ? (
                    <p className="break-words text-sm text-[var(--muted-foreground)]">
                      {t("editingScope", { name: scopeLabel(currentEdit ?? editing) })}
                    </p>
                  ) : null}
                  {editUnavailable ? (
                    <p className="text-sm" role="status">
                      {t("missingEdit")}
                    </p>
                  ) : null}
                  <div className="text-sm">
                    <label className="mb-1 block" htmlFor="quota-metric">
                      {t("metric")}
                    </label>
                    <select
                      ref={metricInput}
                      className={field}
                      id="quota-metric"
                      disabled={Boolean(editing)}
                      value={metric}
                      onChange={(event) => {
                        setMetric(event.target.value);
                        setLimit("");
                      }}
                    >
                      {editing && !metricsAvailable.includes(metric) ? (
                        <option value={metric}>{metricLabel(metric)}</option>
                      ) : null}
                      {metricsAvailable.map((value) => (
                        <option key={value} value={value}>
                          {metricLabel(value)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="text-sm">
                    <label className="mb-1 block" htmlFor="quota-period">
                      {t("period")}
                    </label>
                    <select
                      className={field}
                      id="quota-period"
                      disabled={Boolean(editing)}
                      value={period}
                      onChange={(event) => setPeriod(event.target.value)}
                    >
                      {editing && !["day", "month"].includes(period) ? (
                        <option value={period}>{period}</option>
                      ) : null}
                      <option value="day">{t("day")}</option>
                      <option value="month">{t("month")}</option>
                    </select>
                  </div>
                  <div className="text-sm">
                    <label className="mb-1 block" htmlFor="quota-scope">
                      {t("scope")}
                    </label>
                    <select
                      className={field}
                      id="quota-scope"
                      disabled={Boolean(editing)}
                      value={scope}
                      onChange={(event) => {
                        setScope(event.target.value);
                        setScopeId("");
                      }}
                    >
                      <option value="user">{t("user")}</option>
                      <option value="tenant">{t("tenant")}</option>
                      <option value="person" disabled={!canPickPeople}>
                        {t("person")}
                      </option>
                      <option value="team" disabled={!canPickPeople}>
                        {t("team")}
                      </option>
                      {editing && !["user", "tenant", "person", "team", "agent"].includes(scope) ? (
                        <option value={scope}>{t.has(scope) ? t(scope) : scope}</option>
                      ) : null}
                      <option value="agent" disabled={!canPickAgents}>
                        {t("agent")}
                      </option>
                    </select>
                  </div>
                  {!editing && (!canPickPeople || !canPickAgents) ? (
                    <p className="text-xs text-[var(--muted-foreground)]">{t("targetAccess")}</p>
                  ) : null}
                  {!editing && needsTarget ? (
                    <ReferencePicker
                      key={scope}
                      label={targetLabel}
                      endpoint={targetEndpoint}
                      value={scopeId}
                      onChange={setScopeId}
                      required
                      disabled={busy}
                    />
                  ) : null}
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {t(scope === "user" ? "eachPersonHelp" : "scopeHelp")}
                  </p>
                  <label className="text-sm" htmlFor="quota-limit">
                    {t(money ? "spendLimit" : "limit")}
                    <Input
                      ref={limitInput}
                      className="mt-1"
                      id="quota-limit"
                      type={money ? "text" : "number"}
                      inputMode={money ? "decimal" : "numeric"}
                      min={money ? undefined : 0}
                      max={money ? undefined : Number.MAX_SAFE_INTEGER}
                      step={money ? undefined : 1}
                      pattern={money ? CURRENCY_AMOUNT_PATTERN : undefined}
                      required
                      aria-invalid={valueInvalid}
                      aria-describedby="quota-limit-help quota-limit-error"
                      value={limit}
                      onChange={(event) => setLimit(event.target.value)}
                    />
                  </label>
                  <p
                    className="text-xs leading-relaxed text-[var(--muted-foreground)]"
                    id="quota-limit-help"
                  >
                    {t.has(`limitHelp.${metric}`) ? t(`limitHelp.${metric}`) : ""}
                    {parsedLimit === 0 ? ` ${t("zeroHelp")}` : ""}
                  </p>
                  <p
                    id="quota-limit-error"
                    className={valueInvalid ? "text-sm text-[var(--destructive)]" : "sr-only"}
                    role={valueInvalid ? "alert" : undefined}
                  >
                    {valueInvalid ? t(money ? "invalidMoney" : "invalidLimit") : ""}
                  </p>
                  {advanced ? (
                    <>
                      <div className="text-sm">
                        <label className="mb-1 block" htmlFor="quota-action">
                          {t("action")}
                        </label>
                        <select
                          className={field}
                          id="quota-action"
                          value={action}
                          onChange={(event) => setAction(event.target.value)}
                        >
                          {!editing ? (
                            <option value="">{t("serviceDefault")}</option>
                          ) : !["block", "warn"].includes(action) ? (
                            <option value={action}>{action}</option>
                          ) : null}
                          <option value="block">{t("block")}</option>
                          <option value="warn">{t("warnOnly")}</option>
                        </select>
                      </div>
                      <label className="text-sm" htmlFor="quota-warn">
                        {t("warn")}
                        <Input
                          className="mt-1"
                          id="quota-warn"
                          required={Boolean(editing)}
                          step={1}
                          max={100}
                          min={1}
                          aria-invalid={!warningValid}
                          type="number"
                          value={warn}
                          onChange={(event) => setWarn(event.target.value)}
                        />
                      </label>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => {
                          setAction(editing ? (currentEdit ?? editing).action : "");
                          setWarn(editing ? String((currentEdit ?? editing).warnAtPct) : "");
                        }}
                      >
                        {t(editing ? "restoreBehavior" : "resetBehavior")}
                      </Button>
                    </>
                  ) : null}
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {action && warn.trim()
                      ? t("behaviorSummary", {
                          action: behaviorLabel(action),
                          percent: Number(warn),
                        })
                      : t("behaviorPartial", {
                          action: behaviorLabel(action),
                          percent: warn.trim() ? `${Number(warn)}%` : t("defaultWarning"),
                        })}
                  </p>
                  {!warningValid ? (
                    <p role="alert" className="text-sm text-[var(--destructive)]">
                      {t("invalidWarn")}
                    </p>
                  ) : null}
                  {needsCheck ? (
                    <p className="text-xs text-[var(--muted-foreground)]">
                      {t("checkBeforeRetry")}
                    </p>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="submit"
                      disabled={
                        !writable ||
                        parsedLimit === null ||
                        !warningValid ||
                        !actionValid ||
                        (!editing && needsTarget && !scopeId) ||
                        editUnavailable ||
                        !hasChanges
                      }
                    >
                      {t(pending === "save" ? "saving" : editing ? "saveChanges" : "save")}
                    </Button>
                    {editing ? (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => {
                          resetForm();
                          if (editButton.current?.isConnected && !editButton.current.disabled)
                            editButton.current.focus();
                          else metricInput.current?.focus();
                        }}
                      >
                        {t("cancel")}
                      </Button>
                    ) : null}
                  </div>
                </fieldset>
              </form>
            ) : null
          }
        >
          {!canManage ? (
            <p className="mb-4 text-sm text-[var(--muted-foreground)]">{t("readOnly")}</p>
          ) : null}
          <ActionStatus
            busy={pending === "remove"}
            busyLabel={t("removing")}
            notice={noticeTarget !== "form" ? notice : ""}
          />
          {actionError && actionError.target !== "form" && !removing ? problem : null}
          {needsCheck && noticeTarget !== "form" && !actionError ? (
            <Button
              className="mb-4"
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => void refresh()}
            >
              {t("refresh")}
            </Button>
          ) : null}
          {loaded && (loading || error) ? (
            <p className="mb-4 text-sm text-[var(--muted-foreground)]" role="status">
              {t("retained")}
            </p>
          ) : null}
          {rows.length ? (
            <fieldset aria-label={t("filters")} className="mb-4 grid min-w-0 gap-3">
              <Input
                ref={search}
                type="search"
                aria-label={t("search")}
                placeholder={t("search")}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <div className="grid gap-3 sm:grid-cols-2">
                {(
                  [
                    [
                      "metric",
                      metricFilter,
                      setMetricFilter,
                      choices.metrics,
                      t("allMetrics"),
                      metricLabel,
                    ],
                    [
                      "scope",
                      scopeFilter,
                      setScopeFilter,
                      choices.scopes,
                      t("allScopes"),
                      (value: string) =>
                        value === "user" ? t("people") : t.has(value) ? t(value) : value,
                    ],
                    [
                      "period",
                      periodFilter,
                      setPeriodFilter,
                      choices.periods,
                      t("allPeriods"),
                      (value: string) => (t.has(value) ? t(value) : value),
                    ],
                    [
                      "action",
                      actionFilter,
                      setActionFilter,
                      choices.actions,
                      t("allActions"),
                      behaviorLabel,
                    ],
                  ] as const
                ).map(([key, value, change, options, all, label]) => (
                  <div key={key} className="min-w-0 text-sm">
                    <label className="mb-1 block" htmlFor={`quota-filter-${key}`}>
                      {t(key)}
                    </label>
                    <select
                      id={`quota-filter-${key}`}
                      className={field}
                      value={value}
                      onChange={(event) => change(event.target.value)}
                    >
                      <option value="">{all}</option>
                      {options.map((item) => (
                        <option key={item} value={item}>
                          {label(item)}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
              {query || metricFilter || scopeFilter || periodFilter || actionFilter ? (
                <Button className="w-fit" type="button" variant="outline" onClick={clearFilters}>
                  {t("clear")}
                </Button>
              ) : null}
            </fieldset>
          ) : null}
          {loaded && !rows.length && !error ? (
            <EmptyState title={t(canManage ? "empty" : "emptyReadOnly")} />
          ) : null}
          {rows.length && !filtered.length ? <EmptyState title={t("noMatches")} /> : null}
          <ul className="row-list">
            {pagination.rows.map((row) => (
              <li className="min-w-0 p-4" key={row.id}>
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-medium">
                      {metricLabel(row.metric)} · {t.has(row.period) ? t(row.period) : row.period}
                    </h3>
                    <p className="break-words text-sm text-[var(--muted-foreground)]">
                      {scopeLabel(row)}
                      {row.implicit ? ` · ${t("plan")}` : ""}
                    </p>
                  </div>
                  <p className="text-sm">
                    {t("used")} {amount(row, row.used)} / {amount(row, row.limitValue)}
                  </p>
                </div>
                <Meter
                  limit={row.limitValue}
                  used={row.used}
                  label={t("meter", {
                    metric: metricLabel(row.metric),
                    name: scopeLabel(row),
                    used: amount(row, row.used),
                    limit: amount(row, row.limitValue),
                  })}
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge>{behaviorLabel(row.action)}</Badge>
                  <span className="text-xs text-[var(--muted-foreground)]">
                    {t("warningAt", { percent: row.warnAtPct })}
                  </span>
                </div>
                {row.scopeType === "user" && !row.scope?.id ? (
                  <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                    {t("eachPersonUsage")}
                  </p>
                ) : null}
                {row.resetsAt ? (
                  <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                    {t("resetAt", { time: formatDateTime(row.resetsAt, locale) })}
                  </p>
                ) : null}
                <details className="mt-2 text-xs text-[var(--muted-foreground)]">
                  <summary className="cursor-pointer">
                    {t("reference", { id: row.id.slice(-8) })}
                  </summary>
                  <p className="mt-1 break-all font-mono">{row.id}</p>
                </details>
                {row.implicit || !canManage ? null : (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!writable}
                      aria-label={t("editNamed", { id: row.id })}
                      onClick={(event) => edit(row, event.currentTarget)}
                    >
                      {t("edit")}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!writable}
                      aria-label={t("removeNamed", { id: row.id })}
                      onClick={(event) => {
                        removeButton.current = event.currentTarget;
                        setRemoving(row);
                      }}
                    >
                      {t("remove")}
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
          {loaded && rows.length ? <ListPagination {...pagination} label={t("listTitle")} /> : null}
        </ManagementLayout>
      ) : null}
      <Dialog
        open={Boolean(removing)}
        onOpenChange={(open) => {
          if (!open && !operation.current) setRemoving(null);
        }}
      >
        <DialogContent
          title={t("removeTitle")}
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            cancelRemove.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (removeButton.current?.isConnected && !removeButton.current.disabled)
              removeButton.current.focus();
            else refreshButton.current?.focus();
          }}
        >
          <p className="mt-3 text-sm">{t("removeHelp")}</p>
          {removing ? (
            <>
              <p className="mt-3 break-words font-medium">
                {metricLabel(removing.metric)} · {scopeLabel(removing)}
              </p>
              <p className="my-3 break-all font-mono text-xs">{removing.id}</p>
            </>
          ) : null}
          {!currentRemove || currentRemove.implicit ? (
            <p className="my-3 text-sm">{t("missingRemove")}</p>
          ) : null}
          <ActionStatus busy={pending === "remove"} busyLabel={t("removing")} />
          {actionError && actionError.target === removing?.id ? problem : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <button
                ref={cancelRemove}
                type="button"
                disabled={busy}
                onClick={() => setRemoving(null)}
              >
                {t("cancelRemove")}
              </button>
            </Button>
            <Button
              type="button"
              disabled={!writable || !currentRemove || currentRemove.implicit}
              onClick={() => void remove()}
            >
              {t(pending === "remove" ? "removing" : "removeConfirm")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
