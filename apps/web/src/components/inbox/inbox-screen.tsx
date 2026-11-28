"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Item = {
  id: string;
  type: string;
  question?: string;
  options?: string[];
  runId?: string;
  qualifiedName?: string;
  status?: string;
};

export function InboxScreen() {
  const t = useTranslations("inbox");
  const [rows, setRows] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const filtered = rows.filter(
    (row) =>
      (!kind || row.type === kind) &&
      [row.question, row.qualifiedName, row.id, row.runId].some((value) =>
        value?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
      ),
  );
  const pagination = usePagedRows(filtered, `${query}::${kind}`);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api<{ items: Item[] }>("/api/v1/inbox");
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

  async function send(row: Item) {
    const text = answers[row.id] ?? row.options?.[0] ?? "";
    if (busy || !text.trim()) return;
    setNotice("");
    setBusy(row.id);
    setError("");
    try {
      await api(`/api/v1/inbox/${row.id}:answer`, {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      setNotice(t("sent"));
      setAnswers((current) => {
        const next = { ...current };
        delete next[row.id];
        return next;
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy("");
    }
  }

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
      {notice ? (
        <p className="mb-3 text-sm" role="status">
          {notice}
        </p>
      ) : null}
      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : null}
      {!loading && !error && rows.length === 0 ? <EmptyState title={t("empty")} /> : null}
      {!loading && rows.length > 0 ? (
        <div className="mb-4 flex flex-wrap gap-3">
          <Input
            type="search"
            className="min-w-0 flex-1"
            aria-label={t("search")}
            placeholder={t("search")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <select
            aria-label={t("type")}
            className="h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
            value={kind}
            onChange={(event) => setKind(event.target.value)}
          >
            <option value="">{t("allTypes")}</option>
            <option value="question">{t("question")}</option>
            <option value="approval">{t("approval")}</option>
          </select>
        </div>
      ) : null}
      {!loading && rows.length > 0 && filtered.length === 0 ? (
        <EmptyState title={t("noMatches")} />
      ) : null}
      <ul className="row-list">
        {(loading ? [] : pagination.rows).map((row) => (
          <li className="p-4" key={row.id}>
            <p className="text-sm font-medium">
              {row.type === "approval" ? t("approval") : t("question")}
            </p>
            <p className="mt-2 text-sm">{row.question || row.qualifiedName}</p>
            {row.type === "approval" ? (
              <p className="mt-3 text-sm">
                <Link className="underline" href={`/approvals/${row.id}`}>
                  {t("reviewApproval")}
                </Link>
              </p>
            ) : null}
            {row.runId ? (
              <p className="mt-2 text-sm">
                <Link className="underline" href={`/runs/${row.runId}`}>
                  {t("openRun")}
                </Link>
              </p>
            ) : null}
            {row.type === "question" ? (
              <form
                className="mt-3 flex flex-wrap items-end gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  void send(row);
                }}
              >
                <fieldset
                  disabled={Boolean(busy)}
                  className="flex min-w-0 flex-wrap items-end gap-2"
                >
                  {row.options && row.options.length > 0 ? (
                    <label className="min-w-0 flex-1 text-sm" htmlFor={`answer-${row.id}`}>
                      {t("answer")}
                      <select
                        className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-2 text-sm"
                        id={`answer-${row.id}`}
                        onChange={(event) =>
                          setAnswers((current) => ({ ...current, [row.id]: event.target.value }))
                        }
                        value={answers[row.id] ?? row.options[0]}
                      >
                        {row.options.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : (
                    <label className="min-w-0 flex-1 text-sm" htmlFor={`answer-${row.id}`}>
                      {t("answer")}
                      <textarea
                        className="mt-1 min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                        required
                        id={`answer-${row.id}`}
                        onChange={(event) =>
                          setAnswers((current) => ({ ...current, [row.id]: event.target.value }))
                        }
                        value={answers[row.id] ?? ""}
                      />
                    </label>
                  )}
                  <Button
                    disabled={Boolean(busy) || !(answers[row.id] ?? row.options?.[0] ?? "").trim()}
                    type="submit"
                  >
                    {busy === row.id ? t("sending") : t("send")}
                  </Button>
                </fieldset>
              </form>
            ) : null}
          </li>
        ))}
      </ul>
      {!loading && rows.length > 0 ? <ListPagination {...pagination} /> : null}
    </AppShell>
  );
}
