"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
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
    setBusy(row.id);
    setError("");
    try {
      await api(`/api/v1/inbox/${row.id}:answer`, {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      setNotice(t("sent"));
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
      <ul className="space-y-3">
        {rows.map((row) => (
          <li
            className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
            key={row.id}
          >
            <p className="text-sm font-medium">
              {row.type === "approval" ? t("approval") : t("question")}
            </p>
            <p className="mt-2 text-sm">{row.question || row.qualifiedName}</p>
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
                {row.options && row.options.length > 0 ? (
                  <label className="text-sm" htmlFor={`answer-${row.id}`}>
                    {t("answer")}
                    <select
                      className="mt-1 rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-2 text-sm"
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
                  <label className="text-sm" htmlFor={`answer-${row.id}`}>
                    {t("answer")}
                    <Input
                      className="mt-1"
                      id={`answer-${row.id}`}
                      onChange={(event) =>
                        setAnswers((current) => ({ ...current, [row.id]: event.target.value }))
                      }
                      value={answers[row.id] ?? ""}
                    />
                  </label>
                )}
                <Button disabled={busy === row.id} type="submit">
                  {busy === row.id ? t("sending") : t("send")}
                </Button>
              </form>
            ) : null}
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
