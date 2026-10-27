"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, BackButton, DetailState } from "@/components/common/detail-state";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
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
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
    setRow(null);
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
    if (!row || busy) {
      return;
    }
    setBusy(true);
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
    } finally {
      setBusy(false);
    }
  }

  async function stepUp() {
    setBusy(true);
    setError("");
    try {
      await confirmStepUp();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  const preview = (row?.preview ?? {}) as { title?: string; summary?: string };
  const reasons = Array.isArray(row?.policyReasons) ? row.policyReasons.map(String) : [];

  return (
    <AppShell>
      <PageHeader
        title={t("detail")}
        body={t("detailBody")}
        actions={
          <>
            <SettingsMode
              advanced={advanced}
              onChange={(next) => {
                setAdvanced(next);
                window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
              }}
            />
            <BackButton href="/approvals">{t("back")}</BackButton>
          </>
        }
      />
      <DetailState loading={loading} error={error} onRetry={() => void load()} />
      <ActionStatus busy={busy} />
      {row ? (
        <article className="mx-auto max-w-3xl rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 sm:p-8">
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
            <fieldset disabled={busy} className="mt-6 border-t border-[var(--border)] pt-2">
              <label className="mt-4 block text-sm" htmlFor="detail-comment">
                {t("comment")}
                <textarea
                  id="detail-comment"
                  className="mt-1 h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                />
              </label>
              <div className="mt-4 flex flex-wrap gap-2">
                {row.stepUpRequired ? (
                  <Button
                    disabled={busy}
                    type="button"
                    variant="outline"
                    onClick={() => void stepUp()}
                  >
                    {t("stepUp")}
                  </Button>
                ) : null}
                <Button disabled={busy} type="button" onClick={() => void decide("approve")}>
                  {t("approve")}
                </Button>
                <Button
                  disabled={busy}
                  type="button"
                  variant="outline"
                  onClick={() => void decide("reject")}
                >
                  {t("reject")}
                </Button>
              </div>
            </fieldset>
          ) : null}
        </article>
      ) : null}
    </AppShell>
  );
}
