"use client";

import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

const UsageChart = dynamic(
  () => import("@/components/usage/usage-chart").then((mod) => mod.UsageChart),
  { ssr: false, loading: () => <Skeleton className="h-56 w-full" /> },
);

type Row = {
  keys?: Record<string, string>;
  quantity?: number;
  costMicros?: number;
};

type Summary = {
  currency?: string;
  rows?: Row[];
  totals?: { quantity?: number; costMicros?: number };
};

const field =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)]";

export function UsageScreen() {
  const t = useTranslations("usage");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [group, setGroup] = useState("day");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ group_by: group });
    if (from) {
      params.set("from", from);
    }
    if (to) {
      params.set("to", to);
    }
    try {
      setSummary(await api<Summary>(`/api/v1/usage/summary?${params.toString()}`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [from, group, t, to]);

  useEffect(() => {
    void load();
  }, [load]);

  async function download() {
    const params = new URLSearchParams({ group_by: group });
    if (from) {
      params.set("from", from);
    }
    if (to) {
      params.set("to", to);
    }
    const response = await fetch(`/api/v1/usage/export?${params.toString()}`, {
      credentials: "include",
    });
    const text = await response.text();
    const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "usage.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  const rows = summary?.rows ?? [];
  const points = rows.map((row) => ({
    label:
      Object.values(row.keys ?? {})
        .filter(Boolean)
        .join(" · ") || "—",
    quantity: row.quantity ?? 0,
  }));

  return (
    <AppShell>
      <PageHeader body={t("body")} title={t("title")} />
      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        <label className="text-sm" htmlFor="usage-from">
          {t("from")}
          <Input
            className="mt-1"
            id="usage-from"
            onChange={(event) => setFrom(event.target.value)}
            type="date"
            value={from}
          />
        </label>
        <label className="text-sm" htmlFor="usage-to">
          {t("to")}
          <Input
            className="mt-1"
            id="usage-to"
            onChange={(event) => setTo(event.target.value)}
            type="date"
            value={to}
          />
        </label>
        <label className="text-sm" htmlFor="usage-group">
          {t("group")}
          <select
            className={`mt-1 ${field}`}
            id="usage-group"
            onChange={(event) => setGroup(event.target.value)}
            value={group}
          >
            <option value="day">day</option>
            <option value="agent">agent</option>
            <option value="user">user</option>
            <option value="model">model</option>
            <option value="metric">metric</option>
          </select>
        </label>
        <div className="flex items-end">
          <Button onClick={() => void download()} type="button" variant="outline">
            {t("export")}
          </Button>
        </div>
      </div>
      {error ? (
        <p className="mb-3 text-sm text-[var(--destructive)]" role="alert">
          {error}{" "}
          <Button onClick={() => void load()} type="button" variant="outline">
            {t("retry")}
          </Button>
        </p>
      ) : null}
      {loading ? <Skeleton className="h-56 w-full" /> : null}
      {!loading && rows.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
      ) : null}
      {!loading && rows.length > 0 ? (
        <section className="space-y-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <p className="text-sm text-[var(--muted-foreground)]">
            {t("quantity")} {summary?.totals?.quantity?.toLocaleString() ?? 0}
            {" · "}
            {t("cost")} {summary?.totals?.costMicros?.toLocaleString() ?? 0} {summary?.currency}
          </p>
          <UsageChart points={points} />
          <ul className="space-y-2">
            {rows.map((row) => (
              <li
                className="flex items-center justify-between gap-3 text-sm"
                key={`${Object.values(row.keys ?? {}).join("-")}-${row.quantity}`}
              >
                <span>
                  {Object.values(row.keys ?? {})
                    .filter(Boolean)
                    .join(" · ")}
                </span>
                <span className="text-[var(--muted-foreground)]">
                  {(row.quantity ?? 0).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </AppShell>
  );
}
