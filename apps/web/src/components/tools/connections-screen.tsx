"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus } from "@/components/common/detail-state";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Row = Record<string, unknown>;

export function ConnectionsScreen() {
  const t = useTranslations("connections");
  const [grants, setGrants] = useState<Row[]>([]);
  const [providers, setProviders] = useState<Row[]>([]);
  const [data, setData] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [link, setLink] = useState("");
  const [pending, setPending] = useState<{
    providerId: string;
    state: string;
    local: boolean;
  } | null>(null);
  const [code, setCode] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [grantPage, providerPage, dataPage] = await Promise.all([
        api<{ items: Row[] }>("/api/v1/connections"),
        api<{ items: Row[] }>("/api/v1/credential-providers"),
        api<{ items: Row[] }>("/api/v1/data-connections"),
      ]);
      setGrants(grantPage.items ?? []);
      setProviders(providerPage.items ?? []);
      setData(dataPage.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function connect(providerId: string, local: boolean) {
    if (busy) return;
    setBusy(true);
    try {
      setError("");
      const started = await api<{ authorizeUrl?: string; state?: string }>(
        `/api/v1/connections/${providerId}:start`,
        {
          method: "POST",
        },
      );
      setLink(started.authorizeUrl ?? "");
      setPending({ providerId, state: started.state ?? "", local });
      setCode(local ? t("workspaceCode") : "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function finish(nextCode: string) {
    if (busy || !pending?.state) return;
    const value = nextCode.trim();
    if (!value) {
      setError(t("code"));
      return;
    }
    setBusy(true);
    try {
      setError("");
      const params = new URLSearchParams({ code: value, state: pending.state });
      await api(`/api/v1/connections/oauth/callback?${params.toString()}`);
      setPending(null);
      setLink("");
      setCode("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function disconnect(grantId: string) {
    if (busy) return;
    setBusy(true);
    try {
      setError("");
      await api(`/api/v1/connections/${grantId}`, { method: "DELETE" });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  const connected = new Set(
    grants.filter((row) => row.status === "active").map((row) => String(row.providerId)),
  );

  return (
    <AppShell>
      <ActionStatus busy={busy} />
      <fieldset disabled={busy} className="min-w-0">
        <PageHeader
          body={t("body")}
          title={t("title")}
          actions={
            <Button asChild variant="outline">
              <a href="/tools">{t("back")}</a>
            </Button>
          }
        />
        {loading ? (
          <div aria-busy="true">
            <Skeleton className="h-24 w-full" />
            <p className="sr-only">{t("loading")}</p>
          </div>
        ) : null}
        {error ? (
          <div role="alert">
            <p>{error}</p>
            <Button onClick={() => void load()} type="button" variant="outline">
              {t("retry")}
            </Button>
          </div>
        ) : null}
        {!loading && !error && providers.length === 0 && data.length === 0 ? (
          <EmptyState title={t("empty")} />
        ) : null}
        <ul className="mb-8 grid gap-4 md:grid-cols-2">
          {providers.map((provider) => {
            const id = String(provider.id);
            const grant = grants.find(
              (row) => String(row.providerId) === id && row.status === "active",
            );
            return (
              <li
                className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
                key={id}
              >
                <h2 className="text-lg font-medium">{String(provider.name)}</h2>
                <p className="text-sm text-[var(--muted-foreground)]">
                  {connected.has(id) ? t("connected") : String(provider.slug)}
                </p>
                <div className="mt-4">
                  {grant ? (
                    <Button
                      onClick={() => void disconnect(String(grant.id))}
                      type="button"
                      variant="outline"
                    >
                      {t("disconnect")}
                    </Button>
                  ) : (
                    <Button
                      onClick={() =>
                        void connect(id, String(provider.tokenUrl || "").startsWith("memory://"))
                      }
                      type="button"
                    >
                      {t("connect")}
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
        {link ? (
          <p role="status">
            <a href={link}>{link}</a>
          </p>
        ) : null}
        {pending ? (
          <form
            className="mb-8 space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
            onSubmit={(event) => {
              event.preventDefault();
              void finish(code);
            }}
          >
            <h2 className="text-base font-semibold">{t("finishTitle")}</h2>
            <p className="text-sm text-[var(--muted-foreground)]">{t("codeHint")}</p>
            <label className="block text-sm" htmlFor="connection-code">
              {t("code")}
              <input
                className="mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
                id="connection-code"
                onChange={(event) => setCode(event.target.value)}
                value={code}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <Button type="submit">{t("finish")}</Button>
              {pending.local ? (
                <Button
                  onClick={() => void finish(t("workspaceCode"))}
                  type="button"
                  variant="outline"
                >
                  {t("connectAsMe")}
                </Button>
              ) : null}
            </div>
          </form>
        ) : null}
        <h2 className="mb-2 text-lg font-medium">{t("data")}</h2>
        <ul className="grid gap-4 md:grid-cols-2">
          {data.map((row) => (
            <li
              className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
              key={String(row.id)}
            >
              <h3 className="font-medium">{String(row.name)}</h3>
              <p className="text-sm text-[var(--muted-foreground)]">{String(row.engine)}</p>
            </li>
          ))}
        </ul>
      </fieldset>
    </AppShell>
  );
}
