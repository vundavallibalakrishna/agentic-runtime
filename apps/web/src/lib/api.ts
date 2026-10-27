export type Session = {
  user?: { id?: string; email?: string; displayName?: string };
  tenant?: { name?: string; slug?: string; id?: string };
  permissions?: string[];
  roles?: string[];
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|; )ar_csrf=([^;]*)/);
  return match?.[1] ? decodeURIComponent(match[1]) : "";
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData) && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const token = csrfToken();
  if (token) {
    headers.set("x-csrf-token", token);
  }
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const problem = (await response.json()) as { detail?: string };
      detail = problem.detail ?? detail;
    } catch {
      detail = response.statusText;
    }
    throw new ApiError(detail || "Request failed", response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
