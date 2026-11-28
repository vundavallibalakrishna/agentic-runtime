export type Session = {
  user?: { id?: string; email?: string; displayName?: string };
  tenant?: { name?: string; slug?: string; id?: string };
  permissions?: string[];
  roles?: string[];
  features?: Record<string, boolean>;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** A 429 is a pause, not a signed-out session. */
/** Too many requests, as opposed to another 429 such as a used-up quota, which says what it is. */
export function isRateLimited(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.code === "rate_limited" || (error.status === 429 && !error.code))
  );
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|; )ar_csrf=([^;]*)/);
  return match?.[1] ? decodeURIComponent(match[1]) : "";
}

// Dev renders each effect twice, back to back, before the first response arrives.
// Those identical reads share one request. A later read, or any write, goes to the API.
const inflightGets = new Map<string, Promise<unknown>>();

export function clearInflightGets(): void {
  inflightGets.clear();
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  if (method === "GET" && !init?.body && !init?.signal) {
    const existing = inflightGets.get(path);
    if (existing) return existing as Promise<T>;
    const promise = send<T>(path, init).finally(() => {
      if (inflightGets.get(path) === promise) inflightGets.delete(path);
    });
    inflightGets.set(path, promise);
    return promise;
  }
  return send<T>(path, init);
}

async function send<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData) && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const token = csrfToken();
  if (token) {
    headers.set("x-csrf-token", token);
  }
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  if (!response.ok) throw await readApiError(response);
  if (response.status === 204) {
    return undefined as T;
  }
  const body = await response.text();
  return body.trim() ? (JSON.parse(body) as T) : (undefined as T);
}

/** Shared error decoding for JSON requests and existing file downloads. */
async function readApiError(response: Response): Promise<ApiError> {
  let detail = response.statusText;
  let code = "";
  try {
    const problem = (await response.json()) as { detail?: unknown; code?: unknown };
    if (typeof problem.detail === "string" && problem.detail) detail = problem.detail;
    if (typeof problem.code === "string") code = problem.code;
  } catch {
    detail = response.statusText;
  }
  return new ApiError(detail || "Request failed", response.status, code);
}

/** Presentation retains the original error; request and authorisation behaviour stay with callers. */
export type DisplayError = string | Error;
export type ErrorGuidance = "csrf" | "unauthenticated" | "rateLimited" | "unavailable" | "internal";

export function apiErrorGuidance(error: DisplayError): ErrorGuidance | null {
  if (!(error instanceof ApiError)) return null;
  if (error.code === "csrf_failed") return "csrf";
  if (error.code === "unauthenticated" || error.status === 401) return "unauthenticated";
  if (isRateLimited(error)) return "rateLimited";
  if (["unavailable", "upstream_error", "upstream_timeout"].includes(error.code))
    return "unavailable";
  if (error.code === "internal_error") return "internal";
  return null;
}
