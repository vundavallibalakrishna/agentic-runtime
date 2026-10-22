"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Meter } from "@/components/usage/meter";
import { api } from "@/lib/api";

type MineQuota = { id?: string; metric: string; period: string; limit: number; used: number };
type Mine = {
  currency?: string;
  totals?: { quantity?: number; costMicros?: number };
  quotas?: MineQuota[];
};

type Identity = {
  id: string;
  externalUserId?: string;
  matchMethod?: string;
};

export function ProfileScreen() {
  const t = useTranslations("profile");
  const [rows, setRows] = useState<Identity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [token, setToken] = useState("");
  const [usage, setUsage] = useState<Mine | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [page, mine] = await Promise.all([
        api<{ items: Identity[] }>("/api/v1/me/channel-identities"),
        api<Mine>("/api/v1/me/usage").catch(() => null),
      ]);
      setRows(page.items ?? []);
      setUsage(mine);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const link = params.get("link");
    if (link) {
      setToken(link);
    }
    void load();
  }, [load]);

  async function linkAccount() {
    setError("");
    setNotice("");
    try {
      await api("/api/v1/me/channel-identities:link", {
        method: "POST",
        body: JSON.stringify({ token }),
      });
      setToken("");
      setNotice(t("linked"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  async function unlink(id: string) {
    setError("");
    try {
      await api(`/api/v1/me/channel-identities/${id}`, { method: "DELETE" });
      setNotice(t("unlinked"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  return (
    <AppShell>
      <PageHeader body={t("body")} title={t("title")} />
      {error ? (
        <p className="mb-3 text-sm text-[var(--destructive)]" role="alert">
          {error}{" "}
          <Button onClick={() => void load()} type="button" variant="outline">
            {t("retry")}
          </Button>
        </p>
      ) : null}
      {notice ? <p className="mb-3 text-sm text-[var(--muted-foreground)]">{notice}</p> : null}
      <section className="mb-6 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-sm font-medium">{t("usageTitle")}</h2>
        <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("usageBody")}</p>
        {usage ? (
          <p className="mt-3 text-sm">
            {(usage.totals?.quantity ?? 0).toLocaleString()} · {usage.totals?.costMicros ?? 0}{" "}
            {usage.currency}
          </p>
        ) : (
          <p className="mt-3 text-sm text-[var(--muted-foreground)]">{t("usageEmpty")}</p>
        )}
        <ul className="mt-3 space-y-3">
          {(usage?.quotas ?? []).map((row) => (
            <li key={row.id ?? `${row.metric}-${row.period}-${row.limit}`}>
              <p className="mb-1 text-sm">
                {row.metric} · {row.used.toLocaleString()} / {row.limit.toLocaleString()}
              </p>
              <Meter limit={row.limit} used={row.used} />
            </li>
          ))}
        </ul>
      </section>
      <section className="mb-6 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <label className="block text-sm" htmlFor="link-code">
          {t("code")}
        </label>
        <Input
          className="mt-1 max-w-xl"
          id="link-code"
          onChange={(event) => setToken(event.target.value)}
          value={token}
        />
        <Button className="mt-3" disabled={!token} onClick={() => void linkAccount()} type="button">
          {t("link")}
        </Button>
      </section>
      {loading ? <Skeleton className="h-16 w-full" /> : null}
      {!loading && rows.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
      ) : null}
      <ul className="space-y-3">
        {rows.map((row) => (
          <li
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
            key={row.id}
          >
            <div>
              <h2 className="text-sm font-medium">{row.externalUserId}</h2>
              <p className="text-sm text-[var(--muted-foreground)]">{row.matchMethod}</p>
            </div>
            <Button onClick={() => void unlink(row.id)} type="button" variant="outline">
              {t("unlink")}
            </Button>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
