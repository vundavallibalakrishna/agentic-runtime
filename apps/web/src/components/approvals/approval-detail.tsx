"use client";

import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  ActionStatus,
  BackButton,
  DetailState,
  ErrorMessage,
} from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TableScroll } from "@/components/ui/table";
import type { DisplayError } from "@/lib/api";
import { ApiError, api } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { confirmStepUp } from "@/lib/step-up";

type Row = Record<string, unknown>;

const MODE_KEY = "ar-settings-mode";

export function ApprovalDetail({ approvalId }: { approvalId: string }) {
  return <ApprovalItem key={approvalId} approvalId={approvalId} />;
}

function ApprovalItem({ approvalId }: { approvalId: string }) {
  const t = useTranslations("approvals");
  const confirmation = useTranslations("detail");
  const readRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const [row, setRow] = useState<Row | null>(null);
  const [error, setError] = useState<DisplayError>("");
  const [loading, setLoading] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const [comment, setComment] = useState("");
  const [phase, setPhase] = useState<
    "confirming" | "approving" | "rejecting" | "refreshing" | null
  >(null);
  const busy = phase !== null;
  const [actionError, setActionError] = useState<DisplayError>("");
  const [missing, setMissing] = useState(false);
  const [recovery, setRecovery] = useState<{ accepted: boolean; detail: DisplayError } | null>(
    null,
  );
  const [recorded, setRecorded] = useState(false);
  const [notice, setNotice] = useState("");
  const [reasonQuery, setReasonQuery] = useState("");

  useEffect(() => {
    try {
      setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
    } catch {
      setAdvanced(false);
    }
  }, []);

  const load = useCallback(
    async (clearRecovery = false) => {
      readRequest.current?.abort();
      const request = new AbortController();
      readRequest.current = request;
      setLoading(true);
      setError("");
      setMissing(false);
      try {
        const body = await api<Row>(`/api/v1/approvals/${encodeURIComponent(approvalId)}`, {
          signal: request.signal,
        });
        if (request.signal.aborted) return false;
        if (body?.id !== approvalId || typeof body.status !== "string" || !body.status)
          throw new Error(t("detailsUnconfirmed"));
        setRow(body);
        if (clearRecovery) {
          setRecovery(null);
          setActionError("");
        }
        return true;
      } catch (caught) {
        if (!request.signal.aborted) {
          if (caught instanceof ApiError && caught.status === 404) {
            setRow(null);
            setMissing(true);
          } else setError(caught instanceof Error ? caught : t("error"));
        }
        return false;
      } finally {
        if (readRequest.current === request) {
          readRequest.current = null;
          setLoading(false);
        }
      }
    },
    [approvalId, t],
  );

  useEffect(() => {
    void load();
    return () => {
      readRequest.current?.abort();
      actionRequest.current?.abort();
    };
  }, [load]);

  const pending = row?.status === "pending";
  const hasHash = typeof row?.argsHash === "string" && Boolean(row.argsHash);
  const canDecide = pending && row?.canDecide === true && hasHash && !recorded;

  async function decide(decision: "approve" | "reject") {
    if (!row || !canDecide || actionRequest.current || loading || error || recovery) return;
    const request = new AbortController();
    actionRequest.current = request;
    const snapshotHash = row.argsHash;
    const submittedComment = comment;
    let posted = false;
    let accepted = false;
    setActionError("");
    setNotice("");
    setPhase(
      row.stepUpRequired ? "confirming" : decision === "approve" ? "approving" : "rejecting",
    );
    try {
      if (row.stepUpRequired)
        await confirmStepUp(confirmation("stepUpUnconfirmed"), request.signal);
      if (request.signal.aborted) return;
      setPhase(decision === "approve" ? "approving" : "rejecting");
      posted = true;
      const result = await api<Row>(`/api/v1/approvals/${encodeURIComponent(approvalId)}:decide`, {
        method: "POST",
        signal: request.signal,
        body: JSON.stringify({ decision, argsHash: snapshotHash, comment: submittedComment }),
      });
      if (request.signal.aborted) return;
      const statuses = decision === "reject" ? ["rejected"] : ["pending", "approved"];
      if (
        result?.id !== approvalId ||
        result.argsHash !== snapshotHash ||
        typeof result.status !== "string" ||
        !statuses.includes(result.status)
      )
        throw new Error(t("decisionUnconfirmed"));
      accepted = true;
      setRecorded(true);
      setRow(result);
      setComment((current) => (current === submittedComment ? "" : current));
      setNotice(
        t(
          result.status === "pending"
            ? "decisionWaiting"
            : decision === "approve"
              ? "approvedRecorded"
              : "rejectedRecorded",
        ),
      );
      setPhase("refreshing");
      if (!(await load()) && !request.signal.aborted) setRecovery({ accepted: true, detail: "" });
    } catch (caught) {
      if (!request.signal.aborted) {
        const detail = caught instanceof Error ? caught : t("error");
        if (posted) setRecovery({ accepted, detail });
        else setActionError(detail);
      }
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setPhase(null);
      }
    }
  }

  const preview = (row?.preview ?? {}) as { title?: string; summary?: string };
  const reasons = useMemo(
    () =>
      Array.isArray(row?.policyReasons)
        ? row.policyReasons.map((text, ordinal) => ({
            id: `reason-${ordinal}`,
            text: String(text),
          }))
        : [],
    [row?.policyReasons],
  );
  const matchingReasons = useMemo(
    () =>
      reasons.filter((reason) =>
        reason.text.toLocaleLowerCase().includes(reasonQuery.trim().toLocaleLowerCase()),
      ),
    [reasons, reasonQuery],
  );
  const reasonPage = usePagedRows(matchingReasons, reasonQuery);
  const countKnown =
    typeof row?.approvalsReceived === "number" &&
    Number.isFinite(row.approvalsReceived) &&
    typeof row.requiredApprovals === "number" &&
    row.requiredApprovals > 0;
  const progress = countKnown
    ? t("approvalProgress", {
        received: formatCount(Number(row?.approvalsReceived)),
        required: formatCount(Number(row?.requiredApprovals)),
      })
    : null;
  const held = busy || loading || Boolean(error) || Boolean(recovery) || !hasHash;
  const refresh = () => {
    if (!actionRequest.current) void load(true);
  };

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
                try {
                  window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
                } catch {
                  /* Keep the chosen mode for this view. */
                }
              }}
            />
            <BackButton href="/approvals">{t("back")}</BackButton>
          </>
        }
      />
      <DetailState loading={loading && !row} error={error} onRetry={busy ? undefined : refresh} />
      <ActionStatus
        busy={busy || (loading && Boolean(row))}
        busyLabel={phase ? t(`progress.${phase}`) : t("progress.refreshing")}
        notice={notice}
      />
      {actionError ? (
        <div role="alert" className="mb-4 break-words text-sm text-[var(--destructive)]">
          <ErrorMessage error={actionError} />
        </div>
      ) : null}
      {recovery ? (
        <div role="alert" className="mb-4 rounded-lg border border-[var(--border)] p-4 text-sm">
          <p>{t(recovery.accepted ? "acceptedRecovery" : "decisionRecovery")}</p>
          {recovery.detail ? (
            <div className="mt-2 break-words text-[var(--muted-foreground)]">
              <ErrorMessage error={recovery.detail} />
            </div>
          ) : null}
        </div>
      ) : null}
      {!row && recovery ? (
        <Button
          className="mb-5"
          type="button"
          variant="outline"
          disabled={busy || loading}
          onClick={refresh}
        >
          {t("refreshApproval")}
        </Button>
      ) : null}
      {missing ? (
        <EmptyState title={t("missing")}>
          <p>{t("missingHelp")}</p>
        </EmptyState>
      ) : null}
      {row ? (
        <article className="detail-panel max-w-3xl">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <h2 className="min-w-0 break-all font-mono text-base font-semibold">
              {String(row.qualifiedName || t("unavailableTool"))}
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={statusTone(String(row.status ?? ""))}>{String(row.status ?? "")}</Badge>
              <Button
                aria-label={t("refreshApproval")}
                title={t("refreshApproval")}
                className="size-9 p-0"
                type="button"
                variant="ghost"
                disabled={busy || loading}
                onClick={refresh}
              >
                <RefreshCw size={16} aria-hidden="true" />
              </Button>
            </div>
          </div>
          <Facts
            className="mt-4"
            items={[
              {
                label: t("risk"),
                value: row.riskClass ? <Badge>{String(row.riskClass)}</Badge> : null,
              },
              { label: t("approvalCount"), value: progress },
            ]}
          />
          {preview.title || preview.summary ? (
            <section className="mt-5 border-t border-[var(--border)] pt-5">
              <h3 className="panel-title">{t("request")}</h3>
              <p className="mt-2 font-medium">{preview.title}</p>
              <p className="mt-1 text-sm">{preview.summary}</p>
            </section>
          ) : null}
          {reasons.length > 0 ? (
            <section className="mt-5 border-t border-[var(--border)] pt-5">
              <h3 className="panel-title">{t("reasons")}</h3>
              {reasons.length > 25 || reasonQuery ? (
                <Input
                  className="mt-3"
                  type="search"
                  aria-label={t("findReasons")}
                  placeholder={t("findReasons")}
                  value={reasonQuery}
                  onChange={(event) => setReasonQuery(event.target.value)}
                />
              ) : null}
              {matchingReasons.length ? null : (
                <p className="mt-3 text-sm">{t("noReasonMatches")}</p>
              )}
              <ul className="mt-2 list-disc pl-5 text-sm">
                {reasonPage.rows.map((reason) => (
                  <li className="break-words" key={reason.id}>
                    {reason.text}
                  </li>
                ))}
              </ul>
              {reasons.length > 25 ? <ListPagination {...reasonPage} label={t("reasons")} /> : null}
            </section>
          ) : null}
          {advanced ? (
            <section className="mt-5 border-t border-[var(--border)] pt-5">
              <h3 className="panel-title">{t("raw")}</h3>
              <TableScroll label={t("raw")} className="mt-2 max-h-96 rounded-lg bg-[var(--muted)]">
                <pre className="p-3 text-xs">{JSON.stringify(row.arguments ?? {}, null, 2)}</pre>
              </TableScroll>
            </section>
          ) : null}
          {pending && !recorded && row.canDecide !== true ? (
            <p className="mt-5 text-sm text-[var(--muted-foreground)]">
              {row.decisionReason
                ? String(row.decisionReason)
                : t(row.canDecide === false ? "cannotDecide" : "eligibilityUnconfirmed")}
            </p>
          ) : null}
          {pending && !recorded && row.canDecide === true && !hasHash ? (
            <p className="mt-5 text-sm text-[var(--muted-foreground)]">{t("hashUnconfirmed")}</p>
          ) : null}
          {pending && !recorded && row.canDecide === true ? (
            <fieldset disabled={held} className="mt-5 border-t border-[var(--border)] pt-1">
              <label className="mt-4 block text-sm" htmlFor="detail-comment">
                {t("comment")}
                <textarea
                  id="detail-comment"
                  className="mt-1 h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                />
              </label>
              {row.stepUpRequired ? (
                <p className="mt-3 text-xs text-[var(--muted-foreground)]">
                  {t("confirmationHelp")}
                </p>
              ) : null}
              <div className="mt-4 flex flex-wrap gap-2">
                <Button disabled={held} type="button" onClick={() => void decide("approve")}>
                  {t("approve")}
                </Button>
                <Button
                  disabled={held}
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
