"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ToolCallCard } from "@/components/chat/tool-call-card";
import { ActionStatus, BackButton, DetailState } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Meter } from "@/components/usage/meter";
import { api } from "@/lib/api";
import { formatCount } from "@/lib/format";

import { durationLabel, liveStatuses } from "./format";
import { RunEvents } from "./run-events";
import { RunTraceGraph } from "./run-trace-graph";
import { buildTrace } from "./trace";
import { type Run, type Step, type Tool, useRunInspection } from "./use-run-inspection";

type Activity =
  | { key: string; label: string; source: "step"; step: Step }
  | { key: string; label: string; source: "tool"; tool: Tool };
const selectClass = "h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm";

export function RunScreen() {
  const { runId } = useParams<{ runId: string }>();
  return <RunDetail key={runId} runId={runId} />;
}

function RunDetail({ runId }: { runId: string }) {
  const t = useTranslations("runs");
  const detail = useTranslations("detail");
  const {
    run,
    setRun,
    session,
    children,
    steps,
    tools,
    loading,
    error,
    sectionErrors,
    refresh,
    pause,
  } = useRunInspection(runId, { includeChildren: true, includeIdentity: true });
  const canCancel = Boolean(
    run?.userId && run.userId === session?.user?.id && session?.permissions?.includes("chat:use"),
  );
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [childQuery, setChildQuery] = useState("");
  const [childStatus, setChildStatus] = useState("");
  const [tab, setTab] = useState("activity");
  const mounted = useRef(true);
  const mutation = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  async function cancel() {
    if (mutation.current || !canCancel || !run || !liveStatuses.includes(run.status ?? "")) return;
    mutation.current = true;
    pause();
    setBusy(true);
    setActionError("");
    setNotice("");
    try {
      const saved = await api<Run>(`/api/v1/runs/${run.id}:cancel`, { method: "POST" });
      if (!mounted.current) return;
      setRun(saved);
      setNotice(t("cancelRecorded"));
    } catch (caught) {
      if (mounted.current) setActionError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      mutation.current = false;
      if (mounted.current) {
        setBusy(false);
        refresh();
      }
    }
  }
  const activity = useMemo<Activity[]>(
    () => [
      ...steps.map(
        (step, index): Activity => ({
          key: `step-${step.id ?? index}`,
          label: `${step.kind || t("stepDetail")}${step.detail?.agent ? ` · ${step.detail.agent}` : ""}`,
          source: "step",
          step,
        }),
      ),
      ...tools.map(
        (tool, index): Activity => ({
          key: `tool-${tool.id ?? index}`,
          label: tool.qualifiedName || t("toolsLabel"),
          source: "tool",
          tool,
        }),
      ),
    ],
    [steps, tools, t],
  );
  const matching = useMemo(
    () =>
      activity.filter(
        (row) =>
          (!kind || row.source === kind) &&
          [row.key, row.label, row.source === "step" ? row.step.kind : row.tool.status].some(
            (value) => value?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
          ),
      ),
    [activity, kind, query],
  );
  const pagination = usePagedRows(matching, `${query}::${kind}`);
  const filteredChildren = useMemo(
    () =>
      children.filter(
        (child) =>
          (!childStatus || child.status === childStatus) &&
          [child.id, child.agentName, child.agentSlug, child.status].some((value) =>
            value?.toLocaleLowerCase().includes(childQuery.trim().toLocaleLowerCase()),
          ),
      ),
    [children, childQuery, childStatus],
  );
  const childPagination = usePagedRows(filteredChildren, `${childQuery}::${childStatus}`);
  const graph = useMemo(
    () =>
      run
        ? buildTrace({
            run,
            children: childPagination.rows,
            steps: pagination.rows.flatMap((row) => (row.source === "step" ? [row.step] : [])),
            tools: pagination.rows.flatMap((row) => (row.source === "tool" ? [row.tool] : [])),
          })
        : { nodes: [], edges: [] },
    [run, childPagination.rows, pagination.rows],
  );
  const retry = refresh;
  const statusLabel = (value: string) =>
    t.has(`statuses.${value}`) ? t(`statuses.${value}`) : value;
  return (
    <AppShell>
      <PageHeader
        title={t("traceTitle")}
        body={t("traceBody")}
        actions={<BackButton href="/runs">{t("back")}</BackButton>}
      />
      <DetailState loading={loading && !run} error={error} onRetry={retry} />
      <ActionStatus busy={busy} notice={notice} />
      {run ? (
        <section aria-label={t("trace")} className="min-w-0 space-y-6">
          <section className="detail-panel">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <Badge tone={statusTone(run.status)}>{statusLabel(run.status ?? "")}</Badge>
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <Button variant="outline" disabled={loading || busy} onClick={retry}>
                  {t("refresh")}
                </Button>
                {run.traceUrl ? (
                  <a className="underline" href={run.traceUrl}>
                    {t("traceLink")}
                  </a>
                ) : null}
                {run.langfuseUrl ? (
                  <a className="underline" href={run.langfuseUrl}>
                    {t("langfuseLink")}
                  </a>
                ) : null}
                {canCancel && liveStatuses.includes(run.status ?? "") ? (
                  <Button variant="outline" disabled={busy} onClick={() => void cancel()}>
                    {busy ? t("cancelling") : t("cancel")}
                  </Button>
                ) : null}
              </div>
            </div>
            <Facts
              items={[
                { label: t("reference"), value: run.id },
                { label: t("agent"), value: run.agentName || run.agentSlug },
                { label: t("trigger"), value: run.trigger },
                { label: t("duration"), value: durationLabel(run) },
                {
                  label: t("costMicros"),
                  value: run.usage?.costMicros != null ? formatCount(run.usage.costMicros) : null,
                },
                {
                  label: t("stepsLabel"),
                  value: run.usage?.steps != null ? formatCount(run.usage.steps) : null,
                },
              ]}
            />
            {run.usage?.steps != null && run.budget?.maxSteps != null && run.budget.maxSteps > 0 ? (
              <div className="mt-4">
                <p className="mb-2 text-sm">
                  {t("stepsBudget", {
                    used: formatCount(run.usage.steps),
                    limit: formatCount(run.budget.maxSteps),
                  })}
                </p>
                <Meter used={run.usage.steps} limit={run.budget.maxSteps} label={t("stepsLabel")} />
              </div>
            ) : null}
            {run.error?.message ? (
              <p className="mt-4 break-words text-sm text-[var(--destructive)]">
                {run.error.message}
              </p>
            ) : null}
            {actionError ? (
              <p role="alert" className="mt-4 break-words text-sm text-[var(--destructive)]">
                {actionError}
              </p>
            ) : null}
          </section>
          {run.resultSummary ? (
            <section className="detail-panel">
              <h2 className="mb-3 text-sm font-semibold">{detail("summary")}</h2>
              <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
                {run.resultSummary}
              </p>
            </section>
          ) : null}
          {Object.values(sectionErrors).some(Boolean) ? (
            <p role="status" className="text-sm text-[var(--muted-foreground)]">
              {t("partialGraph")}
            </p>
          ) : null}
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="activity">{detail("activity")}</TabsTrigger>
              <TabsTrigger value="children">{t("subagents")}</TabsTrigger>
              <TabsTrigger value="events">{t("events")}</TabsTrigger>
              <TabsTrigger value="graph">{t("graph")}</TabsTrigger>
            </TabsList>
            <TabsContent value="activity">
              <section aria-label={detail("activity")} className="detail-panel">
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                  <Input
                    type="search"
                    className="min-w-0 shrink-0 sm:w-auto sm:flex-1"
                    aria-label={t("activitySearch")}
                    placeholder={t("activitySearch")}
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                  />
                  <label className="flex items-center gap-2 text-sm">
                    {t("activityKind")}
                    <select
                      className={selectClass}
                      value={kind}
                      onChange={(event) => setKind(event.target.value)}
                    >
                      <option value="">{t("allActivity")}</option>
                      <option value="step">{t("stepsLabel")}</option>
                      <option value="tool">{t("toolsLabel")}</option>
                    </select>
                  </label>
                </div>
                <DetailState
                  loading={loading && !activity.length}
                  error={sectionErrors.steps}
                  onRetry={retry}
                />
                <DetailState loading={false} error={sectionErrors.tools} onRetry={retry} />
                {!loading && !matching.length && !sectionErrors.steps && !sectionErrors.tools ? (
                  <EmptyState
                    compact
                    title={query || kind ? t("noActivityMatches") : detail("noActivity")}
                  />
                ) : null}
                <ol className="divide-y divide-[var(--border)]">
                  {pagination.rows.map((row) => (
                    <li key={row.key} className="py-3 text-sm">
                      {row.source === "step" ? (
                        <details>
                          <summary className="cursor-pointer break-words font-medium">
                            {row.label}
                          </summary>
                          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs text-[var(--muted-foreground)]">
                            {JSON.stringify(row.step.detail ?? {}, null, 2)}
                          </pre>
                        </details>
                      ) : (
                        <ToolCallCard call={row.tool} label={t("toolsLabel")} />
                      )}
                    </li>
                  ))}
                </ol>
                {activity.length > 0 ? (
                  <ListPagination {...pagination} label={detail("activity")} />
                ) : null}
              </section>
            </TabsContent>
            <TabsContent value="children">
              <section aria-label={t("subagents")} className="detail-panel">
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                  <Input
                    type="search"
                    className="min-w-0 shrink-0 sm:w-auto sm:flex-1"
                    aria-label={t("childSearch")}
                    placeholder={t("childSearch")}
                    value={childQuery}
                    onChange={(event) => setChildQuery(event.target.value)}
                  />
                  <label className="flex items-center gap-2 text-sm">
                    {t("status")}
                    <select
                      className={selectClass}
                      value={childStatus}
                      onChange={(event) => setChildStatus(event.target.value)}
                    >
                      <option value="">{t("allStatuses")}</option>
                      {[
                        ...new Set(
                          children.flatMap((child) => (child.status ? [child.status] : [])),
                        ),
                      ]
                        .sort()
                        .map((value) => (
                          <option key={value} value={value}>
                            {statusLabel(value)}
                          </option>
                        ))}
                    </select>
                  </label>
                </div>
                <DetailState
                  loading={loading && !children.length}
                  error={sectionErrors.children}
                  onRetry={retry}
                />
                {!loading && !filteredChildren.length && !sectionErrors.children ? (
                  <EmptyState
                    compact
                    title={children.length ? t("noChildMatches") : t("noChildren")}
                  />
                ) : null}
                <ul className="row-list">
                  {childPagination.rows.map((child) => (
                    <li key={child.id} className="space-y-2 p-4 text-sm">
                      <Link
                        className="break-words font-medium underline"
                        href={`/runs/${child.id}`}
                      >
                        {child.agentName || child.agentSlug || t("child")}
                      </Link>
                      <div className="flex flex-wrap gap-2">
                        <Badge tone={statusTone(child.status)}>
                          {statusLabel(child.status ?? "")}
                        </Badge>
                        {durationLabel(child)}
                      </div>
                      <p className="break-all text-xs text-[var(--muted-foreground)]">{child.id}</p>
                    </li>
                  ))}
                </ul>
                {children.length > 0 ? (
                  <ListPagination {...childPagination} label={t("subagents")} />
                ) : null}
              </section>
            </TabsContent>
            <TabsContent value="events">
              {tab === "events" ? <RunEvents runId={runId} /> : null}
            </TabsContent>
            <TabsContent value="graph">
              <section aria-label={t("graph")} className="space-y-4">
                <p className="text-sm text-[var(--muted-foreground)]">{t("graphHelp")}</p>
                <RunTraceGraph nodes={graph.nodes} edges={graph.edges} />
              </section>
            </TabsContent>
          </Tabs>
        </section>
      ) : null}
    </AppShell>
  );
}
