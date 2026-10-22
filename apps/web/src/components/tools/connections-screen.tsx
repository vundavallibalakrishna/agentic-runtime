"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
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
  const [loading, setLoading] = useState(true);
  const [link, setLink] = useState("");

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

  async function connect(providerId: string) {
    setError("");
    const started = await api<{ authorizeUrl?: string }>(
      `/api/v1/connections/${providerId}:start`,
      {
        method: "POST",
      },
    );
    setLink(started.authorizeUrl ?? "");
  }

  async function disconnect(grantId: string) {
    setError("");
    await api(`/api/v1/connections/${grantId}`, { method: "DELETE" });
    await load();
  }

  const connected = new Set(
    grants.filter((row) => row.status === "active").map((row) => String(row.providerId)),
  );

  return (
    <AppShell>
      <PageHeader body={t("body")} title={t("title")} />
      <a className="mb-4 inline-block text-sm underline" href="/tools">
        {t("back")}
      </a>
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
      {!loading && providers.length === 0 && data.length === 0 ? <p>{t("empty")}</p> : null}
      <ul className="mb-8 grid gap-3">
        {providers.map((provider) => {
          const id = String(provider.id);
          const grant = grants.find(
            (row) => String(row.providerId) === id && row.status === "active",
          );
          return (
            <li
              className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3"
              key={id}
            >
              <h2 className="text-lg font-medium">{String(provider.name)}</h2>
              <p className="text-sm text-[var(--muted-foreground)]">
                {connected.has(id) ? t("connected") : String(provider.slug)}
              </p>
              {grant ? (
                <Button
                  onClick={() => void disconnect(String(grant.id))}
                  type="button"
                  variant="outline"
                >
                  {t("disconnect")}
                </Button>
              ) : (
                <Button onClick={() => void connect(id)} type="button">
                  {t("connect")}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
      {link ? (
        <p role="status">
          <a href={link}>{link}</a>
        </p>
      ) : null}
      <h2 className="mb-2 text-lg font-medium">{t("data")}</h2>
      <ul className="grid gap-2">
        {data.map((row) => (
          <li className="rounded-xl border border-[var(--border)] px-4 py-3" key={String(row.id)}>
            <h3 className="font-medium">{String(row.name)}</h3>
            <p className="text-sm text-[var(--muted-foreground)]">{String(row.engine)}</p>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
