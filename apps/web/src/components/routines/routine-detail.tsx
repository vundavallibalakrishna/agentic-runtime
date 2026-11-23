"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, BackButton, DetailState } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { DeliveryList, type DeliveryTarget } from "@/components/routines/delivery-fields";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

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
  const t = useTranslations("routines");
  const detail = useTranslations("detail");
  const deliveryText = useTranslations("delivery");
  const [busy, setBusy] = useState(false);
  const [runId, setRunId] = useState("");
  const [routine, setRoutine] = useState<Routine | null>(null);
  const [events, setEvents] = useState<RoutineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [secret, setSecret] = useState("");

  const load = useCallback(async () => {
    setRoutine(null);
    setLoading(true);
    setError("");
    try {
      const [detail, history] = await Promise.all([
        api<Routine>(`/api/v1/routines/${routineId}`),
        api<{ items: RoutineEvent[] }>(`/api/v1/routines/${routineId}/events`),
      ]);
      setRoutine(detail);
      setEvents(history.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [routineId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(path: string, label: string) {
    setError("");
    if (busy) return;
    setBusy(true);
    setRunId("");
    setNotice("");
    try {
      const result = await api<Record<string, string>>(`/api/v1/routines/${routineId}${path}`, {
        method: "POST",
        body: "{}",
      });
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
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
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
                          <li key={stamp}>{new Date(stamp).toLocaleString()}</li>
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
        <section className="mt-8">
          <h2 className="panel-title mb-3">{t("events")}</h2>
          {events.length === 0 ? (
            <EmptyState title={t("noEvents")} />
          ) : (
            <ul className="row-list">
              {events.map((event) => (
                <li
                  className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-sm"
                  key={event.id}
                >
                  <span className="font-medium">{event.source}</span>
                  <Badge tone={statusTone(event.status)}>{event.status}</Badge>
                  {event.receivedAt ? (
                    <span className="tabular-nums text-[var(--muted-foreground)]">
                      {new Date(event.receivedAt).toLocaleString()}
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
          )}
        </section>
      ) : null}
    </AppShell>
  );
}
