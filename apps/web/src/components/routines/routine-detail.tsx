"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
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
  const [routine, setRoutine] = useState<Routine | null>(null);
  const [events, setEvents] = useState<RoutineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [secret, setSecret] = useState("");

  const load = useCallback(async () => {
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
        setNotice(t("ran"));
      } else {
        setNotice(label);
      }
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  return (
    <AppShell>
      <PageHeader body={t("detailBody")} title={routine?.name || t("title")} />
      <Button asChild className="mb-4" variant="outline">
        <Link href="/routines">{t("back")}</Link>
      </Button>
      {error ? (
        <p className="mb-3 text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? <p className="mb-3 text-sm text-[var(--muted-foreground)]">{notice}</p> : null}
      {loading ? <Skeleton className="h-32 w-full" /> : null}
      {routine ? (
        <section className="rounded-xl border border-[var(--border)] p-4">
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
                <li key={stamp}>{stamp}</li>
              ))}
            </ul>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button onClick={() => void act(":run", t("ran"))} type="button">
              {t("runNow")}
            </Button>
            <Button onClick={() => void act(":pause", t("paused"))} type="button" variant="outline">
              {t("pause")}
            </Button>
            <Button
              onClick={() => void act(":resume", t("resumed"))}
              type="button"
              variant="outline"
            >
              {t("resume")}
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
        </section>
      ) : null}
      <section className="mt-6">
        <h2 className="text-sm font-medium">{t("events")}</h2>
        {events.length === 0 ? (
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">{t("noEvents")}</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {events.map((event) => (
              <li className="rounded-xl border border-[var(--border)] p-3 text-sm" key={event.id}>
                {event.source} · {event.status}
                {event.runId ? ` · ${event.runId}` : ""}
              </li>
            ))}
          </ul>
        )}
      </section>
    </AppShell>
  );
}
