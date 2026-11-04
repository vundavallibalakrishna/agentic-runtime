"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus } from "@/components/common/detail-state";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  const [service, setService] = useState<Row[]>([]);
  const [serviceName, setServiceName] = useState("github");
  const [serviceKind, setServiceKind] = useState("bearer");
  const [serviceSecret, setServiceSecret] = useState("");
  const [serviceHeader, setServiceHeader] = useState("Authorization");
  const [serviceUser, setServiceUser] = useState("");
  const [tokenUrl, setTokenUrl] = useState("");
  const [authorizeUrl, setAuthorizeUrl] = useState("");
  const [clientId, setClientId] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [probeUrl, setProbeUrl] = useState("");
  const [notice, setNotice] = useState("");
  const [dbName, setDbName] = useState("");
  const [dbEngine, setDbEngine] = useState("postgres");
  const [dbDsn, setDbDsn] = useState("");
  const [dbSchemas, setDbSchemas] = useState("public");
  const [dbTables, setDbTables] = useState("");
  const [dbRows, setDbRows] = useState(1000);
  const [dbTimeout, setDbTimeout] = useState(30);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [grantPage, providerPage, dataPage] = await Promise.all([
        api<{ items: Row[] }>("/api/v1/connections"),
        api<{ items: Row[] }>("/api/v1/credential-providers"),
        api<{ items: Row[] }>("/api/v1/data-connections"),
      ]);
      const servicePage = await api<{ items?: Row[] }>("/api/v1/service-connections").catch(() => ({
        items: [],
      }));
      setGrants(grantPage.items ?? []);
      setProviders(providerPage.items ?? []);
      setData(dataPage.items ?? []);
      setService(servicePage.items ?? []);
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
    if (busy) return;
    setBusy(true);
    try {
      setError("");
      const started = await api<{ authorizeUrl?: string }>(
        `/api/v1/connections/${providerId}:start`,
        {
          method: "POST",
        },
      );
      setLink(started.authorizeUrl ?? "");
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

  async function createService() {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("/api/v1/service-connections", {
        method: "POST",
        body: JSON.stringify({
          name: serviceName.trim(),
          kind: serviceKind,
          secret: serviceSecret,
          headerName: serviceHeader,
          username: serviceUser,
          tokenUrl,
          authorizeUrl,
          clientId,
          expiresAt: expiresAt || undefined,
          probeUrl,
        }),
      });
      setServiceSecret("");
      setNotice(t("serviceSaved"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function testService(id: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ ok?: boolean; status?: number; error?: string | null }>(
        `/api/v1/service-connections/${id}:test`,
        { method: "POST", body: JSON.stringify({ url: probeUrl }) },
      );
      setNotice(result.ok ? t("serviceTested") : result.error || t("error"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function rotateService(id: string) {
    if (busy || !serviceSecret) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/service-connections/${id}:rotate`, {
        method: "POST",
        body: JSON.stringify({ secret: serviceSecret }),
      });
      setServiceSecret("");
      setNotice(t("serviceRotated"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function saveDatabase() {
    if (busy || !dbName.trim() || !dbDsn.trim()) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = await api<{ id: string }>("/api/v1/data-connections", {
        method: "POST",
        body: JSON.stringify({
          name: dbName.trim(),
          engine: dbEngine,
          dsn: dbDsn,
          allowlist: {
            schemas: dbSchemas
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
            tables: dbTables
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
          },
          rowLimit: dbRows,
          statementTimeoutS: dbTimeout,
        }),
      });
      setDbDsn("");
      setNotice(t("databaseSaved"));
      await load();
      const tested = await api<{ ok?: boolean }>(`/api/v1/data-connections/${created.id}:test`, {
        method: "POST",
        body: "{}",
      });
      setNotice(tested.ok ? t("databaseTested") : t("databaseSaved"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function testDatabase(id: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const tested = await api<{ ok?: boolean }>(`/api/v1/data-connections/${id}:test`, {
        method: "POST",
        body: "{}",
      });
      setNotice(tested.ok ? t("databaseTested") : t("error"));
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
        <section className="mb-8 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
          <h2 className="text-lg font-medium">{t("serviceTitle")}</h2>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("serviceBody")}</p>
          <form
            className="mt-4 grid gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              void createService();
            }}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm" htmlFor="connection-name">
                {t("serviceName")}
                <Input
                  id="connection-name"
                  onChange={(event) => setServiceName(event.target.value)}
                  value={serviceName}
                />
              </label>
              <label className="block text-sm" htmlFor="connection-kind">
                {t("serviceKind")}
                <select
                  className="mt-1 w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-2"
                  id="connection-kind"
                  onChange={(event) => setServiceKind(event.target.value)}
                  value={serviceKind}
                >
                  <option value="api_key">API key</option>
                  <option value="bearer">Bearer token</option>
                  <option value="basic">Basic auth</option>
                  <option value="oauth_authorization_code">OAuth authorization code</option>
                  <option value="oauth_client_credentials">OAuth client credentials</option>
                </select>
              </label>
            </div>
            <label className="block text-sm" htmlFor="connection-secret">
              {t("serviceSecret")}
              <Input
                id="connection-secret"
                onChange={(event) => setServiceSecret(event.target.value)}
                type="password"
                value={serviceSecret}
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm" htmlFor="connection-header">
                {t("serviceHeader")}
                <Input
                  id="connection-header"
                  onChange={(event) => setServiceHeader(event.target.value)}
                  value={serviceHeader}
                />
              </label>
              <label className="block text-sm" htmlFor="connection-user">
                {t("serviceUser")}
                <Input
                  id="connection-user"
                  onChange={(event) => setServiceUser(event.target.value)}
                  value={serviceUser}
                />
              </label>
              <label className="block text-sm" htmlFor="connection-token">
                {t("serviceTokenUrl")}
                <Input
                  id="connection-token"
                  onChange={(event) => setTokenUrl(event.target.value)}
                  value={tokenUrl}
                />
              </label>
              <label className="block text-sm" htmlFor="connection-authorize">
                {t("serviceAuthorizeUrl")}
                <Input
                  id="connection-authorize"
                  onChange={(event) => setAuthorizeUrl(event.target.value)}
                  value={authorizeUrl}
                />
              </label>
              <label className="block text-sm" htmlFor="connection-client">
                {t("serviceClientId")}
                <Input
                  id="connection-client"
                  onChange={(event) => setClientId(event.target.value)}
                  value={clientId}
                />
              </label>
              <label className="block text-sm" htmlFor="connection-expires">
                {t("serviceExpires")}
                <Input
                  id="connection-expires"
                  onChange={(event) => setExpiresAt(event.target.value)}
                  type="datetime-local"
                  value={expiresAt}
                />
              </label>
            </div>
            <label className="block text-sm" htmlFor="connection-probe">
              {t("serviceProbe")}
              <Input
                id="connection-probe"
                onChange={(event) => setProbeUrl(event.target.value)}
                value={probeUrl}
              />
            </label>
            <Button type="submit">{t("serviceSave")}</Button>
          </form>
          {notice ? <p role="status">{notice}</p> : null}
          {service.length === 0 ? (
            <p className="mt-4 text-sm text-[var(--muted-foreground)]">{t("serviceEmpty")}</p>
          ) : (
            <ul className="mt-4 grid gap-3">
              {service.map((row) => {
                const id = String(row.id);
                return (
                  <li
                    className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
                    key={id}
                  >
                    <p className="font-medium">{String(row.name)}</p>
                    <p className="text-[var(--muted-foreground)]">
                      {String(row.kind)} · {String(row.status)}
                      {row.expiresAt ? ` · ${t("serviceExpires")} ${String(row.expiresAt)}` : ""}
                    </p>
                    {row.lastError ? <p>{String(row.lastError)}</p> : null}
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button onClick={() => void testService(id)} type="button" variant="outline">
                        {t("serviceTest")}
                      </Button>
                      <Button
                        onClick={() => void rotateService(id)}
                        type="button"
                        variant="outline"
                      >
                        {t("serviceRotate")}
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
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
                    <Button onClick={() => void connect(id)} type="button">
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
        <h2 className="mb-2 text-lg font-medium">{t("databaseTitle")}</h2>
        <p className="mb-3 text-sm text-[var(--muted-foreground)]">{t("databaseBody")}</p>
        <div className="mb-4 grid gap-3 sm:grid-cols-2">
          <label className="block text-sm" htmlFor="database-name">
            {t("databaseName")}
            <Input
              className="mt-1"
              id="database-name"
              onChange={(event) => setDbName(event.target.value)}
              value={dbName}
            />
          </label>
          <label className="block text-sm" htmlFor="database-engine">
            {t("databaseEngine")}
            <select
              className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-2 text-sm"
              id="database-engine"
              onChange={(event) => setDbEngine(event.target.value)}
              value={dbEngine}
            >
              <option value="postgres">postgres</option>
              <option value="mysql">mysql</option>
            </select>
          </label>
          <label className="block text-sm sm:col-span-2" htmlFor="database-dsn">
            {t("databaseDsn")}
            <Input
              autoComplete="off"
              className="mt-1"
              id="database-dsn"
              onChange={(event) => setDbDsn(event.target.value)}
              type="password"
              value={dbDsn}
            />
          </label>
          <label className="block text-sm" htmlFor="database-schemas">
            {t("databaseSchemas")}
            <Input
              className="mt-1"
              id="database-schemas"
              onChange={(event) => setDbSchemas(event.target.value)}
              value={dbSchemas}
            />
          </label>
          <label className="block text-sm" htmlFor="database-tables">
            {t("databaseTables")}
            <Input
              className="mt-1"
              id="database-tables"
              onChange={(event) => setDbTables(event.target.value)}
              value={dbTables}
            />
          </label>
          <label className="block text-sm" htmlFor="database-rows">
            {t("databaseRows")}
            <Input
              className="mt-1"
              id="database-rows"
              max={5000}
              min={1}
              onChange={(event) => setDbRows(Number(event.target.value) || 1000)}
              type="number"
              value={dbRows}
            />
          </label>
          <label className="block text-sm" htmlFor="database-timeout">
            {t("databaseTimeout")}
            <Input
              className="mt-1"
              id="database-timeout"
              max={120}
              min={1}
              onChange={(event) => setDbTimeout(Number(event.target.value) || 30)}
              type="number"
              value={dbTimeout}
            />
          </label>
        </div>
        <Button onClick={() => void saveDatabase()} type="button">
          {t("databaseSave")}
        </Button>
        <h2 className="mb-2 mt-6 text-lg font-medium">{t("data")}</h2>
        {data.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("databaseEmpty")}</p>
        ) : null}
        <ul className="grid gap-4 md:grid-cols-2">
          {data.map((row) => (
            <li
              className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
              key={String(row.id)}
            >
              <h3 className="font-medium">{String(row.name)}</h3>
              <p className="text-sm text-[var(--muted-foreground)]">{String(row.engine)}</p>
              <Button
                className="mt-3"
                onClick={() => void testDatabase(String(row.id))}
                type="button"
                variant="outline"
              >
                {t("databaseTest")}
              </Button>
            </li>
          ))}
        </ul>
      </fieldset>
    </AppShell>
  );
}
