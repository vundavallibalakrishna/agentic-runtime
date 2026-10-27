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
};

export function RunsScreen() {
  const t = useTranslations("runs");
  const [rows, setRows] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api<{ items: Run[] }>("/api/v1/runs");
      setRows(page.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

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
