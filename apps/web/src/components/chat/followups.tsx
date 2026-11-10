"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

export function followupsOf(message: Record<string, unknown>): string[] {
  const content = message.content;
  if (!Array.isArray(content)) return [];
  const prompts: string[] = [];
  for (const part of content) {
    if (!part || typeof part !== "object") continue;
    const row = part as { type?: string; prompts?: unknown };
    if (row.type !== "followups" || !Array.isArray(row.prompts)) continue;
    for (const prompt of row.prompts) {
      if (typeof prompt === "string" && prompt.trim()) prompts.push(prompt.trim());
    }
  }
  return prompts;
}

export function Followups({
  prompts,
  onPick,
}: {
  prompts: string[];
  onPick: (prompt: string) => void;
}) {
  const t = useTranslations("chat");
  if (prompts.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2" data-testid="followups">
      <p className="sr-only">{t("followups")}</p>
      {prompts.map((prompt) => (
        <Button
          className="h-auto whitespace-normal px-3 py-1.5 text-left text-xs font-normal"
          key={prompt}
          onClick={() => onPick(prompt)}
          type="button"
          variant="outline"
        >
          {prompt}
        </Button>
      ))}
    </div>
  );
}
