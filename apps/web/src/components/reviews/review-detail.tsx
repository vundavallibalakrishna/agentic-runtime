"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { confirmStepUp } from "@/lib/step-up";

type Row = Record<string, unknown>;

export function ReviewDetail({ reviewId }: { reviewId: string }) {
  const t = useTranslations("reviews");
  const [row, setRow] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [comment, setComment] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRow(await api<Row>(`/api/v1/review-items/${reviewId}`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [reviewId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function sign() {
    if (!row) {
      return;
    }
    setError("");
    try {
      await confirmStepUp();
      await api(`/api/v1/review-items/${reviewId}:decide`, {
        method: "POST",
        body: JSON.stringify({
          decision: "approve",
          comment,
          contentHash: String(row.contentHash ?? ""),
          statementHash: String(row.statementHash ?? ""),
        }),
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  return (
    <AppShell>
      <PageHeader title={t("detail")} body={t("detailBody")} />
      <a className="mb-4 inline-block underline" href="/reviews">
        {t("back")}
      </a>
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
          <Skeleton className="h-32 w-full" />
        </div>
      ) : null}
      {row ? (
        <article className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="font-medium">{String(row.subjectType)}</h2>
          <p className="mt-2">{String(row.statementText ?? "")}</p>
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">{String(row.status)}</p>
          {row.status === "pending" || row.status === "in_review" ? (
            <Button className="mt-4" type="button" onClick={() => void sign()}>
              {t("sign")}
            </Button>
          ) : null}
          <label className="mt-4 block text-sm" htmlFor="review-comment">
            {t("comment")}
            <textarea
              id="review-comment"
              className="mt-1 h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
          </label>
        </article>
      ) : null}
    </AppShell>
  );
}
