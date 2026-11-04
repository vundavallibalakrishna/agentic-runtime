"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Routine = {
  id: string;
  name: string;
  status?: string;
  triggerType?: string;
  triggerSummary?: string;
  webhookUrl?: string | null;
  concurrencyPolicy?: string;
};

type Agent = { id: string; name: string };
type EventRow = {
  id: string;
  status?: string;
  detail?: { message?: string };
  runId?: string | null;
};
type Created = Routine & { webhook?: { webhookUrl?: string; webhookSecret?: string } };

export function SchedulesScreen() {
  const t = useTranslations("schedules");
  const [rows, setRows] = useState<Routine[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [secret, setSecret] = useState("");
  const [hookUrl, setHookUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [kind, setKind] = useState("schedule");
  const [cron, setCron] = useState("0 9 * * 1");
  const [timezone, setTimezone] = useState("UTC");
  const [overlap, setOverlap] = useState("skip");
  const [agentId, setAgentId] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [page, agentPage] = await Promise.all([
        api<{ items: Routine[] }>("/api/v1/routines"),
        api<{ items: Agent[] }>("/api/v1/agents"),
      ]);
      const list = page.items ?? [];
      setRows(list);
      const agentsFound = agentPage.items ?? [];
      setAgents(agentsFound);
      setAgentId((current) => current || agentsFound[0]?.id || "");
      setSelected((current) => current || list[0]?.id || "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  const loadEvents = useCallback(async (routineId: string) => {
    if (!routineId) {
      setEvents([]);
      return;
    }
    const page = await api<{ items: EventRow[] }>(`/api/v1/routines/${routineId}/events`);
    setEvents(page.items ?? []);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (selected) void loadEvents(selected).catch(() => setEvents([]));
  }, [loadEvents, selected]);

  async function createSchedule() {
    setBusy(true);
    setError("");
    setSecret("");
    try {
      const created = await api<Created>("/api/v1/routines", {
        method: "POST",
        body: JSON.stringify({
          name,
          description: t("body"),
          agentId,
          instructions,
          concurrencyPolicy: overlap === "queue" ? "buffer_one" : "skip",
          trigger:
            kind === "webhook"
              ? { type: "webhook", executeModel: true }
              : { type: "schedule", cron, timezone, executeModel: true },
          delivery: [{ type: "conversation" }],
        }),
      });
      setNotice(t("secretOnce"));
      setSecret(created.webhook?.webhookSecret ?? "");
      setHookUrl(created.webhook?.webhookUrl ?? "");
      setName("");
      await load();
      setSelected(created.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function act(id: string, path: string, body?: object) {
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/routines/${id}${path}`, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      });
      await load();
      await loadEvents(id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  function eventText(row: EventRow) {
    if (row.detail?.message) return row.detail.message;
    if (row.status === "skipped_concurrency") return t("skipped");
    if (row.status === "queued") return t("queued");
    return row.status ?? "";
  }

  return (
    <AppShell>
      <PageHeader body={t("body")} title={t("title")} />
      {error ? (
        <p className="mb-3 text-sm text-[var(--destructive)]" role="alert">
          {error}{" "}
          <Button onClick={() => void load()} type="button" variant="outline">
            {t("retry")}
          </Button>
        </p>
      ) : null}
      {notice && secret ? (
        <p
          className="mb-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-sm"
          role="status"
        >
          {notice} <span className="font-mono">{secret}</span>
          {hookUrl ? (
            <span className="mt-2 block font-mono">
              {t("webhookUrl")}: {hookUrl}
            </span>
          ) : null}
        </p>
      ) : null}
      <form
        className="mb-6 grid gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
        onSubmit={(event) => {
          event.preventDefault();
          void createSchedule();
        }}
      >
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
        <label className="text-sm" htmlFor="schedule-agent">
          {t("agent")}
          <select
            className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-2 text-sm"
            id="schedule-agent"
            onChange={(event) => setAgentId(event.target.value)}
            value={agentId}
          >
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        </label>
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
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm" htmlFor="schedule-cron">
              {t("cron")}
              <Input
                className="mt-1"
                id="schedule-cron"
                onChange={(event) => setCron(event.target.value)}
                value={cron}
              />
            </label>
            <label className="text-sm" htmlFor="schedule-zone">
              {t("timezone")}
              <Input
                className="mt-1"
                id="schedule-zone"
                onChange={(event) => setTimezone(event.target.value)}
                value={timezone}
              />
              <span className="mt-1 block text-[var(--muted-foreground)]">{t("timezoneHelp")}</span>
            </label>
          </div>
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
          <span className="mt-1 block text-[var(--muted-foreground)]">{t("overlapHelp")}</span>
        </label>
        <Button disabled={busy || !agentId} type="submit">
          {busy ? t("creating") : t("create")}
        </Button>
      </form>
      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : null}
      {!loading && !error && rows.length === 0 ? <EmptyState title={t("empty")} /> : null}
      <ul className="space-y-2">
        {rows.map((row) => (
          <li
            className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
            key={row.id}
          >
            <button className="text-left" onClick={() => setSelected(row.id)} type="button">
              <p className="text-sm font-medium">
                {row.name} · {row.status}
              </p>
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                {row.triggerType} {row.triggerSummary ? `· ${row.triggerSummary}` : ""}
              </p>
            </button>
            {row.webhookUrl ? (
              <p className="mt-2 text-sm">
                {t("webhookUrl")}: <span className="font-mono">{row.webhookUrl}</span>
              </p>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                disabled={busy}
                onClick={() => void act(row.id, ":tick", { force: true })}
                type="button"
                variant="outline"
              >
                {t("runNow")}
              </Button>
              {row.status === "paused" ? (
                <Button
                  disabled={busy}
                  onClick={() => void act(row.id, ":resume")}
                  type="button"
                  variant="outline"
                >
                  {t("enable")}
                </Button>
              ) : (
                <Button
                  disabled={busy}
                  onClick={() => void act(row.id, ":pause")}
                  type="button"
                  variant="outline"
                >
                  {t("pause")}
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>
      {selected ? (
        <section className="mt-6">
          <h2 className="mb-2 text-sm font-semibold">{t("history")}</h2>
          {events.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">{t("noHistory")}</p>
          ) : null}
          <ul className="space-y-2">
            {events.map((row) => (
              <li
                className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
                key={row.id}
              >
                {eventText(row)}
                {row.runId ? ` · ${row.runId}` : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </AppShell>
  );
}
