"use client";

import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActionStatus, DetailState, ErrorMessage } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { DisplayError } from "@/lib/api";
import { ApiError, api } from "@/lib/api";
import { loadSession } from "@/lib/session";

type Tenant = { settings?: { egressAllowlist?: string[] } };
function savedHosts(tenant: Tenant): string[] | null {
  const value = tenant?.settings?.egressAllowlist;
  return Array.isArray(value) && value.every((host) => typeof host === "string" && host)
    ? value
    : null;
}

/** The saved tenant allowlist; changing it does not itself probe a website. */
export function WebAccess() {
  const t = useTranslations("webAccess");
  const [hosts, setHosts] = useState<string[] | null>(null);
  const [host, setHost] = useState("");
  const [canManage, setCanManage] = useState(false);
  const [readDenied, setReadDenied] = useState(false);
  const [loadError, setLoadError] = useState<DisplayError>("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<DisplayError>("");
  const [notice, setNotice] = useState("");
  const [recovery, setRecovery] = useState(false);
  const [query, setQuery] = useState("");
  const readRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);
  const uniqueHosts = useMemo(() => [...new Set(hosts ?? [])], [hosts]);
  const matching = useMemo(
    () =>
      uniqueHosts.filter((name) =>
        name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
      ),
    [uniqueHosts, query],
  );
  const page = usePagedRows(matching, query);
  const locked = busy || loading || recovery || Boolean(loadError) || !canManage;

  const load = useCallback(async () => {
    readRequest.current?.abort();
    const request = new AbortController();
    readRequest.current = request;
    setLoadError("");
    setLoading(true);
    setReadDenied(false);
    try {
      const session = await loadSession();
      if (request.signal.aborted) return false;
      const permissions = session.permissions ?? [];
      if (!permissions.includes("tenant:read")) {
        setCanManage(false);
        setReadDenied(true);
        setHosts(null);
        return false;
      }
      setCanManage(permissions.includes("tenant:manage"));
      const tenant = await api<Tenant>("/api/v1/tenant", { signal: request.signal });
      if (request.signal.aborted) return false;
      const list = savedHosts(tenant);
      if (!list) throw new Error(t("unconfirmed"));
      setHosts(list);
      return true;
    } catch (caught) {
      if (!request.signal.aborted) {
        setLoadError(caught instanceof Error ? caught : t("error"));
        if (caught instanceof ApiError && [401, 403, 404].includes(caught.status)) {
          setCanManage(false);
          setHosts(null);
        }
      }
      return false;
    } finally {
      if (readRequest.current === request) {
        readRequest.current = null;
        setLoading(false);
      }
    }
  }, [t]);

  useEffect(() => {
    void load();
    return () => {
      readRequest.current?.abort();
      actionRequest.current?.abort();
    };
  }, [load]);

  async function refresh() {
    if (actionRequest.current) return;
    if (await load()) {
      setRecovery(false);
      setError("");
    }
  }
  async function save(next: string[], done: string, submittedHost?: string) {
    if (actionRequest.current || readRequest.current || locked || !hosts) return;
    const request = new AbortController();
    actionRequest.current = request;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const saved = await api<Tenant>("/api/v1/tenant", {
        method: "PATCH",
        signal: request.signal,
        body: JSON.stringify({ settings: { egressAllowlist: next } }),
      });
      if (request.signal.aborted) return;
      const list = savedHosts(saved);
      const expected = new Set(next);
      const actual = list ? new Set(list) : null;
      if (
        !actual ||
        actual.size !== expected.size ||
        ![...expected].every((name) => actual.has(name))
      )
        throw new Error(t("unconfirmed"));
      setHosts(list);
      setNotice(done);
      if (submittedHost !== undefined)
        setHost((current) => (current === submittedHost ? "" : current));
    } catch (caught) {
      if (!request.signal.aborted) {
        setError(caught instanceof Error ? caught : t("error"));
        setRecovery(true);
      }
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setBusy(false);
      }
    }
  }
  function add(event: FormEvent) {
    event.preventDefault();
    if (locked || actionRequest.current || readRequest.current || !hosts) return;
    const name = host.trim().toLowerCase();
    if (!name) return;
    if (uniqueHosts.includes(name)) {
      setError(t("already", { host: name }));
      return;
    }
    void save([...hosts, name], t("added", { host: name }), host);
  }

  const status = (
    <ActionStatus
      busy={busy || loading}
      busyLabel={t(busy ? "saving" : "loading")}
      notice={notice}
    />
  );
  return (
    <section aria-labelledby="web-access-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold" id="web-access-title">
          {t("title")}
        </h2>
        <Button
          type="button"
          variant="outline"
          className="size-9 p-0"
          aria-label={t("refresh")}
          title={t("refresh")}
          disabled={busy || loading}
          onClick={() => void refresh()}
        >
          <RefreshCw size={16} aria-hidden="true" />
        </Button>
      </div>
      <p className="mb-4 mt-1 max-w-2xl text-sm leading-relaxed text-[var(--muted-foreground)]">
        {t("body")}
      </p>
      <DetailState
        loading={loading && !hosts}
        error={loadError}
        onRetry={busy ? undefined : () => void refresh()}
      />
      {!hosts ? status : null}
      {recovery ? (
        <p className="mb-2 text-sm text-[var(--muted-foreground)]">{t("recovery")}</p>
      ) : null}
      {error ? (
        <div
          ref={errorRef}
          tabIndex={-1}
          className="mb-4 break-words text-sm text-[var(--destructive)]"
          role="alert"
        >
          <ErrorMessage error={error} />
        </div>
      ) : null}
      {readDenied ? <p className="text-sm">{t("readDenied")}</p> : null}
      {hosts ? (
        <div className="grid gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
          {uniqueHosts.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
          ) : null}
          {uniqueHosts.length > 25 || query ? (
            <div className="flex flex-wrap gap-2">
              <Input
                type="search"
                className="min-w-0 flex-1"
                aria-label={t("search")}
                placeholder={t("search")}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              {query ? (
                <Button type="button" variant="outline" onClick={() => setQuery("")}>
                  {t("clearSearch")}
                </Button>
              ) : null}
            </div>
          ) : null}
          {uniqueHosts.length > 0 && matching.length === 0 ? (
            <p className="text-sm">{t("noMatches")}</p>
          ) : null}
          <ul aria-label={t("listed")} className="grid gap-1">
            {page.rows.map((name) => (
              <li key={name} className="flex items-center justify-between gap-3 text-sm">
                <code className="min-w-0 break-all">{name}</code>
                {canManage ? (
                  <Button
                    aria-label={t("removeNamed", { host: name })}
                    disabled={locked}
                    onClick={() =>
                      void save(
                        (hosts ?? []).filter((item) => item !== name),
                        t("removed", { host: name }),
                      )
                    }
                    type="button"
                    variant="ghost"
                  >
                    {t("remove")}
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
          {uniqueHosts.length > 25 ? <ListPagination {...page} label={t("listed")} /> : null}
          {status}
          {canManage ? (
            <form className="grid gap-1" onSubmit={add}>
              <label className="text-sm font-medium" htmlFor="web-access-host">
                {t("host")}
              </label>
              <div className="flex flex-wrap gap-2">
                <Input
                  aria-describedby="web-access-host-hint"
                  autoCapitalize="none"
                  autoCorrect="off"
                  className="min-w-0 flex-1 basis-full sm:basis-0"
                  disabled={busy || loading || Boolean(loadError)}
                  id="web-access-host"
                  onChange={(event) => {
                    setHost(event.target.value);
                    setNotice("");
                    if (!recovery) setError("");
                  }}
                  spellCheck={false}
                  value={host}
                />
                <Button disabled={locked || !host.trim()} type="submit">
                  {t("add")}
                </Button>
              </div>
              <p
                className="max-w-2xl text-xs leading-relaxed text-[var(--muted-foreground)]"
                id="web-access-host-hint"
              >
                {t("hostHint")}
              </p>
            </form>
          ) : (
            <p className="text-sm">{t("readOnly")}</p>
          )}
        </div>
      ) : null}
    </section>
  );
}
