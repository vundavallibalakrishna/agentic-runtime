"use client";

import { ShieldCheck } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { ErrorMessage } from "@/components/common/detail-state";
import { Button } from "@/components/ui/button";
import type { DisplayError } from "@/lib/api";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { confirmStepUp } from "@/lib/step-up";

/** What the API says about a reply: whether a person accepted this exact text. */
export type ReplyReview = {
  status?: string;
  acceptedBy?: { id?: string; name?: string } | null;
  acceptedAt?: string | null;
  contentHash?: string;
  reviewItemId?: string | null;
  canAccept?: boolean;
};

/**
 * The line under a reply that says it was written by AI, and whether a person has
 * reviewed it. Once someone accepts the reply it names them and the time instead.
 */
export function ReplyReviewStatus({ review }: { review?: ReplyReview | null }) {
  const t = useTranslations("chat");
  const locale = useLocale();
  const status = review?.status ?? "unreviewed";
  let text = t("reviewUnreviewed");
  if (status === "accepted") {
    const name = review?.acceptedBy?.name ?? "";
    const stamp = review?.acceptedAt ?? "";
    const time = Number.isFinite(new Date(stamp).getTime())
      ? formatDateTime(stamp, locale)
      : t("reviewTimeUnavailable");
    text = name ? t("reviewAccepted", { name, time }) : t("reviewAcceptedUnnamed", { time });
  } else if (status === "in_review") {
    text = t("reviewInReview");
  } else if (status === "rejected") {
    text = t("reviewRejected");
  }
  return (
    <span data-review-status={status} data-testid="reply-review">
      <span className="sr-only">{t("reviewStatusLabel")} </span>
      {text}
    </span>
  );
}

/**
 * The Accept action for one reply. It is drawn only when the API says this person may
 * accept the reply now. Accepting confirms it is them first, as signing a review does.
 */
type AcceptReplyProps = {
  messageId: string;
  review?: ReplyReview | null;
  disabled?: boolean;
  onAccepted: (review: ReplyReview) => void;
  onRefresh: () => Promise<void>;
};

export function AcceptReply(props: AcceptReplyProps) {
  return (
    <ReplyAcceptance key={`${props.messageId}:${props.review?.contentHash ?? ""}`} {...props} />
  );
}

function ReplyAcceptance({
  messageId,
  review,
  disabled = false,
  onAccepted,
  onRefresh,
}: AcceptReplyProps) {
  const t = useTranslations("chat");
  const confirmation = useTranslations("detail");
  const requestRef = useRef<AbortController | null>(null);
  const postedRef = useRef(false);
  const [phase, setPhase] = useState<"confirming" | "saving" | "refreshing" | null>(null);
  const [error, setError] = useState<DisplayError>("");
  const [recovery, setRecovery] = useState(false);
  const [recorded, setRecorded] = useState(false);
  const eligible = Boolean(
    messageId && !messageId.startsWith("local-") && review?.canAccept === true,
  );
  useEffect(() => () => requestRef.current?.abort(), []);
  useEffect(() => {
    if (disabled || !eligible) {
      if (requestRef.current && postedRef.current) setRecovery(true);
      requestRef.current?.abort();
      requestRef.current = null;
      setPhase(null);
    }
  }, [disabled, eligible]);

  async function accept() {
    if (!eligible || disabled || requestRef.current || recovery || recorded) return;
    const request = new AbortController();
    requestRef.current = request;
    let posted = false;
    setPhase("confirming");
    setError("");
    try {
      await confirmStepUp(confirmation("stepUpUnconfirmed"), request.signal);
      if (request.signal.aborted) return;
      setPhase("saving");
      posted = true;
      postedRef.current = true;
      const result = await api<ReplyReview>(
        `/api/v1/messages/${encodeURIComponent(messageId)}:accept`,
        {
          method: "POST",
          signal: request.signal,
          body: JSON.stringify({}),
        },
      );
      if (request.signal.aborted) return;
      if (
        (result?.status !== "accepted" && result?.status !== "in_review") ||
        (review?.contentHash && result.contentHash !== review.contentHash)
      )
        throw new Error(t("acceptUnconfirmed"));
      setRecorded(true);
      onAccepted(result);
    } catch (caught) {
      if (!request.signal.aborted) {
        setError(caught instanceof Error && caught.message ? caught.message : t("acceptError"));
        if (posted) setRecovery(true);
      }
    } finally {
      if (requestRef.current === request) {
        requestRef.current = null;
        setPhase(null);
      }
    }
  }

  async function refresh() {
    if (disabled || requestRef.current) return;
    const request = new AbortController();
    requestRef.current = request;
    setPhase("refreshing");
    setError("");
    try {
      await onRefresh();
    } catch (caught) {
      if (!request.signal.aborted) setError(caught instanceof Error ? caught : t("acceptError"));
    } finally {
      if (requestRef.current === request) {
        requestRef.current = null;
        setPhase(null);
      }
    }
  }

  if (!eligible && !recovery) return null;
  const busy = phase !== null;
  return (
    <>
      <Button
        aria-busy={busy}
        className="h-7 gap-1.5 px-2 text-xs font-normal text-[var(--muted-foreground)]"
        disabled={busy || disabled || recovery || recorded}
        onClick={() => void accept()}
        title={t("acceptHint")}
        type="button"
        variant="ghost"
      >
        <ShieldCheck size={13} aria-hidden="true" />
        {phase ? t(`acceptProgress.${phase}`) : recorded ? t("acceptRecorded") : t("accept")}
      </Button>
      {recovery ? (
        <span className="basis-full text-xs text-[var(--muted-foreground)]">
          {t("acceptRecovery")}{" "}
          <Button
            className="h-7 px-2 text-xs"
            type="button"
            variant="outline"
            disabled={busy || disabled}
            onClick={() => void refresh()}
          >
            {t("refreshReviewChat")}
          </Button>
        </span>
      ) : null}
      {error ? (
        <div className="basis-full break-words text-xs text-[var(--destructive)]" role="alert">
          <ErrorMessage error={error} />
        </div>
      ) : null}
    </>
  );
}
