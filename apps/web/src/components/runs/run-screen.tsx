"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { BackButton, DetailState } from "@/components/common/detail-state";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
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
  const detail = useTranslations("detail");
  const params = useParams<{ runId: string }>();
  const runId = params.runId;
  const [run, setRun] = useState<Run | null>(null);
  const [children, setChildren] = useState<Run[]>([]);
  const [steps, setSteps] = useState<Step[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setRun(null);
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
      <PageHeader
        body={t("traceBody")}
        title={t("traceTitle")}
        actions={<BackButton href="/runs">{t("back")}</BackButton>}
      />
      <DetailState loading={loading} error={error} onRetry={() => void load()} />
      {!loading && run ? (
        <section aria-label={t("trace")} className="min-w-0">
          {run.resultSummary ? (
            <div className="detail-panel mb-6">
              <h2 className="mb-3 text-sm font-semibold">{detail("summary")}</h2>
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{run.resultSummary}</p>
            </div>
          ) : null}
          <p className="mb-3 text-sm text-[var(--muted-foreground)]">
            {run.trigger} · {run.status}
            {children.length ? ` · ${t("children", { count: children.length })}` : ""}
          </p>
          {graph.nodes.length === 0 ? (
            <p className="text-sm">{t("emptyTrace")}</p>
          ) : (
            <RunTraceGraph edges={graph.edges} nodes={graph.nodes} />
          )}
          <section className="detail-panel mt-6">
            <h2 className="mb-4 text-sm font-semibold">{detail("activity")}</h2>
            {steps.length === 0 && tools.length === 0 ? (
              <EmptyState title={detail("noActivity")} />
            ) : (
              <ol className="divide-y divide-[var(--border)]">
                {steps.map((step, index) => (
                  <li className="py-3 text-sm" key={step.id ?? index}>
                    {step.kind}
                    {step.detail?.agent ? ` · ${step.detail.agent}` : ""}
                  </li>
                ))}
                {tools.map((tool, index) => (
                  <li className="py-3 text-sm" key={tool.id ?? index}>
                    {tool.qualifiedName} · {tool.status}
                  </li>
                ))}
              </ol>
            )}
          </section>
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
