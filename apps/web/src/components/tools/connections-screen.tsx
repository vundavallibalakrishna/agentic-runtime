"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ActionStatus, DetailState } from "@/components/common/detail-state";
import { RecordList } from "@/components/common/record-list";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { loadSession } from "@/lib/session";

type Row = Record<string, unknown>;
type Section = "service" | "personal" | "database";
type ServiceAction = "test" | "rotate" | "authorize";
type ActionResult = { ok: true; authorizeUrl?: string } | { ok: false; error?: string };
type Permissions = { manage: boolean; read: boolean; create: boolean };

function authorizationUrl(value: unknown, message: string): string {
  try {
    if (typeof value !== "string" || !value) throw new Error();
    const url = new URL(value);
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password)
      throw new Error();
    return url.href;
  } catch {
    throw new Error(message);
  }
}

function ServiceRow({
  row,
  busy,
  onAction,
}: {
  row: Row;
  busy: boolean;
  onAction: (id: string, action: ServiceAction, value: string) => Promise<ActionResult>;
}) {
  const t = useTranslations("connections");
  const locale = useLocale();
  const fieldId = useId();
  const [action, setAction] = useState<ServiceAction | null>(null);
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [link, setLink] = useState("");
  const rotateButton = useRef<HTMLButtonElement>(null);
  const testButton = useRef<HTMLButtonElement>(null);
  const field = useRef<HTMLInputElement>(null);
  const id = String(row.id);
  const kind = String(row.kind ?? "");
  function open(next: ServiceAction) {
    setAction(next);
    setValue(next === "test" ? String(row.probeUrl ?? "") : "");
    setError("");
    setLink("");
  }
  useEffect(() => {
    if (action) field.current?.focus();
  }, [action]);
  function close() {
    const trigger = action === "rotate" ? rotateButton.current : testButton.current;
    setAction(null);
    setValue("");
    setError("");
    requestAnimationFrame(() => trigger?.isConnected && !trigger.disabled && trigger.focus());
  }
  async function submit(next: ServiceAction = action ?? "test") {
    const result = await onAction(id, next, value);
    if (!result.ok) {
      if (result.error) setError(result.error);
      return;
    }
    if (result.authorizeUrl) setLink(result.authorizeUrl);
    else close();
  }
  return (
    <li className="min-w-0 px-4 py-4 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-words font-medium">{String(row.name ?? id)}</p>
          <p className="mt-1 break-words text-[var(--muted-foreground)]">
            {t.has(`authKinds.${kind}`) ? t(`authKinds.${kind}`) : kind}
          </p>
          {row.expiresAt ? (
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">
              {t("serviceExpires")}{" "}
              <time dateTime={String(row.expiresAt)}>
                {formatDateTime(String(row.expiresAt), locale)}
              </time>
            </p>
          ) : null}
        </div>
        {row.status ? (
          <Badge tone={statusTone(String(row.status))}>{String(row.status)}</Badge>
        ) : null}
      </div>
      {row.lastError ? (
        <p className="mt-2 break-words text-[var(--destructive)]">{String(row.lastError)}</p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          disabled={busy}
          onClick={(event) => {
            testButton.current = event.currentTarget;
            open("test");
          }}
          type="button"
          variant="outline"
        >
          {t("serviceTest")}
        </Button>
        <Button
          disabled={busy}
          onClick={(event) => {
            rotateButton.current = event.currentTarget;
            open("rotate");
          }}
          type="button"
          variant="outline"
        >
          {t("serviceRotate")}
        </Button>
        {kind === "oauth_authorization_code" ? (
          <Button
            disabled={busy}
            type="button"
            variant="outline"
            onClick={() => void submit("authorize")}
          >
            {t("authorize")}
          </Button>
        ) : null}
      </div>
      {action ? (
        <form
          className="mt-4 rounded-lg border border-[var(--border)] p-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (event.currentTarget.reportValidity()) void submit();
          }}
        >
          <p className="mb-3 font-medium">
            {t(action === "rotate" ? "rotateNamed" : "testNamed", { name: String(row.name ?? id) })}
          </p>
          <label htmlFor={fieldId} className="block text-sm">
            {t(action === "rotate" ? "replacementSecret" : "serviceProbe")}
          </label>
          <Input
            ref={field}
            id={fieldId}
            className="mt-1"
            type={action === "rotate" ? "password" : "url"}
            autoComplete={action === "rotate" ? "new-password" : "off"}
            required={action === "rotate"}
            disabled={busy}
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
          <p className="mt-2 text-xs text-[var(--muted-foreground)]">
            {t(action === "rotate" ? "replacementHelp" : "testHelp")}
          </p>
          {error ? (
            <p className="mt-2 break-words text-[var(--destructive)]" role="alert">
              {error}
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <Button disabled={busy || (action === "rotate" && !value)} type="submit">
              {t(action === "rotate" ? "saveReplacement" : "serviceTest")}
            </Button>
            <Button disabled={busy} type="button" variant="outline" onClick={close}>
              {t("cancel")}
            </Button>
          </div>
        </form>
      ) : null}
      {error && !action ? (
        <p role="alert" className="mt-2 break-words text-[var(--destructive)]">
          {error}
        </p>
      ) : null}
      {link ? (
        <a className="mt-3 inline-block break-words underline" href={link}>
          {t("continueNamed", { name: String(row.name ?? id) })}
        </a>
      ) : null}
    </li>
  );
}

export function ConnectionsScreen() {
  const t = useTranslations("connections");
  const [grants, setGrants] = useState<Row[]>([]);
  const [providers, setProviders] = useState<Row[]>([]);
  const [data, setData] = useState<Row[]>([]);
  const [service, setService] = useState<Row[]>([]);
  const [permissions, setPermissions] = useState<Permissions | null>(null);
  const [readIssues, setReadIssues] = useState<Partial<Record<Section, string>>>({});
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [tab, setTab] = useState("service");
  const [requestedProvider, setRequestedProvider] = useState("");
  const [link, setLink] = useState<{ url: string; name: string } | null>(null);
  const readRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const [serviceName, setServiceName] = useState("");
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
  const [dbRows, setDbRows] = useState("1000");
  const [dbTimeout, setDbTimeout] = useState("30");
  const oauth = serviceKind.startsWith("oauth_");

  const load = useCallback(async () => {
    readRequest.current?.abort();
    const request = new AbortController();
    readRequest.current = request;
    setLoading(true);
    setError("");
    setReadIssues({});
    try {
      const identity = await loadSession();
      if (request.signal.aborted) return;
      const allowed = {
        manage: identity.permissions?.includes("connections:manage_own") ?? false,
        read: identity.permissions?.includes("tools:read") ?? false,
        create: identity.permissions?.includes("tools:create") ?? false,
      };
      setPermissions(allowed);
      const tasks: { section: Section; read: () => Promise<void> }[] = [];
      if (allowed.manage)
        tasks.push({
          section: "service",
          read: async () => {
            const page = await api<{ items: Row[] }>("/api/v1/service-connections", {
              signal: request.signal,
            });
            if (!request.signal.aborted) setService(page.items ?? []);
          },
        });
      else setService([]);
      if (allowed.manage && allowed.read)
        tasks.push({
          section: "personal",
          read: async () => {
            const [grantPage, providerPage] = await Promise.all([
              api<{ items: Row[] }>("/api/v1/connections", { signal: request.signal }),
              api<{ items: Row[] }>("/api/v1/credential-providers", { signal: request.signal }),
            ]);
            if (!request.signal.aborted) {
              setGrants(grantPage.items ?? []);
              setProviders(providerPage.items ?? []);
            }
          },
        });
      else {
        setGrants([]);
        setProviders([]);
      }
      if (allowed.read)
        tasks.push({
          section: "database",
          read: async () => {
            const page = await api<{ items: Row[] }>("/api/v1/data-connections", {
              signal: request.signal,
            });
            if (!request.signal.aborted) setData(page.items ?? []);
          },
        });
      else setData([]);
      const results = await Promise.allSettled(tasks.map((task) => task.read()));
      if (request.signal.aborted) return;
      const issues: Partial<Record<Section, string>> = {};
      tasks.forEach((task, index) => {
        const result = results[index];
        if (result?.status === "rejected")
          issues[task.section] =
            result.reason instanceof Error ? result.reason.message : t("error");
      });
      setReadIssues(issues);
      setLoaded(true);
    } catch (caught) {
      if (!request.signal.aborted) {
        setPermissions(null);
        setError(caught instanceof Error ? caught.message : t("error"));
      }
    } finally {
      if (readRequest.current === request) {
        readRequest.current = null;
        setLoading(false);
      }
    }
  }, [t]);
  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("provider") ?? "";
    if (requested) {
      setRequestedProvider(requested);
      setTab("personal");
    }
    void load();
    return () => {
      readRequest.current?.abort();
      actionRequest.current?.abort();
    };
  }, [load]);

  const activeGrants = useMemo(() => {
    const result = new Map<string, Row>();
    for (const grant of grants)
      if (grant.status === "active" && !result.has(String(grant.providerId)))
        result.set(String(grant.providerId), grant);
    return result;
  }, [grants]);
  const personalStatus = useCallback(
    (row: Row) => (activeGrants.has(String(row.id)) ? "connected" : "unconnected"),
    [activeGrants],
  );
  const listLabels = (label: string) => ({
    search: t("findRecords", { label }),
    status: t("status"),
    allStatuses: t("allStatuses"),
    clear: t("clearFilters"),
    noMatches: t("noMatches"),
    statusValue: (value: string) => (t.has(`statuses.${value}`) ? t(`statuses.${value}`) : value),
  });

  async function perform(
    action: (signal: AbortSignal) => Promise<{ authorizeUrl?: string } | undefined>,
    localError = false,
  ): Promise<ActionResult> {
    if (actionRequest.current || loading) return { ok: false };
    const request = new AbortController();
    actionRequest.current = request;
    setBusy(true);
    setActionError("");
    setNotice("");
    setLink(null);
    try {
      const result = await action(request.signal);
      return request.signal.aborted ? { ok: false } : { ok: true, ...result };
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : t("error");
      if (!request.signal.aborted && !localError) setActionError(detail);
      return { ok: false, ...(request.signal.aborted ? {} : { error: detail }) };
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setBusy(false);
      }
    }
  }
  async function connect(provider: Row) {
    if (!permissions?.manage || !permissions.read) return;
    await perform(async (signal) => {
      const started = await api<{ authorizeUrl?: string }>(
        `/api/v1/connections/${String(provider.id)}:start`,
        { method: "POST", signal },
      );
      if (!signal.aborted)
        setLink({
          url: authorizationUrl(started.authorizeUrl, t("authorizationUnconfirmed")),
          name: String(provider.name ?? provider.id),
        });
    });
  }
  async function disconnect(grantId: string) {
    if (!permissions?.manage) return;
    await perform(async (signal) => {
      await api(`/api/v1/connections/${grantId}`, { method: "DELETE", signal });
      if (!signal.aborted) {
        setNotice(t("disconnected"));
        await load();
      }
    });
  }
  async function createService() {
    if (!permissions?.manage || !serviceName.trim()) return;
    await perform(async (signal) => {
      await api("/api/v1/service-connections", {
        method: "POST",
        signal,
        body: JSON.stringify({
          name: serviceName.trim(),
          kind: serviceKind,
          secret: serviceSecret,
          ...(serviceKind === "api_key" ? { headerName: serviceHeader } : {}),
          ...(serviceKind === "basic" ? { username: serviceUser } : {}),
          ...(oauth ? { tokenUrl, clientId } : {}),
          ...(serviceKind === "oauth_authorization_code" ? { authorizeUrl } : {}),
          expiresAt: expiresAt ? new Date(expiresAt).toISOString() : undefined,
          probeUrl,
        }),
      });
      if (!signal.aborted) {
        setServiceSecret("");
        setNotice(t("serviceSaved"));
        await load();
      }
    });
  }
  async function runServiceAction(
    id: string,
    action: ServiceAction,
    value: string,
  ): Promise<ActionResult> {
    if (!permissions?.manage) return { ok: false };
    return perform(async (signal) => {
      if (action === "authorize") {
        const result = await api<{ authorizeUrl?: string }>(
          `/api/v1/service-connections/${id}:authorize`,
          { method: "POST", signal },
        );
        if (signal.aborted) return;
        return {
          authorizeUrl: authorizationUrl(result.authorizeUrl, t("authorizationUnconfirmed")),
        };
      }
      if (action === "rotate") {
        if (!value) throw new Error(t("replacementRequired"));
        await api(`/api/v1/service-connections/${id}:rotate`, {
          method: "POST",
          signal,
          body: JSON.stringify({ secret: value }),
        });
        if (!signal.aborted) {
          setNotice(t("serviceRotated"));
          await load();
        }
      } else {
        const result = await api<{ ok?: boolean; error?: string | null }>(
          `/api/v1/service-connections/${id}:test`,
          { method: "POST", signal, body: JSON.stringify({ url: value }) },
        );
        if (signal.aborted) return;
        await load();
        if (!result.ok) throw new Error(result.error || t("testFailed"));
        setNotice(t("serviceTested"));
      }
    }, true);
  }
  async function saveDatabase() {
    if (!permissions?.create || !dbName.trim() || !dbDsn.trim()) return;
    await perform(async (signal) => {
      const created = await api<{ id?: string }>("/api/v1/data-connections", {
        method: "POST",
        signal,
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
          rowLimit: Number(dbRows),
          statementTimeoutS: Number(dbTimeout),
        }),
      });
      if (signal.aborted) return;
      if (typeof created.id !== "string" || !created.id) throw new Error(t("creationUnconfirmed"));
      setDbDsn("");
      setNotice(t("databaseSaved"));
      await load();
      if (signal.aborted) return;
      const tested = await api<{ ok?: boolean; error?: string }>(
        `/api/v1/data-connections/${created.id}:test`,
        {
          method: "POST",
          signal,
          body: "{}",
        },
      );
      if (!signal.aborted) {
        if (!tested.ok) throw new Error(tested.error || t("testFailed"));
        setNotice(t("databaseTested"));
      }
    });
  }
  async function testDatabase(id: string) {
    if (!permissions?.create) return;
    await perform(async (signal) => {
      const result = await api<{ ok?: boolean; error?: string }>(
        `/api/v1/data-connections/${id}:test`,
        {
          method: "POST",
          signal,
          body: "{}",
        },
      );
      if (!signal.aborted) {
        if (!result.ok) throw new Error(result.error || t("testFailed"));
        setNotice(t("databaseTested"));
      }
    });
  }

  return (
    <AppShell>
      <PageHeader
        body={t("body")}
        title={t("title")}
        actions={
          <Button asChild variant="outline">
            <a href="/tools">{t("back")}</a>
          </Button>
        }
      />
      <DetailState
        loading={loading && !loaded}
        error={error}
        onRetry={busy ? undefined : () => void load()}
      />
      <ActionStatus busy={busy || (loading && loaded)} notice={notice} />
      {actionError ? (
        <div className="mb-4 rounded-lg border border-[var(--border)] p-4 text-sm" role="alert">
          <p className="break-words">{actionError}</p>
          <Button
            className="mt-3"
            type="button"
            variant="outline"
            disabled={busy || loading}
            onClick={() => {
              setActionError("");
              void load();
            }}
          >
            {t("refresh")}
          </Button>
        </div>
      ) : null}
      {permissions && loaded ? (
        <fieldset disabled={busy || loading} className="min-w-0">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="service">{t("serviceTab")}</TabsTrigger>
              <TabsTrigger value="personal">{t("personalTab")}</TabsTrigger>
              <TabsTrigger value="database">{t("databaseTitle")}</TabsTrigger>
            </TabsList>
            <TabsContent value="service">
              <h2 className="text-lg font-semibold">{t("serviceTitle")}</h2>
              <p className="mb-5 mt-1 text-sm text-[var(--muted-foreground)]">{t("serviceBody")}</p>
              {!permissions.manage ? (
                <p>{t("manageDenied")}</p>
              ) : (
                <>
                  <DetailState
                    loading={false}
                    error={readIssues.service ?? ""}
                    onRetry={() => void load()}
                  />
                  <fieldset disabled={Boolean(readIssues.service)} className="min-w-0">
                    <details className="detail-panel mb-6">
                      <summary className="cursor-pointer text-sm font-medium">
                        {t("addService")}
                      </summary>
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
                              required
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
                              <option value="api_key">{t("authKinds.api_key")}</option>
                              <option value="bearer">{t("authKinds.bearer")}</option>
                              <option value="basic">{t("authKinds.basic")}</option>
                              <option value="oauth_authorization_code">
                                {t("authKinds.oauth_authorization_code")}
                              </option>
                              <option value="oauth_client_credentials">
                                {t("authKinds.oauth_client_credentials")}
                              </option>
                            </select>
                          </label>
                        </div>
                        <label className="block text-sm" htmlFor="connection-secret">
                          {t(
                            serviceKind === "basic"
                              ? "servicePassword"
                              : oauth
                                ? "serviceClientSecret"
                                : serviceKind === "api_key"
                                  ? "serviceApiKey"
                                  : "serviceBearer",
                          )}
                          <Input
                            id="connection-secret"
                            autoComplete="new-password"
                            onChange={(event) => setServiceSecret(event.target.value)}
                            type="password"
                            value={serviceSecret}
                          />
                        </label>
                        <div className="grid gap-3 sm:grid-cols-2">
                          {serviceKind === "api_key" ? (
                            <label className="block text-sm" htmlFor="connection-header">
                              {t("serviceHeader")}
                              <Input
                                id="connection-header"
                                onChange={(event) => setServiceHeader(event.target.value)}
                                value={serviceHeader}
                              />
                            </label>
                          ) : null}
                          {serviceKind === "basic" ? (
                            <label className="block text-sm" htmlFor="connection-user">
                              {t("serviceUser")}
                              <Input
                                id="connection-user"
                                onChange={(event) => setServiceUser(event.target.value)}
                                value={serviceUser}
                              />
                            </label>
                          ) : null}
                          {oauth ? (
                            <label className="block text-sm" htmlFor="connection-token">
                              {t("serviceTokenUrl")}
                              <Input
                                id="connection-token"
                                type="url"
                                onChange={(event) => setTokenUrl(event.target.value)}
                                value={tokenUrl}
                              />
                            </label>
                          ) : null}
                          {serviceKind === "oauth_authorization_code" ? (
                            <label className="block text-sm" htmlFor="connection-authorize">
                              {t("serviceAuthorizeUrl")}
                              <Input
                                id="connection-authorize"
                                type="url"
                                onChange={(event) => setAuthorizeUrl(event.target.value)}
                                value={authorizeUrl}
                              />
                            </label>
                          ) : null}
                          {oauth ? (
                            <label className="block text-sm" htmlFor="connection-client">
                              {t("serviceClientId")}
                              <Input
                                id="connection-client"
                                onChange={(event) => setClientId(event.target.value)}
                                value={clientId}
                              />
                            </label>
                          ) : null}
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
                            type="url"
                            onChange={(event) => setProbeUrl(event.target.value)}
                            value={probeUrl}
                          />
                        </label>
                        <Button type="submit">{t("serviceSave")}</Button>
                      </form>
                    </details>
                    {!readIssues.service ? (
                      <RecordList
                        rows={service}
                        label={t("serviceTitle")}
                        emptyMessage={t("serviceEmpty")}
                        fields={["id", "name", "kind", "status"]}
                        labels={listLabels(t("serviceTab"))}
                      >
                        {(row) => (
                          <ServiceRow
                            key={String(row.id)}
                            row={row}
                            busy={busy || loading}
                            onAction={runServiceAction}
                          />
                        )}
                      </RecordList>
                    ) : null}
                  </fieldset>
                </>
              )}
            </TabsContent>
            <TabsContent value="personal">
              <h2 className="text-lg font-semibold">{t("personalTab")}</h2>
              <p className="mb-5 mt-1 text-sm text-[var(--muted-foreground)]">
                {t("personalBody")}
              </p>
              {!permissions.manage || !permissions.read ? (
                <p>{t("personalDenied")}</p>
              ) : (
                <>
                  <DetailState
                    loading={false}
                    error={readIssues.personal ?? ""}
                    onRetry={() => void load()}
                  />
                  {!readIssues.personal ? (
                    <RecordList
                      key={requestedProvider}
                      initialQuery={requestedProvider}
                      rows={providers}
                      label={t("personalTab")}
                      emptyMessage={t("empty")}
                      fields={["id", "name", "slug"]}
                      getStatus={personalStatus}
                      labels={listLabels(t("personalTab"))}
                    >
                      {(provider) => {
                        const grant = activeGrants.get(String(provider.id));
                        return (
                          <li
                            key={String(provider.id)}
                            className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 text-sm"
                          >
                            <div className="min-w-0">
                              <p className="break-words font-medium">
                                {String(provider.name ?? provider.id)}
                              </p>
                              <p className="mt-1 break-words text-[var(--muted-foreground)]">
                                {grant ? t("connected") : String(provider.slug ?? "")}
                              </p>
                            </div>
                            {grant ? (
                              <Button
                                type="button"
                                variant="outline"
                                onClick={() => void disconnect(String(grant.id))}
                              >
                                {t("disconnect")}
                              </Button>
                            ) : (
                              <Button type="button" onClick={() => void connect(provider)}>
                                {t("connect")}
                              </Button>
                            )}
                          </li>
                        );
                      }}
                    </RecordList>
                  ) : null}
                  {link ? (
                    <a className="mt-4 inline-block break-words underline" href={link.url}>
                      {t("continueNamed", { name: link.name })}
                    </a>
                  ) : null}
                </>
              )}
            </TabsContent>
            <TabsContent value="database">
              <h2 className="text-lg font-semibold">{t("databaseTitle")}</h2>
              <p className="mb-5 mt-1 text-sm text-[var(--muted-foreground)]">
                {t("databaseBody")}
              </p>
              {!permissions.read ? (
                <p>{t("readDenied")}</p>
              ) : (
                <>
                  <DetailState
                    loading={false}
                    error={readIssues.database ?? ""}
                    onRetry={() => void load()}
                  />
                  {permissions.create ? (
                    <details className="detail-panel mb-6">
                      <summary className="cursor-pointer text-sm font-medium">
                        {t("addDatabase")}
                      </summary>
                      <form
                        className="mt-4"
                        onSubmit={(event) => {
                          event.preventDefault();
                          if (event.currentTarget.reportValidity()) void saveDatabase();
                        }}
                      >
                        <fieldset disabled={Boolean(readIssues.database)} className="min-w-0">
                          <div className="mb-4 grid gap-3 sm:grid-cols-2">
                            <label className="block text-sm" htmlFor="database-name">
                              {t("databaseName")}
                              <Input
                                className="mt-1"
                                id="database-name"
                                required
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
                                required
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
                                required
                                min={1}
                                onChange={(event) => setDbRows(event.target.value)}
                                type="number"
                                value={dbRows}
                              />
                            </label>
                            <label className="block text-sm" htmlFor="database-timeout">
                              {t("databaseTimeout")}
                              <Input
                                className="mt-1"
                                id="database-timeout"
                                required
                                min={1}
                                onChange={(event) => setDbTimeout(event.target.value)}
                                type="number"
                                value={dbTimeout}
                              />
                            </label>
                          </div>
                          <Button type="submit">{t("databaseSave")}</Button>
                        </fieldset>
                      </form>
                    </details>
                  ) : (
                    <p className="mb-4 text-sm text-[var(--muted-foreground)]">
                      {t("createDenied")}
                    </p>
                  )}
                  {!readIssues.database ? (
                    <RecordList
                      rows={data}
                      label={t("data")}
                      emptyMessage={t("databaseEmpty")}
                      fields={["id", "name", "engine", "status"]}
                      labels={listLabels(t("databaseTitle"))}
                    >
                      {(row) => (
                        <li
                          key={String(row.id)}
                          className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 text-sm"
                        >
                          <div className="min-w-0">
                            <p className="break-words font-medium">{String(row.name ?? row.id)}</p>
                            <p className="mt-1 text-[var(--muted-foreground)]">
                              {String(row.engine ?? "")}
                            </p>
                          </div>
                          {permissions.create ? (
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => void testDatabase(String(row.id))}
                            >
                              {t("databaseTest")}
                            </Button>
                          ) : null}
                        </li>
                      )}
                    </RecordList>
                  ) : null}
                </>
              )}
            </TabsContent>
          </Tabs>
        </fieldset>
      ) : null}
    </AppShell>
  );
}
