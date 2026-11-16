"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { Facts } from "@/components/common/facts";
import { durationLabel, liveStatuses } from "@/components/runs/format";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Run = {
  id: string;
  status?: string;
  agentId?: string;
  answeredModel?: string;
  startedAt?: string | null;
  endedAt?: string | null;
};
type Named = { id?: unknown; name?: unknown };
type Step = { id?: string; kind?: string; detail?: { agent?: string } };
type Tool = { id?: string; qualifiedName?: string; status?: string };

/**
 * The facts of the latest run beside the conversation: who answered, how long it took and
 * which tools it called. `settled` changes when the reply finishes, so the panel reads again.
 * The run names its agent by id; `agents` is the list the chat already holds, for the name.
 */
export function RunDetails({
  runId,
  settled,
  agents,
}: {
  runId: string;
  settled: boolean;
  agents: Named[];
}) {
  const t = useTranslations("chat");
  const [run, setRun] = useState<Run | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [body, stepPage, toolPage] = await Promise.all([
        api<Run>(`/api/v1/runs/${runId}`),
        api<{ items: Step[] }>(`/api/v1/runs/${runId}/steps`),
        api<{ items: Tool[] }>(`/api/v1/runs/${runId}/tool-calls`),
      ]);
      setRun(body);
      setSteps(stepPage.items ?? []);
      setTools(toolPage.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("runDetailsError"));
    }
  }, [runId, t]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: a finished reply is a reason to read again
  useEffect(() => {
    void load();
  }, [load, settled]);

  // While the reply streams the chat already shows progress, so the panel does not poll. It
  // reads again when the reply ends, and then slowly only if the run still waits on a person.
  const waiting = settled && liveStatuses.includes(run?.status || "");
  useEffect(() => {
    if (!waiting) return;
    const timer = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(timer);
  }, [waiting, load]);

  const current = run?.id === runId ? run : null;
  const agent = agents.find((item) => item.id === current?.agentId);

  return (
    <aside
      aria-label={t("runDetails")}
      className="max-h-[55%] shrink-0 overflow-y-auto border-b border-l border-[var(--border)] bg-[var(--card)] px-4 py-4"
    >
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--muted-foreground)]">
        {t("runDetails")}
      </h2>
      {error ? (
        <div role="alert">
          <p className="text-sm text-[var(--destructive)]">{error}</p>
          <Button className="mt-3" onClick={() => void load()} type="button" variant="outline">
            {t("retry")}
          </Button>
        </div>
      ) : null}
      {!error && !current ? (
        <div aria-busy="true" className="space-y-3">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="h-5 w-3/4" />
        </div>
      ) : null}
      {!error && current ? (
        <>
          <Facts
            align="end"
            items={[
              {
                label: t("runStatus"),
                value: <Badge tone={statusTone(current.status)}>{current.status}</Badge>,
              },
              {
                label: t("agent"),
                value: (
                  <span className="block truncate font-medium">
                    {agent?.name ? String(agent.name) : "—"}
                  </span>
                ),
              },
              {
                label: t("runModel"),
                value: <span className="block truncate">{current.answeredModel || "—"}</span>,
              },
              {
                label: t("runDuration"),
                value: <span className="tabular-nums">{durationLabel(current) || "—"}</span>,
              },
              { label: t("runSteps"), value: <span className="tabular-nums">{steps.length}</span> },
              {
                label: t("runToolCalls"),
                value: <span className="tabular-nums">{tools.length}</span>,
              },
            ]}
          />
          <h3 className="panel-title mb-2 mt-5">{t("runToolCalls")}</h3>
          {tools.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">{t("runNoTools")}</p>
          ) : (
            <ul className="space-y-2">
              {tools.map((tool, index) => (
                <li
                  className="flex items-center justify-between gap-2 text-sm"
                  key={tool.id ?? index}
                >
                  <span className="min-w-0 truncate font-mono text-xs">{tool.qualifiedName}</span>
                  <Badge tone={statusTone(tool.status)}>{tool.status}</Badge>
                </li>
              ))}
            </ul>
          )}
          <Button asChild className="mt-5" variant="outline">
            <Link href={`/runs/${runId}`}>{t("viewTrace")}</Link>
          </Button>
        </>
      ) : null}
    </aside>
  );
}
