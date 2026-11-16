import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export type Tone = "neutral" | "success" | "warning" | "danger" | "info";

const tones: Record<Tone, string> = {
  neutral: "border-[var(--border)] bg-[var(--muted)]",
  success: "tone tone-success",
  warning: "tone tone-warning",
  danger: "tone tone-danger",
  info: "tone tone-info",
};

const settled = new Set([
  "published",
  "completed",
  "succeeded",
  "success",
  "active",
  "ok",
  "approved",
  "signed",
  "connected",
  "enabled",
  "indexed",
  "ready",
  "accepted",
  "supported",
]);
const moving = new Set(["running", "queued", "in_progress", "started"]);
const waiting = new Set([
  "draft",
  "paused",
  "pending",
  "proposed",
  "waiting_input",
  "waiting_approval",
]);
const broken = new Set([
  "failed",
  "error",
  "denied",
  "disabled",
  "timed_out",
  "rejected",
  "revoked",
  "not_supported",
]);

/** The tone for a status word the API returns. A word it does not know is neutral. */
export function statusTone(status: string | null | undefined): Tone {
  const word = (status ?? "").toLowerCase();
  if (settled.has(word)) return "success";
  if (moving.has(word)) return "info";
  if (waiting.has(word)) return "warning";
  if (broken.has(word)) return "danger";
  return "neutral";
}

export function Badge({
  className,
  tone = "neutral",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-md border px-2 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
