"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Tenant = { settings?: { egressAllowlist?: string[] } };
type Session = { permissions?: string[] };

/**
 * The hosts the organisation's tools may reach. A host that is not listed is refused
 * before anything is sent. An agent can be limited to fewer of these hosts, never more.
 */
export function WebAccess() {
  const t = useTranslations("webAccess");
  const [hosts, setHosts] = useState<string[] | null>(null);
  const [host, setHost] = useState("");
  const [canManage, setCanManage] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoadError("");
    try {
      const session = await api<Session>("/api/v1/auth/session");
      setCanManage((session.permissions ?? []).includes("tenant:manage"));
      const tenant = await api<Tenant>("/api/v1/tenant");
      setHosts(tenant.settings?.egressAllowlist ?? []);
    } catch (caught) {
      setLoadError(caught instanceof Error ? caught.message : t("error"));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save(next: string[], done: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const saved = await api<Tenant>("/api/v1/tenant", {
        method: "PATCH",
        body: JSON.stringify({ settings: { egressAllowlist: next } }),
      });
      setHosts(saved.settings?.egressAllowlist ?? next);
      setNotice(done);
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    const name = host.trim().toLowerCase();
    if (!hosts || !name) return;
    if (hosts.includes(name)) {
      setError(t("already", { host: name }));
      return;
    }
    if (await save([...hosts, name], t("added", { host: name }))) setHost("");
  }

  return (
    <section aria-labelledby="web-access-title" className="mt-10">
      <h2 className="text-sm font-semibold" id="web-access-title">
        {t("title")}
      </h2>
      <p className="mb-4 mt-1 max-w-2xl text-sm leading-relaxed text-[var(--muted-foreground)]">
        {t("body")}
      </p>
      {loadError ? (
        <p role="alert" className="text-sm">
          {loadError}{" "}
          <Button type="button" variant="ghost" onClick={() => void load()}>
            {t("retry")}
          </Button>
        </p>
      ) : null}
      {!hosts && !loadError ? (
        <div aria-busy="true">
          <span className="sr-only">{t("loading")}</span>
          <Skeleton className="h-24 w-full" />
        </div>
      ) : null}
      {hosts ? (
        <div className="grid gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
          {hosts.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
          ) : (
            <ul aria-label={t("listed")} className="grid gap-1">
              {hosts.map((name) => (
                <li key={name} className="flex items-center justify-between gap-3 text-sm">
                  <code>{name}</code>
                  {canManage ? (
                    <Button
                      aria-label={t("removeNamed", { host: name })}
                      disabled={busy}
                      onClick={() =>
                        void save(
                          hosts.filter((item) => item !== name),
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
          )}
          {canManage ? (
            <form className="grid gap-1" onSubmit={(event) => void add(event)}>
              <label className="text-sm font-medium" htmlFor="web-access-host">
                {t("host")}
              </label>
              <div className="flex flex-wrap gap-2">
                <input
                  aria-describedby="web-access-host-hint"
                  autoCapitalize="none"
                  autoCorrect="off"
                  className="min-w-64 flex-1 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
                  disabled={busy}
                  id="web-access-host"
                  onChange={(event) => setHost(event.target.value)}
                  spellCheck={false}
                  value={host}
                />
                <Button disabled={busy || !host.trim()} type="submit">
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
          {error ? (
            <p className="text-sm text-[var(--destructive)]" role="alert">
              {error}
            </p>
          ) : null}
          {notice ? (
            <p className="text-sm" role="status">
              {notice}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
