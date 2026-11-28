"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, DetailState } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { ReferencePicker } from "@/components/common/reference-picker";
import { ScheduleFields } from "@/components/common/schedule-fields";
import { PageHeader } from "@/components/page-header";
import {
  type DeliveryChoice,
  DeliveryFields,
  deliveryTargets,
  NO_DELIVERY,
} from "@/components/routines/delivery-fields";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { isAvailableAgent } from "@/lib/agent-availability";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { loadSession } from "@/lib/session";

type Routine = {
  id: string;
  name: string;
  status?: string;
  triggerType?: string;
  triggerSummary?: string;
  webhookUrl?: string | null;
  concurrencyPolicy?: string;
};

type EventRow = {
  id: string;
  status?: string;
  receivedAt?: string;
  source?: string;
  envelopePreview?: string;
  runId?: string | null;
};
type Created = Routine & { webhook?: { webhookUrl?: string; webhookSecret?: string } };

export function SchedulesScreen() {
  const t = useTranslations("schedules");
  const locale = useLocale();
  const availability = useTranslations("agentAvailability");
  const [rows, setRows] = useState<Routine[]>([]);
  const [canUse, setCanUse] = useState(false);
  const [eventState, setEventState] = useState<{
    id: string;
    rows: EventRow[];
    loading: boolean;
    error: string;
  }>({ id: "", rows: [], loading: false, error: "" });
  const listRequest = useRef<AbortController | null>(null);
  const eventRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const selectedRef = useRef("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [trigger, setTrigger] = useState("");
  const [eventQuery, setEventQuery] = useState("");
  const [eventStatus, setEventStatus] = useState("");
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [runId, setRunId] = useState("");
  const [receipt, setReceipt] = useState<{
    id: string;
    name: string;
    secret: string;
    url: string;
  } | null>(null);
  const [recovery, setRecovery] = useState<{
    detail: string;
    accepted: boolean;
    routineId?: string;
    name?: string;
  } | null>(null);
  const [actionTarget, setActionTarget] = useState("");
  const [action, setAction] = useState("");
  const busy = Boolean(action);
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [kind, setKind] = useState("schedule");
  const [cron, setCron] = useState("0 9 * * 1");
  const [timezone, setTimezone] = useState("UTC");
  const [overlap, setOverlap] = useState("skip");
  const [delivery, setDelivery] = useState<DeliveryChoice>(NO_DELIVERY);
  const [agentId, setAgentId] = useState("");

  const load = useCallback(
    async (preferredId?: string) => {
      listRequest.current?.abort();
      const request = new AbortController();
      listRequest.current = request;
      setLoading(true);
      setError("");
      try {
        const session = await loadSession();
        if (request.signal.aborted) return false;
        const allowed = session.permissions?.includes("routines:create") ?? false;
        setCanUse(allowed);
        if (!allowed) {
          setReceipt(null);
          setRunId("");
          setRows([]);
          selectedRef.current = "";
          setSelected("");
          return false;
        }
        const page = await api<{ items: Routine[] }>("/api/v1/routines", {
          signal: request.signal,
        });
        if (request.signal.aborted) return false;
        const list = page.items ?? [];
        setRows(list);
        const wanted = preferredId ?? selectedRef.current;
        const next = list.some((row) => row.id === wanted) ? wanted : list[0]?.id || "";
        selectedRef.current = next;
        setSelected(next);
        return true;
      } catch (caught) {
        if (!request.signal.aborted)
          setError(caught instanceof Error ? caught.message : t("error"));
        return false;
      } finally {
        if (listRequest.current === request) {
          listRequest.current = null;
          setLoading(false);
        }
      }
    },
    [t],
  );

  const loadEvents = useCallback(
    async (routineId: string) => {
      eventRequest.current?.abort();
      const request = new AbortController();
      eventRequest.current = request;
      setEventState({ id: routineId, rows: [], loading: Boolean(routineId), error: "" });
      if (!routineId) {
        eventRequest.current = null;
        return true;
      }
      try {
        const page = await api<{ items: EventRow[] }>(`/api/v1/routines/${routineId}/events`, {
          signal: request.signal,
        });
        if (request.signal.aborted || selectedRef.current !== routineId) return false;
        setEventState({ id: routineId, rows: page.items ?? [], loading: false, error: "" });
        return true;
      } catch (caught) {
        if (!request.signal.aborted)
          setEventState({
            id: routineId,
            rows: [],
            loading: false,
            error: caught instanceof Error ? caught.message : t("historyError"),
          });
        return false;
      } finally {
        if (eventRequest.current === request) eventRequest.current = null;
      }
    },
    [t],
  );

  useEffect(() => {
    void load();
    return () => {
      listRequest.current?.abort();
      eventRequest.current?.abort();
      actionRequest.current?.abort();
    };
  }, [load]);
  useEffect(() => {
    if (actionRequest.current) return;
    void loadEvents(selected);
    const request = eventRequest.current;
    return () => {
      if (eventRequest.current === request) request?.abort();
    };
  }, [loadEvents, selected]);

  const matching = rows.filter(
    (row) =>
      (!status || row.status === status) &&
      (!trigger || row.triggerType === trigger) &&
      [row.name, row.id, row.triggerSummary].some((value) =>
        value?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
      ),
  );
  const pagination = usePagedRows(matching, `${query}::${status}::${trigger}`);
  const statuses = [...new Set(rows.flatMap((row) => (row.status ? [row.status] : [])))].sort();
  const triggers = [
    ...new Set(rows.flatMap((row) => (row.triggerType ? [row.triggerType] : []))),
  ].sort();
  const selectedRow = rows.find((row) => row.id === selected);
  const events = eventState.id === selected ? eventState.rows : [];
  const eventLoading = eventState.id !== selected || eventState.loading;
  const eventError = eventState.id === selected ? eventState.error : "";
  const eventStatuses = [
    ...new Set(events.flatMap((row) => (row.status ? [row.status] : []))),
  ].sort();
  const matchingEvents = events.filter(
    (row) =>
      (!eventStatus || row.status === eventStatus) &&
      [row.id, row.status, row.runId, row.source, row.envelopePreview].some((value) =>
        value?.toLocaleLowerCase().includes(eventQuery.trim().toLocaleLowerCase()),
      ),
  );
  const eventPage = usePagedRows(matchingEvents, `${selected}::${eventQuery}::${eventStatus}`);
  const labelStatus = (value: string) =>
    t.has(`statuses.${value}`) ? t(`statuses.${value}`) : value;
  const labelTrigger = (value: string) =>
    t.has(`triggers.${value}`) ? t(`triggers.${value}`) : value;
  function selectRoutine(id: string) {
    selectedRef.current = id;
    setSelected(id);
    setReceipt((current) => (current?.id === id ? current : null));
    setEventQuery("");
    setEventStatus("");
  }

  function beginAction(kind: string, target = "") {
    if (actionRequest.current || loading || (kind !== "refresh" && (!canUse || recovery || error)))
      return null;
    const request = new AbortController();
    actionRequest.current = request;
    setAction(kind);
    setActionTarget(target);
    setNotice("");
    return request;
  }
  function endAction(request: AbortController) {
    if (actionRequest.current === request) {
      actionRequest.current = null;
      setAction("");
    }
  }
  async function refreshAfterAction(request: AbortController, routineId?: string) {
    setAction("refresh");
    const loaded = await load(routineId);
    if (request.signal.aborted) return false;
    if (loaded && routineId && selectedRef.current !== routineId) {
      setRecovery((current) =>
        current
          ? { ...current, detail: t("targetUnavailable") }
          : { accepted: true, routineId, detail: t("targetUnavailable") },
      );
      return false;
    }
    // Replace an activity read begun before the mutation with a fresh saved snapshot.
    const history = loaded ? await loadEvents(selectedRef.current) : false;
    return !request.signal.aborted && loaded && history;
  }
  async function refresh() {
    const request = beginAction("refresh");
    if (!request) return;
    try {
      if (await refreshAfterAction(request, recovery?.routineId)) {
        setRecovery(null);
        setNotice(t("refreshed"));
      }
    } finally {
      endAction(request);
    }
  }
  async function createSchedule() {
    if (!agentId || !name.trim() || !instructions.trim()) return;
    const request = beginAction("create");
    if (!request) return;
    const submittedName = name;
    const submittedInstructions = instructions;
    setReceipt(null);
    setRunId("");
    let accepted = false;
    let confirmedId: string | undefined;
    try {
      const created = await api<Created>("/api/v1/routines", {
        method: "POST",
        signal: request.signal,
        body: JSON.stringify({
          name: submittedName.trim(),
          agentId,
          instructions: submittedInstructions,
          concurrencyPolicy: overlap === "queue" ? "buffer_one" : "skip",
          trigger:
            kind === "webhook"
              ? { type: "webhook", executeModel: true }
              : { type: "schedule", cron, timezone, executeModel: true },
          delivery: deliveryTargets(delivery),
        }),
      });
      if (request.signal.aborted) return;
      if (typeof created?.id !== "string" || !created.id) throw new Error(t("creationUnconfirmed"));
      accepted = true;
      confirmedId = created.id;
      selectRoutine(created.id);
      if (created.webhook?.webhookSecret)
        setReceipt({
          id: created.id,
          name: created.name || submittedName.trim(),
          secret: created.webhook.webhookSecret,
          url: created.webhook.webhookUrl ?? "",
        });
      setName((current) => (current === submittedName ? "" : current));
      setInstructions((current) => (current === submittedInstructions ? "" : current));
      setQuery("");
      setStatus("");
      setTrigger("");
      setNotice(t("created"));
      if (!(await refreshAfterAction(request, created.id)) && !request.signal.aborted)
        setRecovery((current) => ({
          accepted: true,
          detail: current?.detail ?? "",
          routineId: created.id,
          name: created.name || submittedName.trim(),
        }));
    } catch (caught) {
      if (!request.signal.aborted)
        setRecovery({
          accepted,
          routineId: confirmedId,
          name: submittedName.trim(),
          detail: caught instanceof Error ? caught.message : t("error"),
        });
    } finally {
      endAction(request);
    }
  }
  async function act(id: string, path: ":run" | ":pause" | ":resume") {
    const target = rows.find((row) => row.id === id);
    if (!target || (path === ":run" && target.status !== "active")) return;
    const request = beginAction(path, target.name);
    if (!request) return;
    selectRoutine(id);
    setRunId("");
    let accepted = false;
    try {
      const result = await api<{ id?: string; status?: string; runId?: string }>(
        `/api/v1/routines/${id}${path}`,
        { method: "POST", signal: request.signal, body: "{}" },
      );
      if (request.signal.aborted) return;
      if (path === ":run") {
        if (typeof result?.runId !== "string" || !result.runId)
          throw new Error(t("runUnconfirmed"));
        setRunId(result.runId);
      } else if (result?.id !== id || result.status !== (path === ":pause" ? "paused" : "active"))
        throw new Error(t("stateUnconfirmed"));
      accepted = true;
      setNotice(
        path === ":run" ? t("runRequested") : path === ":pause" ? t("paused") : t("enabled"),
      );
      if (!(await refreshAfterAction(request, id)) && !request.signal.aborted)
        setRecovery((current) => ({
          accepted: true,
          detail: current?.detail ?? "",
          routineId: id,
          name: target.name,
        }));
    } catch (caught) {
      if (!request.signal.aborted) {
        setRecovery({
          accepted,
          routineId: id,
          name: target.name,
          detail: caught instanceof Error ? caught.message : t("error"),
        });
        void loadEvents(id);
      }
    } finally {
      endAction(request);
    }
  }
  const mutationBlocked = busy || loading || Boolean(recovery) || Boolean(error);
  const busyLabel =
    action === "create"
      ? t("creating")
      : action === "refresh"
        ? t("refreshing")
        : t(
            action === ":run"
              ? "runningNamed"
              : action === ":pause"
                ? "pausingNamed"
                : "enablingNamed",
            { name: actionTarget },
          );

  return (
    <AppShell>
      <PageHeader body={t("body")} title={t("title")} />
      <ActionStatus busy={busy} busyLabel={busyLabel} notice={notice} />
      {runId ? (
        <Link
          className="mb-4 inline-block text-sm underline"
          href={`/runs/${encodeURIComponent(runId)}`}
        >
          {t("openRun")}
        </Link>
      ) : null}
      <DetailState
        loading={false}
        error={error}
        onRetry={busy ? undefined : () => void refresh()}
      />
      {recovery ? (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-sm"
        >
          {recovery.name ? (
            <p className="mb-2 break-words font-medium">
              {t("requestFor", { name: recovery.name })}
            </p>
          ) : null}
          <p>{t(recovery.accepted ? "acceptedRecovery" : "unconfirmedRecovery")}</p>
          {recovery.detail ? (
            <p className="mt-2 break-words text-[var(--muted-foreground)]">{recovery.detail}</p>
          ) : null}
          <Button
            className="mt-3"
            type="button"
            variant="outline"
            disabled={busy || loading}
            onClick={() => void refresh()}
          >
            {t("refresh")}
          </Button>
        </div>
      ) : null}
      {receipt ? (
        <section
          className="mb-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-sm"
          aria-label={t("credentialsFor", { name: receipt.name })}
        >
          <h2 className="mb-2 font-medium">{t("credentialsFor", { name: receipt.name })}</h2>
          <p>
            {t("secretOnce")} <span className="break-all font-mono">{receipt.secret}</span>
          </p>
          {receipt.url ? (
            <p className="mt-2 break-all font-mono">
              {t("webhookUrl")}: {receipt.url}
            </p>
          ) : null}
          <Button className="mt-3" type="button" variant="outline" onClick={() => setReceipt(null)}>
            {t("hideSecret")}
          </Button>
        </section>
      ) : null}
      {!canUse && !loading && !error ? <p className="text-sm">{t("denied")}</p> : null}
      {!canUse && loading ? <DetailState loading error="" /> : null}
      {canUse ? (
        <ManagementLayout
          title={t("listTitle")}
          formTitle={t("createTitle")}
          form={
            <form
              className="grid gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                void createSchedule();
              }}
            >
              <fieldset className="grid min-w-0 gap-3" disabled={mutationBlocked}>
                <label className="text-sm" htmlFor="schedule-name">
                  {t("name")}
                  <Input
                    className="mt-1"
                    id="schedule-name"
                    onChange={(event) => setName(event.target.value)}
                    required
                    value={name}
                  />
                </label>
                <ReferencePicker
                  label={t("agent")}
                  endpoint="/api/v1/agents"
                  filterRow={isAvailableAgent}
                  emptyMessage={availability("empty")}
                  value={agentId}
                  onChange={setAgentId}
                  required
                  disabled={mutationBlocked}
                  help={`${t("agentHelp")} ${availability("help")}`}
                />
                <label className="text-sm" htmlFor="schedule-instructions">
                  {t("instructions")}
                  <textarea
                    className="mt-1 min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                    id="schedule-instructions"
                    onChange={(event) => setInstructions(event.target.value)}
                    required
                    value={instructions}
                  />
                </label>
                <label className="text-sm" htmlFor="schedule-kind">
                  {t("kind")}
                  <select
                    className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-2 text-sm"
                    id="schedule-kind"
                    onChange={(event) => setKind(event.target.value)}
                    value={kind}
                  >
                    <option value="schedule">{t("schedule")}</option>
                    <option value="webhook">{t("webhook")}</option>
                  </select>
                </label>
                {kind === "schedule" ? (
                  <ScheduleFields
                    cron={cron}
                    timezone={timezone}
                    onCronChange={setCron}
                    onTimezoneChange={setTimezone}
                  />
                ) : null}
                <label className="text-sm" htmlFor="schedule-overlap">
                  {t("overlap")}
                  <select
                    className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-2 text-sm"
                    id="schedule-overlap"
                    onChange={(event) => setOverlap(event.target.value)}
                    value={overlap}
                  >
                    <option value="skip">{t("skip")}</option>
                    <option value="queue">{t("queue")}</option>
                  </select>
                  <span className="mt-1 block text-[var(--muted-foreground)]">
                    {t("overlapHelp")}
                  </span>
                </label>
                <DeliveryFields idPrefix="schedule" onChange={setDelivery} value={delivery} />
                <Button disabled={mutationBlocked || !agentId} type="submit">
                  {action === "create" ? t("creating") : t("create")}
                </Button>
              </fieldset>
            </form>
          }
        >
          {rows.length > 0 ? (
            <div className="mb-4 flex flex-wrap gap-3">
              <Input
                type="search"
                aria-label={t("search")}
                placeholder={t("search")}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <label className="text-sm">
                {t("status")}
                <select
                  className="ml-2 h-9 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                >
                  <option value="">{t("allStatuses")}</option>
                  {statuses.map((value) => (
                    <option key={value} value={value}>
                      {labelStatus(value)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                {t("triggerFilter")}
                <select
                  className="ml-2 h-9 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
                  value={trigger}
                  onChange={(event) => setTrigger(event.target.value)}
                >
                  <option value="">{t("allTriggers")}</option>
                  {triggers.map((value) => (
                    <option key={value} value={value}>
                      {labelTrigger(value)}
                    </option>
                  ))}
                </select>
              </label>
              {query || status || trigger ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setQuery("");
                    setStatus("");
                    setTrigger("");
                  }}
                >
                  {t("clearFilters")}
                </Button>
              ) : null}
            </div>
          ) : null}
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : null}
          {!loading && !error && matching.length === 0 ? (
            <EmptyState title={t(rows.length ? "noMatches" : "empty")} />
          ) : null}
          <ul className="row-list">
            {!loading && !error
              ? pagination.rows.map((row) => (
                  <li className="p-4" key={row.id}>
                    <button
                      className="w-full text-left"
                      aria-pressed={selected === row.id}
                      disabled={busy}
                      onClick={() => {
                        if (!actionRequest.current) selectRoutine(row.id);
                      }}
                      type="button"
                    >
                      <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                        <span className="break-words">{row.name}</span>
                        <Badge tone={statusTone(row.status)}>{labelStatus(row.status ?? "")}</Badge>
                      </p>
                      <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                        {labelTrigger(row.triggerType ?? "")}{" "}
                        {row.triggerSummary ? `· ${row.triggerSummary}` : ""}
                      </p>
                      <span className="mt-1 block text-xs text-[var(--muted-foreground)]">
                        {t("reference", { id: row.id.slice(-8) })}
                      </span>
                    </button>
                    {row.webhookUrl ? (
                      <p className="mt-2 text-sm">
                        {t("webhookUrl")}:{" "}
                        <span className="break-all font-mono">{row.webhookUrl}</span>
                      </p>
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        disabled={mutationBlocked || row.status !== "active"}
                        onClick={() => void act(row.id, ":run")}
                        type="button"
                        variant="outline"
                      >
                        {t("runNow")}
                      </Button>
                      {row.status === "paused" ? (
                        <Button
                          disabled={mutationBlocked}
                          onClick={() => void act(row.id, ":resume")}
                          type="button"
                          variant="outline"
                        >
                          {t("enable")}
                        </Button>
                      ) : (
                        <Button
                          disabled={mutationBlocked}
                          onClick={() => void act(row.id, ":pause")}
                          type="button"
                          variant="outline"
                        >
                          {t("pause")}
                        </Button>
                      )}
                    </div>
                  </li>
                ))
              : null}
          </ul>
          {!loading && !error && rows.length > 0 ? (
            <ListPagination {...pagination} label={t("listTitle")} />
          ) : null}
          {selectedRow ? (
            <section className="mt-8" aria-label={t("history")}>
              <h2 className="mb-2 text-sm font-semibold">
                {t("historyFor", { name: selectedRow.name })}
              </h2>
              <p className="mb-3 text-sm text-[var(--muted-foreground)]">{t("historyHelp")}</p>
              <DetailState
                loading={eventLoading}
                error={eventError}
                onRetry={busy ? undefined : () => void loadEvents(selected)}
              />
              {!eventLoading && !eventError ? (
                <>
                  {events.length > 0 ? (
                    <div className="mb-3 flex flex-wrap gap-3">
                      <Input
                        type="search"
                        aria-label={t("eventSearch")}
                        placeholder={t("eventSearch")}
                        value={eventQuery}
                        onChange={(event) => setEventQuery(event.target.value)}
                      />
                      <label className="text-sm">
                        {t("eventStatus")}
                        <select
                          className="ml-2 h-9 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
                          value={eventStatus}
                          onChange={(event) => setEventStatus(event.target.value)}
                        >
                          <option value="">{t("allStatuses")}</option>
                          {eventStatuses.map((value) => (
                            <option key={value} value={value}>
                              {labelStatus(value)}
                            </option>
                          ))}
                        </select>
                      </label>
                      {eventQuery || eventStatus ? (
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => {
                            setEventQuery("");
                            setEventStatus("");
                          }}
                        >
                          {t("clearFilters")}
                        </Button>
                      ) : null}
                    </div>
                  ) : null}
                  {matchingEvents.length === 0 ? (
                    <p className="text-sm text-[var(--muted-foreground)]">
                      {t(events.length ? "noEventMatches" : "noHistory")}
                    </p>
                  ) : null}
                  <ul className="row-list">
                    {eventPage.rows.map((row) => (
                      <li className="space-y-2 px-3 py-3 text-sm" key={row.id}>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={statusTone(row.status)}>
                            {labelStatus(row.status ?? "")}
                          </Badge>
                          {row.receivedAt ? (
                            <time dateTime={row.receivedAt}>
                              {formatDateTime(row.receivedAt, locale)}
                            </time>
                          ) : null}
                        </div>
                        <p className="break-words text-[var(--muted-foreground)]">
                          {[labelTrigger(row.source ?? ""), row.envelopePreview]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                        {row.runId ? (
                          <Link className="block break-all underline" href={`/runs/${row.runId}`}>
                            {t("openRun")} · {row.runId}
                          </Link>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                  {events.length > 0 ? (
                    <ListPagination {...eventPage} label={t("history")} />
                  ) : null}
                </>
              ) : null}
            </section>
          ) : null}
        </ManagementLayout>
      ) : null}
    </AppShell>
  );
}
