"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableScroll,
} from "@/components/ui/table";
import { api } from "@/lib/api";

import { durationLabel, liveStatuses } from "./format";

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

  const live = rows.some((run) => liveStatuses.includes(run.status || ""));
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
      {rows.length > 0 ? (
        <TableScroll
          className="rounded-xl border border-[var(--border)] bg-[var(--card)]"
          label={t("title")}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">{t("run")}</TableHead>
                <TableHead scope="col">{t("status")}</TableHead>
                <TableHead scope="col">{t("duration")}</TableHead>
                <TableHead scope="col">{t("cost")}</TableHead>
                <TableHead scope="col">
                  <span className="sr-only">{t("trace")}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((run) => (
                <TableRow key={run.id}>
                  <TableCell className="min-w-64">
                    <p className="font-medium">
                      {run.trigger || t("title")}
                      {run.depth ? ` · ${t("childStatus")} ${run.depth}` : ""}
                    </p>
                    <p className="mt-1 line-clamp-2 text-[var(--muted-foreground)]">
                      {run.resultSummary || t("noSummary")}
                    </p>
                  </TableCell>
                  <TableCell>
                    <Badge tone={statusTone(run.status)}>{run.status}</Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {durationLabel(run) || "—"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {run.usage?.costMicros ?? "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button asChild className="whitespace-nowrap" variant="outline">
                      <Link href={`/runs/${run.id}`}>{t("trace")}</Link>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableScroll>
      ) : null}
    </AppShell>
  );
}
