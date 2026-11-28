"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ErrorMessage } from "@/components/common/detail-state";
import { ListPagination } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { useCursorPage } from "@/components/common/use-cursor-page";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const pagination = useCursorPage<Run>("/api/v1/runs", { q: query, status });
  const { rows, loading, error, refresh: load } = pagination;
  const live = rows.some((run) => liveStatuses.includes(run.status || ""));
  useEffect(() => {
    if (!live) return;
    const timer = window.setInterval(() => void load(true), 2000);
    return () => window.clearInterval(timer);
  }, [live, load]);

  return (
    <AppShell>
      <PageHeader body={t("body")} title={t("title")} />
      {rows.length > 0 || query || status ? (
        <div className="mb-5 flex flex-wrap items-end gap-3">
          <label className="block w-full max-w-md text-sm" htmlFor="run-search">
            {t("searchRuns")}
            <Input
              className="mt-2"
              id="run-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label className="block text-sm" htmlFor="run-status">
            {t("status")}
            <select
              id="run-status"
              className="mt-2 block h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="">{t("allStatuses")}</option>
              {[
                "queued",
                "running",
                "waiting_approval",
                "waiting_input",
                "completed",
                "failed",
                "cancelled",
                "budget_exceeded",
              ].map((value) => (
                <option key={value} value={value}>
                  {t.has(`statuses.${value}`) ? t(`statuses.${value}`) : value}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : null}
      {!loading && !error && rows.length === 0 && (query || status) ? (
        <p className="mb-5 text-sm text-[var(--muted-foreground)]" role="status">
          {t("noMatches")}
        </p>
      ) : null}
      {error ? (
        <p className="mb-3 text-sm text-[var(--destructive)]" role="alert">
          <ErrorMessage error={error} />{" "}
          <Button onClick={() => pagination.retry()} type="button" variant="outline">
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
      {!loading && !error && rows.length === 0 && !query && !status ? (
        <EmptyState title={t("empty")} />
      ) : null}
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
                <TableHead scope="col">{t("costMicros")}</TableHead>
                <TableHead scope="col">
                  <span className="sr-only">{t("trace")}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagination.rows.map((run) => (
                <TableRow key={run.id}>
                  <TableCell className="min-w-64">
                    <p className="font-medium">
                      {run.trigger || t("title")}
                      {run.depth ? ` · ${t("childStatus")} ${run.depth}` : ""}
                    </p>
                    <p
                      className="mt-1 font-mono text-xs text-[var(--muted-foreground)]"
                      title={run.id}
                    >
                      {run.id.slice(-8)}
                    </p>
                    <p className="mt-1 line-clamp-2 text-[var(--muted-foreground)]">
                      {run.resultSummary || t("noSummary")}
                    </p>
                  </TableCell>
                  <TableCell>
                    <Badge tone={statusTone(run.status)}>
                      {run.status && t.has(`statuses.${run.status}`)
                        ? t(`statuses.${run.status}`)
                        : run.status}
                    </Badge>
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
      {rows.length > 0 || pagination.page > 1 ? <ListPagination {...pagination} /> : null}
    </AppShell>
  );
}
