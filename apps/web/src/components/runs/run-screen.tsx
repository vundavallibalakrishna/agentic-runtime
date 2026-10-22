"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

import { RunTraceGraph } from "./run-trace-graph";
import { buildTrace } from "./trace";

type Run = {
  id: string;
  status?: string;
  trigger?: string;
  resultSummary?: string;
  agentName?: string;
  agentSlug?: string;
};

type Step = { id?: string; kind?: string; detail?: { agent?: string } };
type Tool = { id?: string; qualifiedName?: string; status?: string };

export function RunScreen() {
  const t = useTranslations("runs");
  const params = useParams<{ runId: string }>();
  const runId = params.runId;
  const [run, setRun] = useState<Run | null>(null);
  const [children, setChildren] = useState<Run[]>([]);
  const [steps, setSteps] = useState<Step[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [body, childPage, stepPage, toolPage] = await Promise.all([
        api<Run>(`/api/v1/runs/${runId}`),
        api<{ items: Run[] }>(`/api/v1/runs/${runId}/children`),
        api<{ items: Step[] }>(`/api/v1/runs/${runId}/steps`),
        api<{ items: Tool[] }>(`/api/v1/runs/${runId}/tool-calls`),
      ]);
      setRun(body);
      setChildren(childPage.items ?? []);
      setSteps(stepPage.items ?? []);
      setTools(toolPage.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [runId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const graph = run ? buildTrace({ run, children, steps, tools }) : { nodes: [], edges: [] };

  return (
    <AppShell>
      <PageHeader body={run?.resultSummary || t("traceBody")} title={t("traceTitle")} />
      <Button asChild className="mb-4" variant="outline">
        <Link href="/runs">{t("back")}</Link>
      </Button>
      {error ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? <Skeleton className="h-80 w-full" /> : null}
      {!loading && run ? (
        <section aria-label={t("trace")}>
          <p className="mb-3 text-sm text-[var(--muted-foreground)]">
            {run.trigger} · {run.status}
            {children.length ? ` · ${t("children", { count: children.length })}` : ""}
          </p>
          {graph.nodes.length === 0 ? (
            <p className="text-sm">{t("emptyTrace")}</p>
          ) : (
            <RunTraceGraph edges={graph.edges} nodes={graph.nodes} />
          )}
          <ul className="mt-4 space-y-2">
            {children.map((child) => (
              <li className="text-sm" key={child.id}>
                <Link className="underline" href={`/runs/${child.id}`}>
                  {child.agentName || child.agentSlug || t("child")} · {child.status}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </AppShell>
  );
}
