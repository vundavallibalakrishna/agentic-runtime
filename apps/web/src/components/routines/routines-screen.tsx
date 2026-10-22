"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Routine = {
  id: string;
  name: string;
  description?: string;
  status?: string;
  triggerType?: string;
  triggerSummary?: string;
  nextRunAt?: string | null;
  consecutiveFailures?: number;
};

type Agent = { id: string; name: string; slug?: string };
type Preview = { valid: boolean; description: string; next: string[] };

export function RoutinesScreen() {
  const t = useTranslations("routines");
  const [rows, setRows] = useState<Routine[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [cron, setCron] = useState("0 9 * * 1");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [agentId, setAgentId] = useState("");
  const [preApproved, setPreApproved] = useState(true);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [page, agentPage] = await Promise.all([
        api<{ items: Routine[] }>("/api/v1/routines"),
        api<{ items: Agent[] }>("/api/v1/agents"),
      ]);
      setRows(page.items ?? []);
      const list = agentPage.items ?? [];
      setAgents(list);
      setAgentId((current) => current || list[0]?.id || "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function showPreview() {
    setError("");
    try {
      const found = await api<Preview>("/api/v1/routines:preview-schedule", {
        method: "POST",
        body: JSON.stringify({ cron, timezone }),
      });
      setPreview(found);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  async function createRoutine() {
    setBusy(true);
    setError("");
    try {
      const created = await api<Routine>("/api/v1/routines", {
        method: "POST",
        body: JSON.stringify({
          name,
          description: t("seedDescription"),
          agentId,
          instructions,
          trigger: { type: "schedule", cron, timezone },
          delivery: [
            { type: "conversation" },
            { type: "slack", channel: "#platform", preApproved },
          ],
        }),
      });
      window.location.assign(`/routines/${created.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
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
      <section className="mb-6 rounded-xl border border-[var(--border)] p-4">
        <h2 className="text-sm font-medium">{t("create")}</h2>
        <label className="mt-3 block text-sm" htmlFor="routine-name">
          {t("name")}
        </label>
        <Input
          className="mt-1 max-w-md"
          id="routine-name"
          onChange={(event) => setName(event.target.value)}
          value={name}
        />
        <label className="mt-3 block text-sm" htmlFor="routine-agent">
          {t("agent")}
        </label>
        <select
          className="mt-1 max-w-md rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 text-sm"
          id="routine-agent"
          onChange={(event) => setAgentId(event.target.value)}
          value={agentId}
        >
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name}
            </option>
          ))}
        </select>
        <label className="mt-3 block text-sm" htmlFor="routine-instructions">
          {t("instructions")}
        </label>
        <textarea
          className="mt-1 min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
          id="routine-instructions"
          onChange={(event) => setInstructions(event.target.value)}
          value={instructions}
        />
        <div className="mt-3 flex flex-wrap gap-3">
          <div>
            <label className="block text-sm" htmlFor="routine-cron">
              {t("cron")}
            </label>
            <Input
              className="mt-1 w-40"
              id="routine-cron"
              onChange={(event) => setCron(event.target.value)}
              value={cron}
            />
          </div>
          <div>
            <label className="block text-sm" htmlFor="routine-timezone">
              {t("timezone")}
            </label>
            <Input
              className="mt-1 w-48"
              id="routine-timezone"
              onChange={(event) => setTimezone(event.target.value)}
              value={timezone}
            />
          </div>
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm" htmlFor="routine-preapprove">
          <input
            checked={preApproved}
            id="routine-preapprove"
            onChange={(event) => setPreApproved(event.target.checked)}
            type="checkbox"
          />
          {t("preApproved")}
        </label>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button onClick={() => void showPreview()} type="button" variant="outline">
            {t("preview")}
          </Button>
          <Button
            disabled={busy || !name.trim() || !instructions.trim() || !agentId}
            onClick={() => void createRoutine()}
            type="button"
          >
            {t("create")}
          </Button>
        </div>
        {preview ? (
          <div className="mt-3 text-sm text-[var(--muted-foreground)]">
            <p>{preview.valid ? preview.description : t("invalidSchedule")}</p>
            <ul className="mt-1 list-disc pl-5">
              {preview.next.map((stamp) => (
                <li key={stamp}>{stamp}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>
      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : null}
      {!loading && rows.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
      ) : null}
      <ul className="space-y-2">
        {rows.map((routine) => (
          <li className="rounded-xl border border-[var(--border)] p-3" key={routine.id}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-medium">{routine.name}</p>
                <p className="text-sm text-[var(--muted-foreground)]">
                  {routine.triggerSummary || routine.triggerType}
                </p>
                <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                  {routine.status}
                  {routine.consecutiveFailures ? ` · ${routine.consecutiveFailures}` : ""}
                </p>
              </div>
              <Button asChild variant="outline">
                <Link href={`/routines/${routine.id}`}>{t("open")}</Link>
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
