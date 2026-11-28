"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, BackButton, DetailState } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TableScroll } from "@/components/ui/table";
import { ApiError, api, type Session } from "@/lib/api";
import { loadSession } from "@/lib/session";
import { confirmStepUp } from "@/lib/step-up";

type Row = Record<string, unknown>;

/** The statement a saved-query item asks the signer to approve, shown in full. */
function SubjectQuery({ subject }: { subject: unknown }) {
  const t = useTranslations("reviews");
  const ref = subject && typeof subject === "object" ? (subject as Row) : {};
  if (typeof ref.sql !== "string" || !ref.sql) {
    return null;
  }
  return (
    <section className="mt-5 min-w-0">
      <h3 className="text-sm font-medium">{t("queryText")}</h3>
      <p className="mt-1 break-words text-sm text-[var(--muted-foreground)]">
        {t("queryVersion", { name: String(ref.name ?? ""), version: String(ref.version ?? "") })}
      </p>
      {typeof ref.description === "string" && ref.description ? (
        <p className="mt-1 break-words text-sm">{ref.description}</p>
      ) : null}
      <TableScroll label={t("queryText")} className="mt-2 max-h-96 rounded-lg bg-[var(--muted)]">
        <pre className="p-3 text-xs">{ref.sql}</pre>
      </TableScroll>
    </section>
  );
}

export function ReviewDetail({ reviewId }: { reviewId: string }) {
  return <ReviewItem key={reviewId} reviewId={reviewId} />;
}

function ReviewItem({ reviewId }: { reviewId: string }) {
  const t = useTranslations("reviews");
  const confirmation = useTranslations("detail");
  const [session, setSession] = useState<Session | null>(null);
  const [missing, setMissing] = useState(false);
  const [actionError, setActionError] = useState("");
  const readRequest = useRef<AbortController | null>(null);
  const decisionRequest = useRef<AbortController | null>(null);
  const [row, setRow] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    readRequest.current?.abort();
    const controller = new AbortController();
    readRequest.current = controller;
    setRow(null);
    setMissing(false);
    setLoading(true);
    setError("");
    setActionError("");
    try {
      const [identity, item] = await Promise.all([
        loadSession(),
        api<Row>(`/api/v1/review-items/${encodeURIComponent(reviewId)}`, {
          signal: controller.signal,
        }).catch((caught: unknown) => {
          if (caught instanceof ApiError && caught.status === 404) return null;
          throw caught;
        }),
      ]);
      if (controller.signal.aborted) return;
      setSession(identity);
      setRow(item);
      setMissing(item === null);
    } catch (caught) {
      if (!controller.signal.aborted)
        setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [reviewId, t]);

  useEffect(() => {
    void load();
    return () => {
      readRequest.current?.abort();
      decisionRequest.current?.abort();
    };
  }, [load]);

  const pending = row?.status === "pending" || row?.status === "in_review";
  const hasPermission = Boolean(
    session?.user?.id && session.permissions?.includes("reviews:decide"),
  );
  const preparedByMe = Boolean(session?.user?.id && row?.preparerPrincipalId === session.user.id);
  const hasHashes =
    typeof row?.contentHash === "string" &&
    Boolean(row.contentHash) &&
    typeof row?.statementHash === "string" &&
    Boolean(row.statementHash);
  const canSign = pending && hasPermission && !preparedByMe && hasHashes;

  async function sign() {
    if (!row || !canSign || decisionRequest.current) return;
    const controller = new AbortController();
    decisionRequest.current = controller;
    setBusy(true);
    setActionError("");
    try {
      await confirmStepUp(confirmation("stepUpUnconfirmed"), controller.signal);
      if (controller.signal.aborted) return;
      await api(`/api/v1/review-items/${encodeURIComponent(reviewId)}:decide`, {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          decision: "approve",
          comment,
          contentHash: row.contentHash,
          statementHash: row.statementHash,
        }),
      });
      if (!controller.signal.aborted) await load();
    } catch (caught) {
      if (!controller.signal.aborted)
        setActionError(caught instanceof Error ? caught.message : t("decisionError"));
    } finally {
      decisionRequest.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title={t("detail")}
        body={t("detailBody")}
        actions={<BackButton href="/reviews">{t("back")}</BackButton>}
      />
      <DetailState loading={loading} error={error} onRetry={busy ? undefined : () => void load()} />
      <ActionStatus busy={busy} />
      {missing ? (
        <div className="max-w-3xl">
          <EmptyState title={t("missing")}>{t("missingHelp")}</EmptyState>
        </div>
      ) : null}
      {row ? (
        <article className="min-w-0 max-w-3xl rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 sm:p-8">
          <Facts
            items={[
              {
                label: t("subject"),
                value: typeof row.subjectType === "string" ? row.subjectType : null,
              },
              { label: t("itemReference"), value: typeof row.id === "string" ? row.id : null },
              {
                label: t("status"),
                value:
                  typeof row.status === "string" ? (
                    <Badge tone={statusTone(row.status)}>{row.status}</Badge>
                  ) : null,
              },
            ]}
          />
          <h2 className="mt-6 font-medium">{t("statement")}</h2>
          <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-relaxed">
            {String(row.statementText ?? "")}
          </p>
          <SubjectQuery subject={row.subjectRef} />
          {pending && !canSign ? (
            <p className="mt-6 border-t border-[var(--border)] pt-4 text-sm text-[var(--muted-foreground)]">
              {t(!hasPermission ? "readOnly" : preparedByMe ? "selfReview" : "missingHashes")}
            </p>
          ) : null}
          <DetailState loading={false} error={actionError} />
          {actionError || (pending && hasPermission && !preparedByMe && !hasHashes) ? (
            <Button className="mt-4" variant="outline" disabled={busy} onClick={() => void load()}>
              {t("refresh")}
            </Button>
          ) : null}
          {canSign ? (
            <fieldset disabled={busy} className="mt-6 border-t border-[var(--border)] pt-2">
              <legend className="sr-only">{t("yourReview")}</legend>
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
