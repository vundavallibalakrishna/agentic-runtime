/** Availability hint for new work; APIs remain responsible for authorisation. */
export function isAvailableAgent(agent: unknown): boolean {
  if (!agent || typeof agent !== "object") return false;
  const row = agent as { status?: unknown; disabled?: unknown };
  return row.status === "published" && row.disabled === false;
}
