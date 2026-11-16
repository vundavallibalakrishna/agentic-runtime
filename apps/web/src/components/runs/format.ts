export const liveStatuses = ["queued", "running", "waiting_input", "waiting_approval"];

/** How long a run has taken, in whole seconds; empty when it has not started. */
export function durationLabel(run: { startedAt?: string | null; endedAt?: string | null }) {
  const start = Date.parse(run.startedAt || "");
  if (!start) return "";
  const end = Date.parse(run.endedAt || "") || Date.now();
  return `${Math.max(0, Math.round((end - start) / 1000))}s`;
}
