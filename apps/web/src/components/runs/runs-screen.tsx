"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Run = {
  id: string;
  status?: string;
  trigger?: string;
  resultSummary?: string;
  startedAt?: string | null;
  endedAt?: string | null;
  depth?: number;
  parentRunId?: string | null;
  usage?: { costMicros?: number; tokensOut?: number };
};

function durationLabel(run: Run) {
  const start = Date.parse(run.startedAt || "");
  if (!start) return "";
  const end = Date.parse(run.endedAt || "") || Date.now();
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  return `${seconds}s`;
}

export function RunsScreen() {
  const t = useTranslations("runs");
  const [rows, setRows] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(
    async (quiet = false) => {
      if (!quiet) setLoading(true);
      setError("");
      try {
        const page = await api<{ items: Run[] }>("/api/v1/runs");
        setRows(page.items ?? []);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : t("error"));
      } finally {
        setLoading(false);
      }
    },
    [t],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const live = rows.some((run) =>
    ["queued", "running", "waiting_input", "waiting_approval"].includes(run.status || ""),
  );
  useEffect(() => {
    if (!live) return;
    const timer = window.setInterval(() => void load(true), 2000);
    return () => window.clearInterval(timer);
  }, [live, load]);

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
      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : null}
      {!loading && !error && rows.length === 0 ? <EmptyState title={t("empty")} /> : null}
      <ul className="space-y-2">
        {rows.map((run) => (
          <li
            className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
            key={run.id}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  {run.trigger || t("title")} · {run.status}
                  {durationLabel(run) ? ` · ${durationLabel(run)}` : ""}
                  {run.usage?.costMicros != null ? ` · ${t("cost")} ${run.usage.costMicros}` : ""}
                  {run.depth ? ` · ${t("childStatus")} ${run.depth}` : ""}
                </p>
                <p className="mt-2 line-clamp-2 text-sm text-[var(--muted-foreground)]">
                  {run.resultSummary || t("noSummary")}
                </p>
              </div>
              <Button asChild variant="outline">
                <Link href={`/runs/${run.id}`}>{t("trace")}</Link>
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
