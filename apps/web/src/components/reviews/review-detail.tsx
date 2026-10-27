"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, BackButton, DetailState } from "@/components/common/detail-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { confirmStepUp } from "@/lib/step-up";

type Row = Record<string, unknown>;

export function ReviewDetail({ reviewId }: { reviewId: string }) {
  const t = useTranslations("reviews");
  const [row, setRow] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setRow(null);
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
    if (!row || busy) {
      return;
    }
    setBusy(true);
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
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title={t("detail")}
        body={t("detailBody")}
        actions={<BackButton href="/reviews">{t("back")}</BackButton>}
      />
      <DetailState loading={loading} error={error} onRetry={() => void load()} />
      <ActionStatus busy={busy} />
      {row ? (
        <article className="mx-auto max-w-3xl rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 sm:p-8">
          <h2 className="font-medium">{String(row.subjectType)}</h2>
          <p className="mt-2">{String(row.statementText ?? "")}</p>
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">{String(row.status)}</p>
          {row.status === "pending" || row.status === "in_review" ? (
            <fieldset disabled={busy} className="mt-6 border-t border-[var(--border)] pt-2">
              <label className="mt-4 block text-sm" htmlFor="review-comment">
                {t("comment")}
                <textarea
                  id="review-comment"
                  className="mt-1 h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                />
              </label>
              <Button className="mt-4" disabled={busy} type="button" onClick={() => void sign()}>
                {t("sign")}
              </Button>
            </fieldset>
          ) : null}
        </article>
      ) : null}
    </AppShell>
  );
}
