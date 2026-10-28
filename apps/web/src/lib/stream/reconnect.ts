import type { StreamState } from "@/lib/stream/reducer";

/** Resume a dropped SSE stream. A finished run is not resumed. */
export function shouldResumeStream(
  status: StreamState["status"],
  attempt: number,
  maxAttempts = 3,
): boolean {
  if (status === "completed" || status === "cancelled" || status === "failed") return false;
  return attempt < maxAttempts;
}

/** Retry transport failures. A 4xx other than 429 is returned to the caller. */
export function shouldResumeStatus(httpStatus: number, attempt: number, maxAttempts = 3): boolean {
  if (attempt >= maxAttempts) return false;
  return httpStatus === 0 || httpStatus === 429 || httpStatus >= 500;
}

export function streamHeaders(lastSeq: number): HeadersInit {
  if (lastSeq <= 0) return {};
  return { "Last-Event-ID": String(lastSeq) };
}

export function waitForResume(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(signal.reason);
      return;
    }
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    signal.addEventListener("abort", onAbort, { once: true });
  });
}
