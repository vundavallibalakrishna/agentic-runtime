"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { DetailState } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { durationLabel } from "@/components/runs/format";
import { useRunInspection } from "@/components/runs/use-run-inspection";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Named = { id?: unknown; name?: unknown };
export function RunDetails(props: { runId: string; settled: boolean; agents: Named[] }) {
  return <RunFacts key={props.runId} {...props} />;
}
function RunFacts({
  runId,
  settled,
  agents,
}: {
  runId: string;
  settled: boolean;
  agents: Named[];
}) {
  const t = useTranslations("chat");
  const { run, steps, tools, loading, error, sectionErrors, refresh } = useRunInspection(runId, {
    allowPolling: settled,
    pollInterval: 5000,
  });
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const matching = tools.filter(
    (tool) =>
      (!status || tool.status === status) &&
      [tool.id, tool.qualifiedName, tool.status].some((value) =>
        value?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
      ),
  );
  const pagination = usePagedRows(matching, `${query}::${status}`);
  const agent = agents.find((item) => item.id === run?.agentId);
  return (
    <aside
      aria-label={t("runDetails")}
      className="max-h-[55%] min-w-0 shrink-0 overflow-y-auto border-b border-l border-[var(--border)] bg-[var(--card)] px-4 py-4"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--muted-foreground)]">
          {t("runDetails")}
        </h2>
        <Button asChild className="h-8 px-2 text-xs" variant="outline">
          <Link href={`/runs/${runId}`}>{t("viewTrace")}</Link>
        </Button>
      </div>
      <DetailState loading={loading && !run} error={error} onRetry={refresh} />
      {run ? (
        <>
          <Facts
            align="end"
            items={[
              {
                label: t("runStatus"),
                value: <Badge tone={statusTone(run.status)}>{run.status}</Badge>,
              },
              {
                label: t("agent"),
                value: (
                  <span className="block break-words font-medium">
                    {agent?.name ? String(agent.name) : run.agentName || run.agentSlug || "—"}
                  </span>
                ),
              },
              {
                label: t("runModel"),
                value: <span className="block break-words">{run.answeredModel || "—"}</span>,
              },
              {
                label: t("runDuration"),
                value: <span className="tabular-nums">{durationLabel(run) || "—"}</span>,
              },
              {
                label: t("runSteps"),
                value: (
                  <span className="tabular-nums">
                    {run.usage?.steps ??
                      (sectionErrors.steps || (loading && !steps.length) ? "—" : steps.length)}
                  </span>
                ),
              },
              {
                label: t("runToolCalls"),
                value: (
                  <span className="tabular-nums">
                    {sectionErrors.tools || (loading && !tools.length) ? "—" : tools.length}
                  </span>
                ),
              },
            ]}
          />
          <div className="mt-4">
            <DetailState loading={false} error={sectionErrors.steps} onRetry={refresh} />
          </div>
          <h3 className="panel-title mb-2 mt-5">{t("runToolCalls")}</h3>
          <DetailState
            loading={loading && tools.length === 0}
            error={sectionErrors.tools}
            onRetry={refresh}
          />
          {tools.length ? (
            <details className="mb-3">
              <summary className="mb-2 cursor-pointer text-xs text-[var(--muted-foreground)]">
                {t(query || status ? "runToolFiltersActive" : "runToolFilters")}
              </summary>
              <div className="space-y-2">
                <Input
                  type="search"
                  aria-label={t("runToolSearch")}
                  placeholder={t("runToolSearch")}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
                <label className="block text-xs">
                  {t("runStatus")}
                  <select
                    className="mt-1 h-9 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 text-sm"
                    value={status}
                    onChange={(event) => setStatus(event.target.value)}
                  >
                    <option value="">{t("runAllStatuses")}</option>
                    {[...new Set(tools.flatMap((tool) => (tool.status ? [tool.status] : [])))]
                      .sort()
                      .map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
              {query || status ? (
                <Button
                  type="button"
                  variant="ghost"
                  className="mt-2 h-8 text-xs"
                  onClick={() => {
                    setQuery("");
                    setStatus("");
                  }}
                >
                  {t("runClearFilters")}
                </Button>
              ) : null}
            </details>
          ) : null}
          {!loading && !sectionErrors.tools && matching.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">
              {t(tools.length ? "runNoToolMatches" : "runNoTools")}
            </p>
          ) : null}
          {!sectionErrors.tools ? (
            <ul className="space-y-2">
              {pagination.rows.map((tool, index) => (
                <li
                  className="flex flex-wrap items-center justify-between gap-2 text-sm"
                  key={tool.id ?? `tool-${index}`}
                >
                  <span className="min-w-0 break-all font-mono text-xs">{tool.qualifiedName}</span>
                  <Badge tone={statusTone(tool.status)}>{tool.status}</Badge>
                </li>
              ))}
            </ul>
          ) : null}
          {tools.length &&
          !sectionErrors.tools &&
          (tools.length > pagination.pageSize || query || status) ? (
            <div className="mt-4">
              <ListPagination {...pagination} compact label={t("runToolCalls")} />
            </div>
          ) : null}
        </>
      ) : null}
    </aside>
  );
}
