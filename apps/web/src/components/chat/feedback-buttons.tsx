"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export function FeedbackButtons({ messageId, initial }: { messageId: string; initial?: string }) {
  const t = useTranslations("chat");
  const [rating, setRating] = useState(initial ?? "");
  const [error, setError] = useState("");
  if (!messageId || messageId.startsWith("local-")) return null;

  async function send(next: "up" | "down") {
    setError("");
    try {
      await api(`/api/v1/messages/${messageId}/feedback`, {
        method: "PUT",
        body: JSON.stringify({ rating: next, comment: "" }),
      });
      setRating(next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("feedbackError"));
    }
  }

  return (
    <div className="flex items-center gap-1">
      <Button
        aria-pressed={rating === "up"}
        className="h-7 px-2 text-xs font-normal text-[var(--muted-foreground)]"
        onClick={() => void send("up")}
        type="button"
        variant="ghost"
      >
        {t("feedbackUp")}
      </Button>
      <Button
        aria-pressed={rating === "down"}
        className="h-7 px-2 text-xs font-normal text-[var(--muted-foreground)]"
        onClick={() => void send("down")}
        type="button"
        variant="ghost"
      >
        {t("feedbackDown")}
      </Button>
      {error ? <span className="text-xs text-[var(--destructive)]">{error}</span> : null}
    </div>
  );
}
