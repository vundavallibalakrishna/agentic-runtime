import { api, type Session } from "@/lib/api";

/**
 * One session read for the shell and the page.
 *
 * Concurrent callers share the request in flight. A success is reused for the
 * same 15 seconds the server gate uses (`AR_SESSION_GATE_TTL_S`), so a navigation
 * does not fetch the session again. This module stays out of the proxy bundle:
 * sharing that file made the dev server rebuild and reload the page. A failure
 * is not reused: the next read asks the API.
 */
export const SESSION_CACHE_TTL_MS = 15_000;

let generation = 0;
let cached: { at: number; value: Session } | null = null;
let pending: Promise<Session> | null = null;

export function clearCachedSession(): void {
  generation += 1;
  cached = null;
  pending = null;
}

export function loadSession(clock: () => number = Date.now): Promise<Session> {
  const at = clock();
  if (cached && at - cached.at < SESSION_CACHE_TTL_MS) return Promise.resolve(cached.value);
  if (pending) return pending;
  const ticket = generation;
  const request = api<Session>("/api/v1/auth/session")
    .then((value) => {
      if (ticket === generation) cached = { at: clock(), value };
      return value;
    })
    .finally(() => {
      if (ticket === generation) pending = null;
    });
  pending = request;
  return request;
}
