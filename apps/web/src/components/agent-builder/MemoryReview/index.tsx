"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Fact = {
  id: string;
  content: string;
  status: string;
};

export function MemoryReview({ agentId }: { agentId: string }) {
  const t = useTranslations("memory");
  const [rows, setRows] = useState<Fact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [lesson, setLesson] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api<{ items: Fact[] }>(
        `/api/v1/agents/${agentId}/memory?status=pending_review`,
      );
      setRows(page.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("reviewError"));
    } finally {
      setLoading(false);
    }
  }, [agentId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function approve(id: string) {
    setBusy(true);
    setError("");
    try {
      setNotice("");
      await api(`/api/v1/agents/${agentId}/memory/${id}:approve`, { method: "POST" });
      setNotice(t("approved"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("reviewError"));
    } finally {
      setBusy(false);
    }
  }

  async function reject(id: string) {
    setBusy(true);
    setError("");
    try {
      setNotice("");
      await api(`/api/v1/agents/${agentId}/memory/${id}:reject`, { method: "POST" });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("reviewError"));
    } finally {
      setBusy(false);
    }
  }

  async function addLesson() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`/api/v1/agents/${agentId}/memory`, {
        method: "POST",
        body: JSON.stringify({ content: lesson, category: "lesson" }),
      });
      setLesson("");
      setNotice(t("saved"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("reviewError"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-label={t("reviewTitle")}
      className="mt-6 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
    >
      <h2 className="text-base font-semibold">{t("reviewTitle")}</h2>
      <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("reviewBody")}</p>
      {error ? (
        <p className="mt-3 text-sm text-[var(--destructive)]" role="alert">
          {error}{" "}
          <button className="underline" onClick={() => void load()} type="button">
            {t("retry")}
          </button>
        </p>
      ) : null}
      {notice ? (
        <p className="mt-3 text-sm" role="status">
          {notice}
        </p>
      ) : null}
      {loading ? <Skeleton className="mt-3 h-16 w-full" /> : null}
      {!loading && !error && rows.length === 0 ? (
        <p className="mt-3 text-sm text-[var(--muted-foreground)]">{t("reviewEmpty")}</p>
      ) : null}
      <ul className="mt-3 grid gap-2">
        {(!loading && !error ? rows : []).map((row) => (
          <li
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--border)] p-3"
            key={row.id}
          >
            <p>{row.content}</p>
            <div className="flex gap-2">
              <Button disabled={busy} onClick={() => void approve(row.id)} type="button">
                {t("approve")}
              </Button>
              <Button
                disabled={busy}
                onClick={() => void reject(row.id)}
                type="button"
                variant="outline"
              >
                {t("reject")}
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <form
        className="mt-4 grid max-w-xl gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void addLesson();
        }}
      >
        <label htmlFor="shared-lesson">
          {t("lesson")}
          <Input
            id="shared-lesson"
            onChange={(event) => setLesson(event.target.value)}
            value={lesson}
          />
        </label>
        <Button className="justify-self-start" disabled={busy || !lesson.trim()} type="submit">
          {t("addLesson")}
        </Button>
      </form>
    </section>
  );
}
