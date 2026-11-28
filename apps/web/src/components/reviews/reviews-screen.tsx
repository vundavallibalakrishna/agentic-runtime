"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { ReplyAcceptanceSettings } from "@/components/reviews/reply-acceptance-settings";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Row = {
  id: string;
  subjectType?: string;
  subjectId?: string;
  status?: string;
  createdAt?: string;
};

export function ReviewsScreen() {
  const t = useTranslations("reviews");
  const shell = useTranslations("shell");
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [scope, setScope] = useState("to_decide");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const requestVersion = useRef(0);
  const filtered = rows.filter(
    (row) =>
      (!status || row.status === status) &&
      [row.id, row.subjectId, row.subjectType, row.status].some((value) =>
        value?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
      ),
  );
  const pagination = usePagedRows(filtered, `${scope}::${query}::${status}`);
  const statuses = [
    ...new Set(rows.map((row) => row.status).filter((value): value is string => Boolean(value))),
  ].sort();

  const load = useCallback(async () => {
    const version = ++requestVersion.current;
    setLoading(true);
    setError("");
    try {
      const page = await api<{ items: Row[] }>(`/api/v1/review-items?scope=${scope}`);
      if (version === requestVersion.current) setRows(page.items ?? []);
    } catch (caught) {
      if (version === requestVersion.current)
        setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [scope, t]);

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
      <div className="mb-5 grid gap-3 sm:grid-cols-[auto_minmax(0,1fr)_auto]">
        <label className="text-sm">
          {t("view")}
          <select
            className="mt-1 block h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
            value={scope}
            onChange={(event) => {
              setScope(event.target.value);
              setStatus("");
            }}
          >
            <option value="to_decide">{t("toDecide")}</option>
            <option value="prepared">{t("prepared")}</option>
            <option value="all">{t("all")}</option>
          </select>
        </label>
        <label htmlFor="review-search" className="min-w-0 flex-1 text-sm">
          {t("search")}
          <Input
            className="mt-1"
            id="review-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label className="text-sm">
          {t("status")}
          <select
            className="mt-1 block h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">{t("allStatuses")}</option>
            {statuses.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>
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
      {!loading && !error && filtered.length === 0 ? (
        <EmptyState
          title={
            query.trim() || status
              ? t("noMatches")
              : scope === "to_decide"
                ? t("empty")
                : t("emptyView")
          }
        />
      ) : null}
      <ul className="row-list">
        {(loading ? [] : pagination.rows).map((row) => (
          <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="min-w-0">
              <a className="break-words font-medium hover:underline" href={`/reviews/${row.id}`}>
                {row.subjectType?.replaceAll("_", " ")} · {t("reference", { id: row.id.slice(-8) })}
              </a>
              {row.subjectId ? (
                <p className="mt-1 break-all text-xs text-[var(--muted-foreground)]">
                  {t("subject")}: <span title={row.subjectId}>{row.subjectId.slice(-8)}</span>
                </p>
              ) : null}
              {row.createdAt ? (
                <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                  <time dateTime={row.createdAt}>{new Date(row.createdAt).toLocaleString()}</time>
                </p>
              ) : null}
            </div>
            {row.status ? <Badge tone={statusTone(row.status)}>{row.status}</Badge> : null}
          </li>
        ))}
      </ul>
      {!loading && rows.length > 0 ? <ListPagination {...pagination} /> : null}
      <ReplyAcceptanceSettings />
    </AppShell>
  );
}
