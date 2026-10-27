"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, BackButton, DetailState } from "@/components/common/detail-state";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
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
        actions={<BackButton href="/routines">{t("back")}</BackButton>}
      />
      <DetailState loading={loading} error={error} onRetry={() => void load()} />
      <ActionStatus busy={busy} notice={notice} />
      {runId ? (
        <Button asChild variant="outline" className="mb-5">
          <Link href={`/runs/${runId}`}>{detail("openRun")}</Link>
        </Button>
      ) : null}
      {routine ? (
        <fieldset disabled={busy} className="detail-panel">
          <p className="text-sm text-[var(--muted-foreground)]">{routine.triggerSummary}</p>
          <p className="mt-2 text-sm">
            {routine.status}
            {routine.pausedReason ? ` · ${routine.pausedReason}` : ""}
          </p>
          <p className="mt-3 whitespace-pre-wrap text-sm">{routine.instructions}</p>
          {routine.webhookUrl ? (
            <p className="mt-3 break-all text-sm text-[var(--muted-foreground)]">
              {routine.webhookUrl}
            </p>
          ) : null}
          {secret ? (
            <p className="mt-2 break-all text-sm" data-testid="webhook-secret">
              {secret}
            </p>
          ) : null}
          {routine.nextFires && routine.nextFires.length > 0 ? (
            <ul className="mt-3 list-disc pl-5 text-sm text-[var(--muted-foreground)]">
              {routine.nextFires.map((stamp) => (
                <li key={stamp}>{new Date(stamp).toLocaleString()}</li>
              ))}
            </ul>
          ) : null}
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
      ) : null}
      {!loading && routine ? (
        <section className="detail-panel mt-6">
          <h2 className="text-sm font-medium">{t("events")}</h2>
          {events.length === 0 ? (
            <EmptyState title={t("noEvents")} />
          ) : (
            <ul className="mt-2 space-y-2">
              {events.map((event) => (
                <li className="rounded-xl border border-[var(--border)] p-3 text-sm" key={event.id}>
                  {event.source} · {event.status}
                  {event.runId ? (
                    <Link className="ml-3 underline" href={`/runs/${event.runId}`}>
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
