"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { CodeSample } from "@/components/common/code-sample";
import { ActionStatus } from "@/components/common/detail-state";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { ConfirmDialog } from "@/components/models/dialogs";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { clearCachedSession, loadSession } from "@/lib/session";
import { exactOrigins } from "@/lib/widget-origins";

type Agent = {
  id: string;
  name: string;
  slug?: string;
  status?: string;
  visibility?: string;
  publishedVersion?: number | null;
};
type Post = { id: string; body: string; status?: string };
type Integration = {
  id: string;
  kind: string;
  name: string;
  status?: string;
  statusDetail?: string;
  identitiesCount?: number;
  recentPosts?: Post[];
  config?: Record<string, unknown>;
  defaultAgent?: { id: string; name: string } | null;
  agentRouting?: unknown[];
};
type Limits = {
  maxMessages: string;
  maxMessageChars: string;
  sessionsPerMinute: string;
  sessionsPerClientPerMinute: string;
  sessionMinutes: string;
};

const MODE_KEY = "ar-settings-mode";
// What the server applies when a limit is left as it is.
const LIMITS: Limits = {
  maxMessages: "30",
  maxMessageChars: "2000",
  sessionsPerMinute: "60",
  sessionsPerClientPerMinute: "10",
  sessionMinutes: "30",
};

function whole(value: string, fallback: number): number {
  const number = Math.floor(Number(value));
  return Number.isFinite(number) && number > 0 ? number : fallback;
}

function numberText(value: unknown, fallback: string, divide = 1): string {
  return typeof value === "number" && value > 0 ? String(Math.round(value / divide)) : fallback;
}

function originsOf(config: Record<string, unknown>): string {
  const raw = config.allowedOrigins ?? config.allowed_origins;
  return Array.isArray(raw) ? raw.map(String).join("\n") : "";
}

export function ChannelsScreen() {
  const t = useTranslations("channels");
  const [rows, setRows] = useState<Integration[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<Integration | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("slack");
  const [token, setToken] = useState("");
  // The second credential a kind needs: Slack's signing secret, Teams' app id, a mailbox user.
  const [second, setSecond] = useState("");
  const [origins, setOrigins] = useState("");
  const [access, setAccess] = useState("signed");
  const [visitorEmail, setVisitorEmail] = useState("");
  const [visitorNotice, setVisitorNotice] = useState("");
  const [limits, setLimits] = useState<Limits>(LIMITS);
  const [showSources, setShowSources] = useState(true);
  const anyone = kind === "widget" && access === "public";
  const [embed, setEmbed] = useState<{ id: string; public: boolean } | null>(null);
  const [routing, setRouting] = useState("");
  const [agentId, setAgentId] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Integration | null>(null);
  const [removing, setRemoving] = useState<Integration | null>(null);
  // Whether this workspace may have widgets at all, and whether this person may change that.
  const [widgetOn, setWidgetOn] = useState<boolean | null>(null);
  const [manageTenant, setManageTenant] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [page, agentPage, session] = await Promise.all([
        api<{ items: Integration[] }>("/api/v1/channel-integrations"),
        api<{ items: Agent[] }>("/api/v1/agents"),
        loadSession(),
      ]);
      const list = page.items ?? [];
      setRows(list);
      const people = agentPage.items ?? [];
      setAgents(people);
      setAgentId(
        (current) => current || people.find((agent) => agent.status !== "archived")?.id || "",
      );
      setWidgetOn(session.features?.widget === true);
      setManageTenant((session.permissions ?? []).includes("tenant:manage"));
      setSelected(null);
      if (list[0]) {
        const detail = await api<Integration>(`/api/v1/channel-integrations/${list[0].id}`);
        setSelected(detail);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
    void load();
  }, [load]);

  function chooseMode(next: boolean) {
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }

  function resetForm() {
    setEditing(null);
    setName("");
    setKind("slack");
    setToken("");
    setSecond("");
    setOrigins("");
    setAccess("signed");
    setVisitorEmail("");
    setVisitorNotice("");
    setLimits(LIMITS);
    setShowSources(true);
    setRouting("");
    setAgentId(agents.find((agent) => agent.status !== "archived")?.id ?? "");
  }

  async function startEdit(id: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const detail = await api<Integration>(`/api/v1/channel-integrations/${id}`);
      const config = detail.config ?? {};
      setEditing(detail);
      setName(detail.name);
      setKind(detail.kind);
      setToken("");
      setSecond("");
      setOrigins(originsOf(config));
      setAccess(config.access === "public" ? "public" : "signed");
      setVisitorEmail(String(config.visitorEmail ?? ""));
      setVisitorNotice(String(config.notice ?? ""));
      setLimits({
        maxMessages: numberText(config.maxMessages, LIMITS.maxMessages),
        maxMessageChars: numberText(config.maxMessageChars, LIMITS.maxMessageChars),
        sessionsPerMinute: numberText(config.sessionsPerMinute, LIMITS.sessionsPerMinute),
        sessionsPerClientPerMinute: numberText(
          config.sessionsPerClientPerMinute,
          LIMITS.sessionsPerClientPerMinute,
        ),
        sessionMinutes: numberText(config.sessionSeconds, LIMITS.sessionMinutes, 60),
      });
      setShowSources(config.showSources !== false);
      setRouting(detail.agentRouting?.length ? JSON.stringify(detail.agentRouting) : "");
      setAgentId(detail.defaultAgent?.id ?? "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  function widgetConfig(): Record<string, unknown> {
    const requested = origins.split(/[\s,]+/).filter(Boolean);
    const allowedOrigins = exactOrigins(requested);
    if (!allowedOrigins.length || allowedOrigins.length !== new Set(requested).size)
      throw new Error(t("invalidOrigins"));
    if (!anyone) return { allowedOrigins, showSources };
    return {
      allowedOrigins,
      showSources,
      access: "public",
      visitorEmail: visitorEmail.trim(),
      notice: visitorNotice.trim(),
      maxMessages: whole(limits.maxMessages, 30),
      maxMessageChars: whole(limits.maxMessageChars, 2000),
      sessionsPerMinute: whole(limits.sessionsPerMinute, 60),
      sessionsPerClientPerMinute: whole(limits.sessionsPerClientPerMinute, 10),
      sessionSeconds: whole(limits.sessionMinutes, 30) * 60,
    };
  }

  /** The credentials typed in, or null when none were (an edit then keeps the saved ones). */
  function credentials(): Record<string, string> | null {
    if (anyone) return editing ? null : {};
    if (!token && !second) return null;
    if (kind !== "widget" && (!token || !second)) throw new Error(t("bothCredentials"));
    if (kind === "slack") return { botToken: token, signingSecret: second };
    if (kind === "teams") return { appId: second, appPassword: token };
    if (kind === "email") return { username: second, password: token };
    return { widgetSecret: token };
  }

  async function saveChannel() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const config = kind === "widget" ? widgetConfig() : undefined;
      const secrets = credentials();
      const agentRouting = advanced && routing ? JSON.parse(routing) : undefined;
      if (editing) {
        await api<Integration>(`/api/v1/channel-integrations/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            name,
            defaultAgentId: agentId || null,
            ...(config ? { config } : {}),
            ...(secrets ? { credentials: secrets } : {}),
            ...(agentRouting ? { agentRouting } : {}),
          }),
        });
        setEmbed(null);
      } else {
        const created = await api<Integration>("/api/v1/channel-integrations", {
          method: "POST",
          body: JSON.stringify({
            kind,
            name,
            defaultAgentId: agentId || undefined,
            credentials: secrets ?? {},
            agentRouting: agentRouting ?? [],
            config: config ?? { command: "/agent", allowedChannelIds: [] },
          }),
        });
        setEmbed(kind === "widget" ? { id: created.id, public: anyone } : null);
      }
      resetForm();
      setNotice(t("saved"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(row: Integration, status: "active" | "disabled") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`/api/v1/channel-integrations/${row.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setNotice(t(status === "disabled" ? "turnedOff" : "turnedOn", { name: row.name }));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function remove(row: Integration) {
    setError("");
    setNotice("");
    try {
      await api(`/api/v1/channel-integrations/${row.id}`, { method: "DELETE" });
      if (editing?.id === row.id) resetForm();
      if (embed?.id === row.id) setEmbed(null);
      setNotice(t("deleted", { name: row.name }));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  async function switchWidget(next: boolean) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const saved = await api<{ settings?: { features?: { widget?: boolean } } }>(
        "/api/v1/tenant",
        { method: "PATCH", body: JSON.stringify({ settings: { features: { widget: next } } }) },
      );
      setWidgetOn(saved.settings?.features?.widget === true);
      // The shell reads features from the session; read it again on the next screen.
      clearCachedSession();
      setNotice(t(next ? "widgetTurnedOn" : "widgetTurnedOff"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function showInstall(id: string) {
    setBusy(true);
    setError("");
    try {
      const detail = await api<Integration>(`/api/v1/channel-integrations/${id}`);
      setEmbed({ id, public: detail.config?.access === "public" });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function testConnection(id: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api<{ ok: boolean; detail: string }>(
        `/api/v1/channel-integrations/${id}:test`,
        { method: "POST" },
      );
      setNotice(`${t("tested")} ${result.detail}`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function showPosts(id: string) {
    setBusy(true);
    setError("");
    setSelected(null);
    try {
      setSelected(await api<Integration>(`/api/v1/channel-integrations/${id}`));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  const chosen = agents.find((agent) => agent.id === agentId);
  const widgetBlocked = kind === "widget" && widgetOn === false && !editing;
  const secondLabel =
    kind === "slack" ? t("signingSecret") : kind === "teams" ? t("appId") : t("mailboxUser");

  const secondField =
    kind === "widget" ? null : (
      <>
        <label className="mt-3 block text-sm" htmlFor="channel-second">
          {secondLabel}
        </label>
        <Input
          autoComplete="off"
          className="mt-1 max-w-md"
          id="channel-second"
          onChange={(event) => setSecond(event.target.value)}
          type={kind === "slack" ? "password" : "text"}
          value={second}
        />
      </>
    );

  return (
    <AppShell>
      <ActionStatus busy={busy} />
      <fieldset disabled={busy} className="min-w-0">
        <PageHeader
          title={t("title")}
          body={t("body")}
          actions={<SettingsMode advanced={advanced} onChange={chooseMode} />}
        />
        {error ? (
          <p className="mb-3 text-sm text-[var(--destructive)]" role="alert">
            {error}{" "}
            <Button onClick={() => void load()} type="button" variant="outline">
              {t("retry")}
            </Button>
          </p>
        ) : null}
        {notice ? (
          <p className="mb-3 text-sm text-[var(--muted-foreground)]" role="status">
            {notice}
          </p>
        ) : null}

        {widgetOn !== null ? (
          <section
            aria-labelledby="widget-feature-title"
            className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4"
          >
            <div className="min-w-0">
              <h2 className="text-base font-medium" id="widget-feature-title">
                {t("widgetFeature")}
              </h2>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                {t(widgetOn ? "widgetFeatureOn" : "widgetFeatureOff")}
              </p>
            </div>
            {manageTenant ? (
              <Button
                onClick={() => void switchWidget(!widgetOn)}
                type="button"
                variant={widgetOn ? "outline" : "default"}
              >
                {t(widgetOn ? "widgetTurnOff" : "widgetTurnOn")}
              </Button>
            ) : (
              <p className="text-sm text-muted-foreground">{t("widgetAskAdmin")}</p>
            )}
          </section>
        ) : null}

        {embed && (
          <section
            className="mb-6 rounded-xl border border-border bg-card p-4"
            aria-label={t("embedTitle")}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-medium">{t("embedTitle")}</h2>
              <Button onClick={() => setEmbed(null)} type="button" variant="ghost">
                {t("close")}
              </Button>
            </div>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              {t(embed.public ? "embedHelpPublic" : "embedHelp")}
            </p>
            <div className="mt-3">
              <CodeSample
                title={t("embedCode")}
                value={`<script src="${window.location.origin}/widget.js" data-integration="${embed.id}"></script>`}
              />
            </div>
          </section>
        )}
        <ManagementLayout
          title={t("listTitle")}
          formTitle={editing ? t("editTitle", { name: editing.name }) : t("create")}
          form={
            <section className="space-y-1">
              <label className="mt-3 block text-sm" htmlFor="channel-name">
                {t("name")}
              </label>
              <Input
                className="mt-1 max-w-md"
                id="channel-name"
                onChange={(event) => setName(event.target.value)}
                value={name}
              />
              <label className="mt-3 block text-sm" htmlFor="channel-kind">
                {t("kind")}
              </label>
              <select
                className="mt-1 max-w-md rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 text-sm"
                disabled={!!editing}
                id="channel-kind"
                onChange={(event) => setKind(event.target.value)}
                value={kind}
              >
                <option value="slack">Slack</option>
                <option value="teams">Teams</option>
                <option value="email">Email</option>
                <option value="widget">Widget</option>
              </select>
              {widgetBlocked ? (
                <p className="mt-2 max-w-md text-sm text-[var(--destructive)]" role="alert">
                  {t(manageTenant ? "widgetOffTurnOn" : "widgetOffAsk")}
                </p>
              ) : null}
              {kind === "widget" && (
                <div className="mt-3">
                  <label className="block text-sm" htmlFor="widget-access">
                    {t("widgetAccess")}
                  </label>
                  <select
                    className="mt-1 max-w-md rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 text-sm"
                    id="widget-access"
                    onChange={(event) => setAccess(event.target.value)}
                    value={access}
                  >
                    <option value="signed">{t("widgetAccessSigned")}</option>
                    <option value="public">{t("widgetAccessPublic")}</option>
                  </select>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t(anyone ? "widgetAccessPublicHelp" : "widgetAccessSignedHelp")}
                  </p>
                </div>
              )}
              {anyone ? (
                <div className="mt-3">
                  <label className="block text-sm" htmlFor="widget-visitor">
                    {t("widgetVisitor")}
                  </label>
                  <Input
                    className="mt-1 max-w-md"
                    id="widget-visitor"
                    onChange={(event) => setVisitorEmail(event.target.value)}
                    type="email"
                    value={visitorEmail}
                  />
                  <p className="mt-1 text-xs text-muted-foreground">{t("widgetVisitorHelp")}</p>
                  <label className="mt-3 block text-sm" htmlFor="widget-notice">
                    {t("widgetNotice")}
                  </label>
                  <textarea
                    id="widget-notice"
                    value={visitorNotice}
                    onChange={(event) => setVisitorNotice(event.target.value)}
                    rows={2}
                    className="mt-1 w-full max-w-xl rounded-lg border border-border bg-background p-3 text-sm"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">{t("widgetNoticeHelp")}</p>
                  <fieldset className="mt-3">
                    <legend className="text-sm font-medium">{t("widgetLimits")}</legend>
                    <div className="mt-1 flex flex-wrap gap-4">
                      {(
                        [
                          ["maxMessages", "widgetMaxMessages", 1000],
                          ["maxMessageChars", "widgetMaxChars", 32000],
                          ["sessionsPerMinute", "widgetSessionsPerMinute", 6000],
                          ["sessionsPerClientPerMinute", "widgetSessionsPerVisitor", 600],
                          ["sessionMinutes", "widgetSessionMinutes", 1440],
                        ] as const
                      ).map(([key, label, most]) => (
                        <label className="text-sm" htmlFor={`widget-${key}`} key={key}>
                          {t(label)}
                          <Input
                            className="mt-1 w-28"
                            id={`widget-${key}`}
                            max={most}
                            min={1}
                            onChange={(event) =>
                              setLimits((current) => ({ ...current, [key]: event.target.value }))
                            }
                            type="number"
                            value={limits[key]}
                          />
                        </label>
                      ))}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{t("widgetLimitsHelp")}</p>
                  </fieldset>
                </div>
              ) : (
                <>
                  {kind === "slack" ? null : secondField}
                  <label className="mt-3 block text-sm" htmlFor="channel-token">
                    {kind === "widget"
                      ? t("widgetSecret")
                      : kind === "slack"
                        ? t("token")
                        : t("password")}
                  </label>
                  <Input
                    aria-describedby={editing ? "channel-token-keep" : undefined}
                    autoComplete="new-password"
                    className="mt-1 max-w-md"
                    id="channel-token"
                    onChange={(event) => setToken(event.target.value)}
                    type="password"
                    value={token}
                  />
                  {editing ? (
                    <p className="mt-1 text-xs text-muted-foreground" id="channel-token-keep">
                      {t("keepSecret")}
                    </p>
                  ) : null}
                  {kind === "slack" ? secondField : null}
                </>
              )}
              {kind === "widget" && (
                <div className="mt-3">
                  <label htmlFor="widget-origins" className="block text-sm">
                    {t("origins")}
                  </label>
                  <textarea
                    id="widget-origins"
                    value={origins}
                    onChange={(event) => setOrigins(event.target.value)}
                    rows={2}
                    className="mt-1 w-full max-w-xl rounded-lg border border-border bg-background p-3 text-sm"
                    placeholder="https://portal.example.com"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">{t("originsHelp")}</p>
                  <label className="mt-3 flex items-start gap-2 text-sm">
                    <input
                      checked={showSources}
                      className="mt-1"
                      onChange={(event) => setShowSources(event.target.checked)}
                      type="checkbox"
                    />
                    <span>
                      {t("showSources")}
                      <span className="block text-xs text-muted-foreground">
                        {t("showSourcesHelp")}
                      </span>
                    </span>
                  </label>
                </div>
              )}
              {advanced || kind === "widget" ? (
                <div className="mt-3">
                  <label className="block text-sm" htmlFor="channel-agent">
                    {t("agent")}
                  </label>
                  <select
                    aria-describedby={chosen ? "channel-agent-hint" : undefined}
                    className="mt-1 max-w-md rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 text-sm"
                    id="channel-agent"
                    onChange={(event) => setAgentId(event.target.value)}
                    value={agentId}
                  >
                    {agentId && !chosen ? (
                      <option value={agentId}>{t("agentUnknown")}</option>
                    ) : null}
                    {agents
                      .filter((agent) => agent.status !== "archived" || agent.id === agentId)
                      .map((agent) => (
                        <option key={agent.id} value={agent.id}>
                          {agent.slug ? `${agent.name} (${agent.slug})` : agent.name}
                        </option>
                      ))}
                  </select>
                  {chosen ? (
                    <p
                      className="mt-1 max-w-md text-xs text-muted-foreground"
                      id="channel-agent-hint"
                    >
                      {chosen.publishedVersion
                        ? t("agentVersion", { version: chosen.publishedVersion })
                        : t("agentUnpublished")}{" "}
                      {chosen.visibility && chosen.visibility !== "tenant" ? (
                        <>
                          {t("agentNotShared")}{" "}
                          <Link className="underline" href={`/agents/${chosen.id}`}>
                            {t("agentOpen", { name: chosen.name })}
                          </Link>
                        </>
                      ) : null}
                    </p>
                  ) : null}
                  {advanced && (
                    <>
                      <label className="mt-3 block text-sm" htmlFor="channel-routing">
                        {t("routing")}
                      </label>
                      <textarea
                        className="mt-1 min-h-20 w-full max-w-xl rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                        id="channel-routing"
                        onChange={(event) => setRouting(event.target.value)}
                        placeholder='[{"match": {"keyword": "status"}, "agentId": ""}]'
                        value={routing}
                      />
                      <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                        {t("routingHelp")}
                      </p>
                    </>
                  )}
                </div>
              ) : null}
              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  disabled={busy || !name || widgetBlocked}
                  onClick={() => void saveChannel()}
                  type="button"
                >
                  {editing ? t("saveChanges") : t("save")}
                </Button>
                {editing ? (
                  <Button onClick={resetForm} type="button" variant="outline">
                    {t("cancelEdit")}
                  </Button>
                ) : null}
              </div>
            </section>
          }
        >
          {loading ? (
            <div className="space-y-2" aria-busy="true">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <p className="sr-only">{t("loading")}</p>
            </div>
          ) : null}
          {!loading && !error && rows.length === 0 ? <EmptyState title={t("empty")} /> : null}
          <ul className="row-list">
            {rows.map((row) => (
              <li className="p-4" key={row.id}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="text-base font-medium">{row.name}</h2>
                    <p className="text-sm text-[var(--muted-foreground)]">
                      {row.kind} · {t("status")} {row.status} · {row.identitiesCount ?? 0}{" "}
                      {t("identities")}
                      {row.defaultAgent ? ` · ${t("agent")} ${row.defaultAgent.name}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      aria-label={t("editNamed", { name: row.name })}
                      onClick={() => void startEdit(row.id)}
                      type="button"
                      variant="outline"
                    >
                      {t("edit")}
                    </Button>
                    {row.kind === "widget" ? (
                      <Button
                        aria-label={t("installNamed", { name: row.name })}
                        onClick={() => void showInstall(row.id)}
                        type="button"
                        variant="outline"
                      >
                        {t("install")}
                      </Button>
                    ) : null}
                    <Button
                      aria-label={t("testNamed", { name: row.name })}
                      onClick={() => void testConnection(row.id)}
                      type="button"
                      variant="outline"
                    >
                      {t("test")}
                    </Button>
                    <Button
                      aria-label={t(row.status === "disabled" ? "turnOnNamed" : "turnOffNamed", {
                        name: row.name,
                      })}
                      onClick={() =>
                        void setStatus(row, row.status === "disabled" ? "active" : "disabled")
                      }
                      type="button"
                      variant="ghost"
                    >
                      {t(row.status === "disabled" ? "turnOn" : "turnOff")}
                    </Button>
                    <Button
                      aria-label={t("deleteNamed", { name: row.name })}
                      onClick={() => setRemoving(row)}
                      type="button"
                      variant="ghost"
                    >
                      {t("delete")}
                    </Button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {selected ? (
            <section className="mt-6">
              <h2 className="text-sm font-medium">{t("recent")}</h2>
              <label className="mt-3 block text-sm">
                {t("postChannel")}
                <select
                  className="ml-3 max-w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
                  value={selected.id}
                  onChange={(event) => void showPosts(event.target.value)}
                >
                  {rows.map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.name}
                    </option>
                  ))}
                </select>
              </label>
              {(selected.recentPosts ?? []).length === 0 ? (
                <p className="mt-2 text-sm text-[var(--muted-foreground)]">{t("noPosts")}</p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {(selected.recentPosts ?? []).map((post) => (
                    <li
                      className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
                      key={post.id}
                    >
                      {post.body}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ) : null}
        </ManagementLayout>
      </fieldset>
      <ConfirmDialog
        body={t("deleteBody", { name: removing?.name ?? "" })}
        confirmLabel={t("delete")}
        onClose={() => setRemoving(null)}
        onConfirm={async () => {
          if (removing) await remove(removing);
          setRemoving(null);
        }}
        open={removing !== null}
        title={t("deleteTitle", { name: removing?.name ?? "" })}
      />
    </AppShell>
  );
}
