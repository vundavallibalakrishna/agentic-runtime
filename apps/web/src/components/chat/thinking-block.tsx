"use client";

import { useTranslations } from "next-intl";

export function ThinkingBlock({ text, durationMs }: { text: string; durationMs?: number }) {
  const t = useTranslations("chat");
  const body = text.trim();
  if (!body) return null;
  const seconds = durationMs && durationMs > 0 ? Math.max(1, Math.round(durationMs / 1000)) : 0;
  return (
    <details
      className="mb-3 rounded-xl border border-[var(--border)] bg-[var(--muted)] px-3 py-2 text-sm"
      data-testid="thinking"
    >
      <summary className="cursor-pointer text-[var(--muted-foreground)]">
        {seconds ? t("thoughtFor", { seconds }) : t("thinking")}
      </summary>
      <p className="mt-2 whitespace-pre-wrap leading-relaxed">{body}</p>
    </details>
  );
}
