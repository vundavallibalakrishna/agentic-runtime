"use client";

import { useTranslations } from "next-intl";

import type { PlanStep } from "@/lib/stream/reducer";

const MARK: Record<
  string,
  { glyph: string; label: "planPending" | "planActive" | "planDone" | "planCancelled" }
> = {
  pending: { glyph: "○", label: "planPending" },
  in_progress: { glyph: "●", label: "planActive" },
  done: { glyph: "✓", label: "planDone" },
  cancelled: { glyph: "–", label: "planCancelled" },
};

export function planItems(value: unknown): PlanStep[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item, index) => {
      if (typeof item === "string" && item) {
        return { id: String(index + 1), title: item, status: "pending" };
      }
      if (item && typeof item === "object" && "title" in item) {
        const row = item as { id?: string; title?: string; status?: string };
        const title = String(row.title ?? "");
        if (!title) return null;
        return {
          id: String(row.id ?? index + 1),
          title,
          status: String(row.status ?? "pending"),
        };
      }
      return null;
    })
    .filter((item): item is PlanStep => item !== null);
}

export function PlanChecklist({ items }: { items: PlanStep[] }) {
  const t = useTranslations("chat");
  if (items.length === 0) return null;
  const current = items.find((step) => step.status === "in_progress");
  return (
    // Closed until a person opens it: the answer is what they came for, the plan is detail.
    <details className="mt-2 text-xs text-[var(--muted-foreground)]" data-testid="plan-checklist">
      <summary className="cursor-pointer select-none">
        {t("planSteps", { count: items.length })}
        {current ? ` · ${current.title}` : ""}
      </summary>
      <ol className="mt-1.5 space-y-1 pl-1">
        {items.map((step) => {
          const mark = MARK[step.status] ?? MARK.pending;
          if (!mark) return null;
          return (
            <li className="flex items-start gap-2" key={`${step.id}-${step.title}`}>
              <span aria-hidden="true" className="w-4 text-[var(--muted-foreground)]">
                {mark.glyph}
              </span>
              <span>
                {step.title}
                <span className="sr-only"> {t(mark.label)}</span>
              </span>
            </li>
          );
        })}
      </ol>
    </details>
  );
}
