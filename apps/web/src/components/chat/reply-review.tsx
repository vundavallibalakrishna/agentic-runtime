"use client";

import { ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
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

function when(stamp: string): string {
  const date = new Date(stamp);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/**
 * The line under a reply that says it was written by AI, and whether a person has
 * reviewed it. Once someone accepts the reply it names them and the time instead.
 */
export function ReplyReviewStatus({ review }: { review?: ReplyReview | null }) {
  const t = useTranslations("chat");
  const status = review?.status ?? "unreviewed";
  let text = t("reviewUnreviewed");
  if (status === "accepted") {
    const name = review?.acceptedBy?.name ?? "";
    const time = when(review?.acceptedAt ?? "");
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
export function AcceptReply({
  messageId,
  review,
  disabled = false,
  onAccepted,
}: {
  messageId: string;
  review?: ReplyReview | null;
  disabled?: boolean;
  onAccepted: (review: ReplyReview) => void;
}) {
  const t = useTranslations("chat");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!messageId || messageId.startsWith("local-") || !review?.canAccept) return null;

  async function accept() {
    setBusy(true);
    setError("");
    try {
      await confirmStepUp();
      onAccepted(
        await api<ReplyReview>(`/api/v1/messages/${messageId}:accept`, {
          method: "POST",
          body: JSON.stringify({}),
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error && caught.message ? caught.message : t("acceptError"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button
        aria-busy={busy}
        className="h-7 gap-1.5 px-2 text-xs font-normal text-[var(--muted-foreground)]"
        disabled={busy || disabled}
        onClick={() => void accept()}
        title={t("acceptHint")}
        type="button"
        variant="ghost"
      >
        <ShieldCheck size={13} aria-hidden="true" />
        {busy ? t("accepting") : t("accept")}
      </Button>
      {error ? (
        <span className="text-xs text-[var(--destructive)]" role="alert">
          {error}
        </span>
      ) : null}
    </>
  );
}
