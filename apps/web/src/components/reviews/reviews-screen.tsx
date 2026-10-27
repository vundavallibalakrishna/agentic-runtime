"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Row = Record<string, unknown>;

export function ReviewsScreen() {
  const t = useTranslations("reviews");
  const shell = useTranslations("shell");
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api<{ items: Row[] }>("/api/v1/review-items?scope=to_decide");
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
      <PageHeader
        title={t("title")}
        body={t("body")}
        actions={
          <Button asChild variant="outline">
            <a href="/approvals">{shell("navApprovals")}</a>
          </Button>
        }
      />
      {error ? (
        <p role="alert">
          {error}{" "}
          <button className="underline" type="button" onClick={() => void load()}>
            {t("retry")}
          </button>
        </p>
      ) : null}
      {loading ? (
        <div aria-busy="true">
          <span className="sr-only">{t("loading")}</span>
          <Skeleton className="h-24 w-full" />
        </div>
      ) : null}
      {!loading && !error && rows.length === 0 ? <EmptyState title={t("empty")} /> : null}
      <ul className="space-y-3">
        {rows.map((row) => (
          <li
            key={String(row.id)}
            className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
          >
            <a className="font-medium underline" href={`/reviews/${String(row.id)}`}>
              {String(row.subjectType)} · {String(row.status)}
            </a>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
