"use client";

import { useTranslations } from "next-intl";

import { MarkdownView } from "@/components/chat/markdown-view";
import { Button } from "@/components/ui/button";

/**
 * A reply the agent could not finish. It is drawn as a failure, with the reason the run
 * gave and a way to try again, never as an answer.
 */
export function FailedReply({
  said,
  reason,
  onRetry,
  busy,
}: {
  said: string;
  reason: string;
  onRetry?: () => void;
  busy: boolean;
}) {
  const t = useTranslations("chat");
  return (
    <div>
      {said ? <MarkdownView text={said} /> : null}
      <div
        className="mt-2 rounded-xl border border-[var(--destructive)]/40 bg-[var(--card)] p-4"
        role="alert"
      >
        <p className="text-sm font-medium">{t("failedTitle")}</p>
        <p className="mt-1 text-sm text-[var(--muted-foreground)]">{reason || t("runFailed")}</p>
        {onRetry ? (
          <Button className="mt-3" disabled={busy} onClick={onRetry} type="button">
            {t("tryAgain")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
