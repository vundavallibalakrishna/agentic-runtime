import { act, renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import messages from "@/messages/en.json";
import { server } from "@/test/server";
import { useCursorPage } from "./use-cursor-page";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}
const endpoint = "/api/v1/cursor-test";

it("requests one bounded page, navigates cursors and resets search and account scope", async () => {
  const requests: URLSearchParams[] = [];
  server.use(
    http.get(`*${endpoint}`, ({ request }) => {
      const params = new URL(request.url).searchParams;
      requests.push(params);
      return HttpResponse.json({
        items: [{ id: params.get("q") || params.get("cursor") || "first" }],
        hasMore: !params.has("cursor"),
        nextCursor: params.has("cursor") ? null : "second",
      });
    }),
  );
  const { result, rerender } = renderHook(
    ({ q, scope }) => useCursorPage<{ id: string }>(endpoint, { q }, true, scope),
    { wrapper, initialProps: { q: "", scope: "alice" } },
  );
  await waitFor(() => expect(result.current.rows[0]?.id).toBe("first"));
  expect(requests).toHaveLength(1);
  expect(requests[0]?.get("limit")).toBe("25");
  act(() => result.current.setPage(2));
  await waitFor(() => expect(result.current.rows[0]?.id).toBe("second"));
  expect(requests[1]?.get("cursor")).toBe("second");
  act(() => result.current.setPage(1));
  await waitFor(() => expect(result.current.rows[0]?.id).toBe("first"));
  act(() => result.current.setPage(2));
  await waitFor(() => expect(result.current.rows[0]?.id).toBe("second"));
  rerender({ q: "older record", scope: "alice" });
  expect(result.current.rows).toEqual([]);
  await waitFor(() => expect(result.current.rows[0]?.id).toBe("older record"));
  expect(requests.at(-1)?.has("cursor")).toBe(false);
  rerender({ q: "", scope: "alice" });
  await waitFor(() => expect(result.current.rows[0]?.id).toBe("first"));
  expect(result.current.page).toBe(1);
  act(() => result.current.setPage(2));
  await waitFor(() => expect(result.current.rows[0]?.id).toBe("second"));
  rerender({ q: "", scope: "bob" });
  expect(result.current.rows).toEqual([]);
  await waitFor(() => expect(result.current.rows[0]?.id).toBe("first"));
  expect(result.current.page).toBe(1);
});

it("retains the current page on a transient failure, clears protected data and restarts expired cursors", async () => {
  let failure = "";
  server.use(
    http.get(`*${endpoint}`, ({ request }) =>
      failure
        ? HttpResponse.json(
            { code: failure, detail: "Request rejected" },
            { status: failure === "unavailable" ? 503 : failure === "invalid_cursor" ? 400 : 401 },
          )
        : HttpResponse.json({
            items: [{ id: new URL(request.url).searchParams.get("cursor") || "first" }],
            hasMore: true,
            nextCursor: "second",
          }),
    ),
  );
  const { result } = renderHook(() => useCursorPage<{ id: string }>(endpoint), { wrapper });
  await waitFor(() => expect(result.current.rows).toHaveLength(1));
  failure = "unavailable";
  await act(() => result.current.refresh());
  expect(result.current.rows).toHaveLength(1);
  expect(result.current.error).toBeInstanceOf(ApiError);
  failure = "session_expired";
  await act(() => result.current.refresh());
  expect(result.current.rows).toEqual([]);
  failure = "";
  await act(() => result.current.refresh());
  act(() => result.current.setPage(2));
  await waitFor(() => expect(result.current.rows[0]?.id).toBe("second"));
  failure = "invalid_cursor";
  await act(() => result.current.refresh());
  expect(result.current.rows).toEqual([]);
  failure = "";
  act(() => result.current.retry());
  await waitFor(() => expect(result.current.rows[0]?.id).toBe("first"));
  expect(result.current.page).toBe(1);
});

it.each([
  { items: Array.from({ length: 26 }, (_, id) => ({ id })) },
  { items: [], hasMore: true, nextCursor: null },
  { items: null },
])("rejects a malformed or unbounded server page", async (body) => {
  server.use(http.get(`*${endpoint}`, () => HttpResponse.json(body)));
  const { result } = renderHook(() => useCursorPage(endpoint), { wrapper });
  await waitFor(() => expect(result.current.error).toBeTruthy());
  expect(result.current.rows).toEqual([]);
  expect(result.current.canNext).toBe(false);
});

it("discards an old response when a search changes while it is pending", async () => {
  let release: (() => void) | undefined;
  let started = false;
  server.use(
    http.get(`*${endpoint}`, async ({ request }) => {
      const q = new URL(request.url).searchParams.get("q");
      if (!q) {
        started = true;
        await new Promise<void>((resolve) => {
          release = resolve;
        });
      }
      return HttpResponse.json({ items: [{ id: q || "obsolete" }] });
    }),
  );
  const { result, rerender } = renderHook(
    ({ q }) => useCursorPage<{ id: string }>(endpoint, { q }),
    { wrapper, initialProps: { q: "" } },
  );
  await waitFor(() => expect(started).toBe(true));
  rerender({ q: "current" });
  await waitFor(() => expect(result.current.rows[0]?.id).toBe("current"));
  await act(async () => release?.());
  expect(result.current.rows[0]?.id).toBe("current");
});
