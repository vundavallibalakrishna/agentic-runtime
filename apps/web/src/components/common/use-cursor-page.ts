"use client";

import type { Page } from "@ar/api-client/schemas";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, type DisplayError } from "@/lib/api";

type Result<T> = {
  key: string;
  rows: T[];
  next: string | null;
  error: DisplayError;
  loaded: boolean;
};
/** Keep one server page. Search/filter values and page boundaries never fetch the full list. */
export function useCursorPage<T>(
  endpoint: string,
  filters: Record<string, string> = {},
  enabled = true,
  scope = "",
) {
  const t = useTranslations("pagination");
  const filterKey = JSON.stringify(filters),
    [size, setSize] = useState(25),
    key = JSON.stringify([endpoint, filterKey, size, scope]);
  const [position, setPosition] = useState<{
    key: string;
    page: number;
    cursors: (string | null)[];
  }>({ key, page: 1, cursors: [null] });
  useEffect(() => {
    setPosition((previous) =>
      previous.key === key ? previous : { key, page: 1, cursors: [null] },
    );
  }, [key]);
  const page = position.key === key ? position.page : 1,
    cursors = position.key === key ? position.cursors : [null],
    cursor = cursors[page - 1] ?? null,
    requestKey = JSON.stringify([key, cursor]);
  const [result, setResult] = useState<Result<T>>({
      key: "",
      rows: [],
      next: null,
      error: "",
      loaded: false,
    }),
    [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null),
    latest = useRef(requestKey);
  latest.current = requestKey;
  const refresh = useCallback(
    async (quiet = false) => {
      if (!enabled || request.current) return;
      const controller = new AbortController();
      request.current = controller;
      setBusy(!quiet);
      const params = new URLSearchParams(JSON.parse(filterKey) as Record<string, string>);
      params.set("limit", String(size));
      if (cursor) params.set("cursor", cursor);
      try {
        const value = await api<Omit<Page, "items"> & { items: T[] }>(`${endpoint}?${params}`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted || latest.current !== requestKey) return;
        if (
          !Array.isArray(value?.items) ||
          value.items.length > size ||
          (value.hasMore && !value.nextCursor)
        )
          throw new Error(t("invalidPage"));
        setResult({
          key: requestKey,
          rows: value.items.slice(0, size),
          next: value.nextCursor || null,
          error: "",
          loaded: true,
        });
      } catch (caught) {
        if (!controller.signal.aborted && latest.current === requestKey)
          setResult((previous) => ({
            key: requestKey,
            rows:
              previous.key === requestKey &&
              !(
                caught instanceof ApiError &&
                ([401, 403].includes(caught.status) || caught.code === "invalid_cursor")
              )
                ? previous.rows
                : [],
            next:
              previous.key === requestKey &&
              !(
                caught instanceof ApiError &&
                ([401, 403].includes(caught.status) || caught.code === "invalid_cursor")
              )
                ? previous.next
                : null,
            loaded: previous.key === requestKey && previous.loaded,
            error: caught instanceof Error ? caught : t("loadError"),
          }));
      } finally {
        if (request.current === controller) {
          request.current = null;
          setBusy(false);
        }
      }
    },
    [endpoint, filterKey, size, cursor, enabled, requestKey, t],
  );
  useEffect(() => {
    if (!enabled) {
      setResult({ key: "", rows: [], next: null, error: "", loaded: false });
      return;
    }
    const timer = setTimeout(
      () => void refresh(),
      (JSON.parse(filterKey) as Record<string, string>).q ? 150 : 0,
    );
    return () => {
      clearTimeout(timer);
      request.current?.abort();
      request.current = null;
    };
  }, [refresh, enabled, filterKey]);
  const current = result.key === requestKey ? result : null,
    rows = current?.rows ?? [],
    error = current?.error ?? "",
    loading = enabled && (busy || (!current?.loaded && !error));
  return {
    rows,
    error,
    loading,
    refresh,
    page,
    pageSize: size,
    cursor: true as const,
    count: rows.length,
    canNext: Boolean(current?.next),
    disabled: loading || Boolean(error),
    setPage(next: number) {
      if (next === 1) setPosition({ key, page: 1, cursors: [null] });
      else if (next === page + 1 && current?.next)
        setPosition({ key, page: next, cursors: [...cursors.slice(0, page), current.next] });
      else if (next >= 1 && next < page) setPosition({ key, page: next, cursors });
    },
    retry() {
      if (cursor && current?.error instanceof ApiError && current.error.code === "invalid_cursor") {
        setPosition({ key, page: 1, cursors: [null] });
      } else void refresh();
    },
    setPageSize(next: number) {
      setSize(next);
      setPosition({ key: "", page: 1, cursors: [null] });
    },
    setRows(update: (previous: T[]) => T[]) {
      setResult((previous) => ({ ...previous, rows: update(previous.rows).slice(0, size) }));
    },
  };
}
