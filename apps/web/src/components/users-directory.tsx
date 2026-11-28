"use client";

import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DetailState } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TableScroll } from "@/components/ui/table";
import { type UserRow, UsersPanel, useStatusLabel } from "@/components/users-panel";
import { ApiError, api, type DisplayError } from "@/lib/api";
import { loadSession } from "@/lib/session";

function isUser(value: unknown): value is UserRow {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  return (
    typeof row.id === "string" &&
    Boolean(row.id.trim()) &&
    typeof row.email === "string" &&
    Boolean(row.email.trim()) &&
    typeof row.displayName === "string" &&
    typeof row.status === "string" &&
    Boolean(row.status.trim()) &&
    (row.lastLoginAt === null ||
      (typeof row.lastLoginAt === "string" &&
        /(?:Z|[+-]\d{2}:\d{2})$/i.test(row.lastLoginAt) &&
        Number.isFinite(new Date(row.lastLoginAt).getTime())))
  );
}

export function UsersDirectory() {
  const t = useTranslations("admin");
  const finder = useTranslations("directory");
  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<DisplayError>("");
  const [allowed, setAllowed] = useState<boolean | null>(null);
  // Suspending needs users:manage. Someone who may only read the list sees no actions.
  const [manage, setManage] = useState(false);
  const [selfId, setSelfId] = useState<string | undefined>(undefined);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const request = useRef<AbortController | null>(null);
  const search = useRef<HTMLInputElement>(null);
  const load = useCallback(async () => {
    if (request.current) return;
    const active = new AbortController();
    request.current = active;
    setLoading(true);
    setError("");
    try {
      const session = await loadSession();
      if (active.signal.aborted) return;
      const permissions = session.permissions ?? [];
      const canRead = permissions.includes("users:read");
      setAllowed(canRead);
      setManage(permissions.includes("users:manage"));
      setSelfId(session.user?.id);
      if (!canRead) {
        setUsers(null);
        return;
      }
      const body = await api<{ items: unknown[] }>("/api/v1/users", { signal: active.signal });
      if (active.signal.aborted) return;
      if (!body || !Array.isArray(body.items) || !body.items.every(isUser))
        throw new Error(finder("metadataError"));
      setUsers(body.items);
    } catch (caught) {
      if (!active.signal.aborted) {
        setError(caught instanceof Error ? caught : t("error"));
        if (caught instanceof ApiError && [401, 403].includes(caught.status)) {
          setAllowed(false);
          setUsers(null);
        }
      }
    } finally {
      if (request.current === active) {
        request.current = null;
        setLoading(false);
      }
    }
  }, [finder, t]);
  useEffect(() => {
    void load();
    return () => {
      request.current?.abort();
      request.current = null;
    };
  }, [load]);

  const change = useCallback(
    async (user: UserRow, next: "active" | "suspended") => {
      await api(`/api/v1/users/${encodeURIComponent(user.id)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: next }),
      });
      await load();
    },
    [load],
  );
  const statusLabel = useStatusLabel();

  const statuses = useMemo(
    () => [...new Set([status, ...(users ?? []).map((row) => row.status)])].filter(Boolean).sort(),
    [users, status],
  );
  const matching = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return (users ?? []).filter(
      (user) =>
        (!status || user.status === status) &&
        `${user.displayName} ${user.email}`.toLocaleLowerCase().includes(term),
    );
  }, [users, query, status]);
  const pagination = usePagedRows(matching, JSON.stringify([query, status]));

  return (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm leading-relaxed text-[var(--muted-foreground)]">
          {finder("help")}
        </p>
        <Button
          className="inline-flex items-center gap-2"
          type="button"
          variant="outline"
          disabled={loading}
          onClick={() => void load()}
        >
          <RefreshCw size={16} aria-hidden="true" />
          {finder("refresh")}
        </Button>
      </div>
      {allowed === false ? <p className="mb-5 text-sm">{t("forbidden")}</p> : null}
      <DetailState
        loading={loading && users === null}
        error={error}
        onRetry={loading ? undefined : () => void load()}
      />
      {users !== null && allowed ? (
        <>
          {loading || error ? (
            <p className="mb-4 text-sm text-[var(--muted-foreground)]" role="status">
              {finder(loading ? "refreshing" : "retained")}
            </p>
          ) : null}
          {users.length ? (
            <>
              <div className="mb-5 grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(10rem,auto)_auto]">
                <label className="min-w-0 text-sm" htmlFor="user-search">
                  <span className="mb-1 block">{finder("search")}</span>
                  <Input
                    id="user-search"
                    ref={search}
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                  />
                </label>
                <div className="min-w-0 text-sm">
                  <label className="mb-1 block" htmlFor="user-status">
                    {finder("status")}
                  </label>
                  <select
                    id="user-status"
                    className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
                    value={status}
                    onChange={(event) => setStatus(event.target.value)}
                  >
                    <option value="">{finder("allStatuses")}</option>
                    {statuses.map((value) => (
                      <option key={value} value={value}>
                        {statusLabel(value)}
                      </option>
                    ))}
                  </select>
                </div>
                {query || status ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setQuery("");
                      setStatus("");
                      search.current?.focus();
                    }}
                  >
                    {finder("clear")}
                  </Button>
                ) : null}
              </div>
              {matching.length ? (
                <>
                  <p className="mb-2 text-xs text-[var(--muted-foreground)] sm:hidden">
                    {finder("tableScrollHelp")}
                  </p>
                  <TableScroll
                    className="rounded-xl border border-[var(--border)] bg-[var(--card)]"
                    label={t("usersTitle")}
                  >
                    <UsersPanel
                      onStatus={manage ? change : undefined}
                      selfId={selfId}
                      users={pagination.rows}
                    />
                  </TableScroll>
                </>
              ) : (
                <EmptyState title={finder("noMatches")} />
              )}
              <ListPagination {...pagination} label={t("usersTitle")} />
            </>
          ) : (
            <EmptyState title={t("empty")} />
          )}
        </>
      ) : null}
    </>
  );
}
