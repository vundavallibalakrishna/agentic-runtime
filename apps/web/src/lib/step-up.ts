import { api } from "@/lib/api";

/** A successful HTTP response must explicitly confirm the session before protected work. */
export async function confirmStepUp(
  unconfirmedMessage?: string,
  signal?: AbortSignal,
): Promise<void> {
  const result = await api<{ steppedUp?: boolean | string }>("/api/v1/auth/step-up", {
    method: "POST",
    signal,
    body: JSON.stringify({ confirmed: true }),
  });
  signal?.throwIfAborted();
  if (result?.steppedUp !== true && result?.steppedUp !== "true") {
    throw new Error(unconfirmedMessage);
  }
}
