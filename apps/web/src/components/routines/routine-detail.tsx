"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, BackButton, DetailState } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { DeliveryList, type DeliveryTarget } from "@/components/routines/delivery-fields";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

type Routine = {
  id: string;
  name: string;
  description?: string;
  status?: string;
  pausedReason?: string | null;
  instructions?: string;
  triggerSummary?: string;
  webhookUrl?: string | null;
  nextFires?: string[];
  consecutiveFailures?: number;
  delivery?: DeliveryTarget[];
};

type RoutineEvent = {
  id: string;
  source?: string;
  status?: string;
  receivedAt?: string;
  runId?: string | null;
};

export function RoutineDetail({ routineId }: { routineId: string }) {
  return <RoutineView key={routineId} routineId={routineId} />;
}

function RoutineView({ routineId }: { routineId: string }) {
  const t = useTranslations("routines");
  const activity = useTranslations("schedules");
  const locale = useLocale();
  const detail = useTranslations("detail");
  const deliveryText = useTranslations("delivery");
  const searchId = useId();
  const loadRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const [runId, setRunId] = useState("");
  const [routine, setRoutine] = useState<Routine | null>(null);
  const [events, setEvents] = useState<RoutineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [secret, setSecret] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const statuses = useMemo(
    () => [...new Set(events.flatMap((event) => (event.status ? [event.status] : [])))].sort(),
    [events],
  );
  const matchingEvents = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return events.filter(
      (event) =>
        (!status || event.status === status) &&
        (!term ||
          [event.id, event.source, event.status, event.runId, event.receivedAt].some((value) =>
            value?.toLocaleLowerCase().includes(term),
          )),
    );
  }, [events, query, status]);
  const eventPage = usePagedRows(matchingEvents, `${routineId}::${query}::${status}`);
  const labelStatus = (value: string) =>
    activity.has(`statuses.${value}`) ? activity(`statuses.${value}`) : value;

  const load = useCallback(async () => {
    loadRequest.current?.abort();
    const request = new AbortController();
    loadRequest.current = request;
    setRoutine(null);
    setLoading(true);
    setError("");
    try {
      const [detail, history] = await Promise.all([
        api<Routine>(`/api/v1/routines/${routineId}`, { signal: request.signal }),
        api<{ items: RoutineEvent[] }>(`/api/v1/routines/${routineId}/events`, {
          signal: request.signal,
        }),
      ]);
      if (request.signal.aborted) return;
      setRoutine(detail);
      setEvents(history.items ?? []);
    } catch (caught) {
      if (!request.signal.aborted) setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      if (loadRequest.current === request) {
        loadRequest.current = null;
        setLoading(false);
      }
    }
  }, [routineId, t]);

  useEffect(() => {
    void load();
    return () => {
      loadRequest.current?.abort();
      actionRequest.current?.abort();
    };
  }, [load]);

  async function act(path: string, label: string) {
    if (actionRequest.current) return;
    const request = new AbortController();
    actionRequest.current = request;
    setError("");
    setBusy(true);
    setRunId("");
    setNotice("");
    try {
      const result = await api<Record<string, string>>(`/api/v1/routines/${routineId}${path}`, {
        method: "POST",
        body: "{}",
        signal: request.signal,
      });
      if (request.signal.aborted) return;
      if (result.webhookSecret) {
        setSecret(result.webhookSecret);
      }
      if (result.runId) {
        setRunId(result.runId);
        setNotice(t("ran"));
      } else {
        setNotice(label);
      }
      await load();
    } catch (caught) {
      if (!request.signal.aborted) setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setBusy(false);
      }
    }
  }

  return (
    <AppShell>
      <PageHeader
        body={t("detailBody")}
        title={routine?.name || t("title")}
        actions={
          <>
            {routine?.status ? (
              <Badge tone={statusTone(routine.status)}>{routine.status}</Badge>
            ) : null}
            <BackButton href="/routines">{t("back")}</BackButton>
          </>
        }
      />
      <DetailState loading={loading} error={error} onRetry={() => void load()} />
      <ActionStatus busy={busy} notice={notice} />
      {runId ? (
        <Button asChild variant="outline" className="mb-5">
          <Link href={`/runs/${runId}`}>{detail("openRun")}</Link>
        </Button>
      ) : null}
      {routine ? (
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <fieldset disabled={busy} className="detail-panel">
            <h2 className="panel-title">{t("instructions")}</h2>
            <p className="mt-3 whitespace-pre-wrap text-sm">{routine.instructions}</p>
            <div className="mt-6 flex flex-wrap gap-2 border-t border-[var(--border)] pt-5">
              <Button onClick={() => void act(":run", t("ran"))} type="button">
                {t("runNow")}
              </Button>
              <Button
                onClick={() =>
                  void act(
                    routine.status === "paused" ? ":resume" : ":pause",
                    routine.status === "paused" ? t("resumed") : t("paused"),
                  )
                }
                type="button"
                variant="outline"
              >
                {routine.status === "paused" ? t("resume") : t("pause")}
              </Button>
              {routine.webhookUrl ? (
                <Button
                  onClick={() => void act(":rotate-webhook-secret", t("rotated"))}
                  type="button"
                  variant="outline"
                >
                  {t("rotate")}
                </Button>
              ) : null}
            </div>
          </fieldset>
          <section className="detail-panel">
            <Facts
              items={[
                { label: t("trigger"), value: routine.triggerSummary },
                {
                  label: t("status"),
                  value: routine.pausedReason
                    ? `${routine.status} · ${routine.pausedReason}`
                    : null,
                },
                {
                  label: deliveryText("label"),
                  value:
                    routine.delivery && routine.delivery.length > 0 ? (
                      <DeliveryList targets={routine.delivery} />
                    ) : null,
                },
                {
                  label: t("webhook"),
                  value: routine.webhookUrl ? (
                    <span className="break-all font-mono text-xs">{routine.webhookUrl}</span>
                  ) : null,
                },
                {
                  label: t("webhookSecret"),
                  value: secret ? (
                    <span className="break-all font-mono text-xs" data-testid="webhook-secret">
                      {secret}
                    </span>
                  ) : null,
                },
                {
                  label: detail("upcoming"),
                  value:
                    routine.nextFires && routine.nextFires.length > 0 ? (
                      <ul className="space-y-1 tabular-nums">
                        {routine.nextFires.map((stamp) => (
                          <li key={stamp}>
                            <time dateTime={stamp}>{formatDateTime(stamp, locale)}</time>
                          </li>
                        ))}
                      </ul>
                    ) : null,
                },
              ]}
            />
          </section>
        </div>
      ) : null}
      {!loading && routine ? (
        <section className="mt-8" aria-label={t("events")}>
          <h2 className="panel-title mb-3">{t("events")}</h2>
          {events.length === 0 ? (
            <EmptyState title={t("noEvents")} />
          ) : (
            <>
              <div className="mb-4 grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
                <label htmlFor={searchId} className="min-w-0 text-sm">
                  <span className="mb-1 block">{activity("eventSearch")}</span>
                  <Input
                    id={searchId}
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                  />
                </label>
                <label className="min-w-0 text-sm">
                  <span className="mb-1 block">{activity("eventStatus")}</span>
                  <select
                    className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
                    value={status}
                    onChange={(event) => setStatus(event.target.value)}
                  >
                    <option value="">{activity("allStatuses")}</option>
                    {statuses.map((value) => (
                      <option key={value} value={value}>
                        {labelStatus(value)}
                      </option>
                    ))}
                  </select>
                </label>
                {query || status ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setQuery("");
                      setStatus("");
                    }}
                  >
                    {activity("clearFilters")}
                  </Button>
                ) : null}
              </div>
              {matchingEvents.length === 0 ? (
                <EmptyState title={activity("noEventMatches")} />
              ) : null}
              <ul className="row-list">
                {eventPage.rows.map((event) => (
                  <li
                    className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-sm"
                    key={event.id}
                  >
                    <span className="max-w-full break-all font-medium">{event.source}</span>
                    <Badge tone={statusTone(event.status)}>{event.status}</Badge>
                    {event.receivedAt ? (
                      <span className="tabular-nums text-[var(--muted-foreground)]">
                        <time dateTime={event.receivedAt}>
                          {formatDateTime(event.receivedAt, locale)}
                        </time>
                      </span>
                    ) : null}
                    {event.runId ? (
                      <Link className="ml-auto underline" href={`/runs/${event.runId}`}>
                        {detail("openRun")}
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ul>
              <ListPagination {...eventPage} label={t("events")} />
            </>
          )}
        </section>
      ) : null}
    </AppShell>
  );
}
