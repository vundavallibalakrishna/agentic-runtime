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

const MODE_KEY = "ar-settings-mode";

export function ApprovalDetail({ approvalId }: { approvalId: string }) {
  const t = useTranslations("approvals");
  const [row, setRow] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const [comment, setComment] = useState("");

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRow(await api<Row>(`/api/v1/approvals/${approvalId}`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [approvalId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function decide(decision: "approve" | "reject") {
    if (!row) {
      return;
    }
    setError("");
    try {
      if (row.stepUpRequired) {
        await confirmStepUp();
      }
      await api(`/api/v1/approvals/${approvalId}:decide`, {
        method: "POST",
        body: JSON.stringify({
          decision,
          argsHash: String(row.argsHash ?? ""),
          comment,
        }),
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  const preview = (row?.preview ?? {}) as { title?: string; summary?: string };
  const reasons = Array.isArray(row?.policyReasons) ? row.policyReasons.map(String) : [];

  return (
    <AppShell>
      <PageHeader title={t("detail")} body={t("detailBody")} />
      <a className="mb-4 inline-block underline" href="/approvals">
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
          <Skeleton className="h-40 w-full" />
        </div>
      ) : null}
      {row ? (
        <article className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-lg font-medium">{String(row.qualifiedName ?? "")}</h2>
          <p className="text-sm text-[var(--muted-foreground)]">
            {String(row.riskClass ?? "")} · {String(row.status ?? "")}
          </p>
          <p className="mt-3">{preview.title}</p>
          <p>{preview.summary}</p>
          {reasons.length > 0 ? (
            <section className="mt-4">
              <h3 className="text-sm font-medium">{t("reasons")}</h3>
              <ul className="mt-1 list-disc pl-5">
                {reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </section>
          ) : null}
          {advanced ? (
            <pre className="mt-4 overflow-auto rounded-lg bg-[var(--muted)] p-3 text-xs">
              {JSON.stringify(row.arguments ?? {}, null, 2)}
            </pre>
          ) : null}
          {row.status === "pending" ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {row.stepUpRequired ? (
                <Button type="button" variant="outline" onClick={() => void confirmStepUp()}>
                  {t("stepUp")}
                </Button>
              ) : null}
              <Button type="button" onClick={() => void decide("approve")}>
                {t("approve")}
              </Button>
              <Button type="button" variant="outline" onClick={() => void decide("reject")}>
                {t("reject")}
              </Button>
            </div>
          ) : null}
          <label className="mt-4 block text-sm" htmlFor="detail-comment">
            {t("comment")}
            <textarea
              id="detail-comment"
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
