"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { CodeSample } from "@/components/common/code-sample";
import { ActionStatus, DetailState } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { ReferencePicker } from "@/components/common/reference-picker";
import { SettingsMode } from "@/components/common/settings-mode";
import { ConfirmDialog } from "@/components/models/dialogs";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { isAvailableAgent } from "@/lib/agent-availability";
import { api } from "@/lib/api";
import { clearCachedSession, loadSession } from "@/lib/session";
import { exactOrigins } from "@/lib/widget-origins";

import {
  type ChannelKind,
  CredentialFields,
  type CredentialValues,
  channelKinds,
  credentialBody,
  credentialsValid,
} from "./credential-fields";

type Post = { id: string; body: string; status?: string };
type AgentRow = {
  id: string;
  name?: string;
  slug?: string;
  status?: string;
  disabled?: boolean;
  visibility?: string;
  publishedVersion?: number | null;
  published?: { version?: number } | null;
};
type Limits = {
  maxMessages: string;
  maxMessageChars: string;
  sessionsPerMinute: string;
  sessionsPerClientPerMinute: string;
  sessionMinutes: string;
};
type Integration = {
  id: string;
  kind: ChannelKind;
  name: string;
  status?: string;
  identitiesCount?: number;
  defaultAgent?: { id: string; name: string } | null;
  config?: Record<string, unknown>;
  recentPosts?: Post[];
};
const MODE_KEY = "ar-settings-mode";
const selectClass =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm";
// What the server applies when a limit is left as it is.
const LIMITS: Limits = {
  maxMessages: "30",
  maxMessageChars: "2000",
  sessionsPerMinute: "60",
  sessionsPerClientPerMinute: "10",
  sessionMinutes: "30",
};
const LIMIT_FIELDS = [
  ["maxMessages", "widgetMaxMessages", 1000],
  ["maxMessageChars", "widgetMaxChars", 32000],
  ["sessionsPerMinute", "widgetSessionsPerMinute", 6000],
  ["sessionsPerClientPerMinute", "widgetSessionsPerVisitor", 600],
  ["sessionMinutes", "widgetSessionMinutes", 1440],
] as const;

function whole(value: string, fallback: number): number {
  const number = Math.floor(Number(value));
  return Number.isFinite(number) && number > 0 ? number : fallback;
}

function numberText(value: unknown, fallback: string, divide = 1): string {
  return typeof value === "number" && value > 0 ? String(Math.round(value / divide)) : fallback;
}

function originsOf(config: Record<string, unknown> | undefined): string {
  const raw = config?.allowedOrigins;
  return Array.isArray(raw)
    ? raw.filter((value): value is string => typeof value === "string").join("\n")
    : "";
}

/** Two agents of one name are told apart by their slug. */
function agentDescription(row: AgentRow): string {
  return row.slug ? `${row.slug} · ${row.id}` : row.id;
}

export function ChannelsScreen() {
  const t = useTranslations("channels");
  const availability = useTranslations("agentAvailability");
  const [rows, setRows] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [canManage, setCanManage] = useState(false);
  const [canChooseAgent, setCanChooseAgent] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<ChannelKind>("slack");
  const [credentials, setCredentials] = useState<CredentialValues>({});
  const [origins, setOrigins] = useState("");
  const [agentId, setAgentId] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [editing, setEditing] = useState<Integration | null>(null);
  const [replaceCredentials, setReplaceCredentials] = useState(false);
  const nameInput = useRef<HTMLInputElement>(null);
  const editButton = useRef<HTMLButtonElement>(null);
  const [query, setQuery] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [focusDetails, setFocusDetails] = useState(false);
  const detailsHeading = useRef<HTMLHeadingElement>(null);
  const viewButton = useRef<HTMLButtonElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const [detail, setDetail] = useState<{
    id: string;
    value: Integration | null;
    loading: boolean;
    error: string;
  }>({ id: "", value: null, loading: false, error: "" });
  const detailRequest = useRef(0);
  const [embed, setEmbed] = useState("");
  // A widget: who may chat, and for one open to anyone, the account and limits visitors get.
  const [access, setAccess] = useState("signed");
  const [visitorEmail, setVisitorEmail] = useState("");
  const [visitorNotice, setVisitorNotice] = useState("");
  const [limits, setLimits] = useState<Limits>(LIMITS);
  const [showSources, setShowSources] = useState(true);
  const anyone = kind === "widget" && access === "public";
  // Whether this workspace may have widgets at all, and whether this person may change that.
  const [widgetOn, setWidgetOn] = useState<boolean | null>(null);
  const [manageTenant, setManageTenant] = useState(false);
  const widgetBlocked = kind === "widget" && widgetOn === false && !editing;
  const [removing, setRemoving] = useState<Integration | null>(null);
  const [actionError, setActionError] = useState("");
  const [chosenAgent, setChosenAgent] = useState<AgentRow | null>(null);

  const statusLabel = (value: string) =>
    t.has(`statuses.${value}`) ? t(`statuses.${value}`) : value;
  const kindLabel = (value: string) => (t.has(`kinds.${value}`) ? t(`kinds.${value}`) : value);
  const filtered = rows.filter(
    (row) =>
      (!kindFilter || row.kind === kindFilter) &&
      (!statusFilter || row.status === statusFilter) &&
      [row.name, row.id, row.defaultAgent?.name, kindLabel(row.kind)].some((value) =>
        value?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
      ),
  );
  const pagination = usePagedRows(filtered, `${query}::${kindFilter}::${statusFilter}`);
  const statuses = [...new Set(rows.flatMap((row) => (row.status ? [row.status] : [])))].sort();
  const selectedRow = rows.find((row) => row.id === selectedId);
  const selected = detail.id === selectedId ? detail.value : null;
  useEffect(() => {
    if (focusDetails && selectedRow) {
      detailsHeading.current?.focus();
      setFocusDetails(false);
    }
  }, [focusDetails, selectedRow]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const session = await loadSession();
      const allowed = session.permissions?.includes("channels:manage") ?? false;
      setCanManage(allowed);
      setCanChooseAgent(session.permissions?.includes("agents:read") ?? false);
      setWidgetOn(session.features?.widget === true);
      setManageTenant(session.permissions?.includes("tenant:manage") ?? false);
      if (!allowed) {
        setRows([]);
        setSelectedId("");
        return;
      }
      const page = await api<{ items: Integration[] }>("/api/v1/channel-integrations");
      const list = page.items ?? [];
      setRows(list);
      setSelectedId((current) =>
        list.some((row) => row.id === current) ? current : (list[0]?.id ?? ""),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);
  const loadDetail = useCallback(
    async (id: string) => {
      const ticket = ++detailRequest.current;
      setDetail({ id, value: null, loading: Boolean(id), error: "" });
      if (!id) return;
      try {
        const value = await api<Integration>(`/api/v1/channel-integrations/${id}`);
        if (ticket === detailRequest.current) setDetail({ id, value, loading: false, error: "" });
      } catch (caught) {
        if (ticket === detailRequest.current)
          setDetail({
            id,
            value: null,
            loading: false,
            error: caught instanceof Error ? caught.message : t("detailError"),
          });
      }
    },
    [t],
  );
  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
    void load();
  }, [load]);
  useEffect(() => {
    void loadDetail(selectedId);
    return () => {
      detailRequest.current += 1;
    };
  }, [selectedId, loadDetail]);
  useEffect(() => {
    if (editing) nameInput.current?.focus();
  }, [editing]);
  useEffect(() => {
    setEmbed(
      selected?.kind === "widget"
        ? `<script src="${window.location.origin}/widget.js" data-integration="${selected.id}"></script>`
        : "",
    );
  }, [selected]);
  // What the chosen agent's state means for people reaching it through this channel.
  useEffect(() => {
    setChosenAgent(null);
    if (!agentId || !canChooseAgent) return;
    let current = true;
    api<AgentRow>(`/api/v1/agents/${encodeURIComponent(agentId)}`)
      .then((row) => {
        if (current && row?.id === agentId) setChosenAgent(row);
      })
      .catch(() => {
        if (current) setChosenAgent(null);
      });
    return () => {
      current = false;
    };
  }, [agentId, canChooseAgent]);
  function chooseMode(next: boolean) {
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }
  function resetForm() {
    setEditing(null);
    setReplaceCredentials(false);
    setName("");
    setAgentId("");
    setKind("slack");
    setCredentials({});
    setOrigins("");
    setWidgetFields(undefined);
    setSaveError("");
  }
  function setWidgetFields(config: Record<string, unknown> | undefined) {
    setOrigins(originsOf(config));
    setAccess(config?.access === "public" ? "public" : "signed");
    setVisitorEmail(typeof config?.visitorEmail === "string" ? config.visitorEmail : "");
    setVisitorNotice(typeof config?.notice === "string" ? config.notice : "");
    setLimits(
      config
        ? {
            maxMessages: numberText(config.maxMessages, LIMITS.maxMessages),
            maxMessageChars: numberText(config.maxMessageChars, LIMITS.maxMessageChars),
            sessionsPerMinute: numberText(config.sessionsPerMinute, LIMITS.sessionsPerMinute),
            sessionsPerClientPerMinute: numberText(
              config.sessionsPerClientPerMinute,
              LIMITS.sessionsPerClientPerMinute,
            ),
            sessionMinutes: numberText(config.sessionSeconds, LIMITS.sessionMinutes, 60),
          }
        : LIMITS,
    );
    setShowSources(config?.showSources !== false);
  }
  async function edit(row: Integration, trigger: HTMLButtonElement) {
    editButton.current = trigger;
    setEditing(row);
    setReplaceCredentials(false);
    setName(row.name);
    setAgentId(row.defaultAgent?.id ?? "");
    setKind(row.kind);
    setCredentials({});
    setWidgetFields(row.config);
    setSaveError("");
    setNotice("");
    if (row.kind !== "widget") return;
    // A widget's saved settings come with its details, not with the list.
    try {
      const value =
        selected?.id === row.id
          ? selected
          : await api<Integration>(`/api/v1/channel-integrations/${encodeURIComponent(row.id)}`);
      setEditing((current) => (current?.id === row.id ? value : current));
      setWidgetFields(value.config);
    } catch (caught) {
      setSaveError(caught instanceof Error ? caught.message : t("detailError"));
    }
  }
  /** The widget settings to save, or null with the reason shown when they are not valid. */
  function widgetConfig(): Record<string, unknown> | null {
    const requested = [...new Set(origins.split(/[\s,]+/).filter(Boolean))];
    const allowedOrigins = exactOrigins(requested);
    if (!allowedOrigins.length || allowedOrigins.length !== requested.length) {
      setSaveError(t("invalidOrigins"));
      return null;
    }
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
  async function save() {
    if (saving || !canManage) return;
    setSaveError("");
    setNotice("");
    if (!name.trim() || !agentId) {
      setSaveError(t("requiredSetup"));
      return;
    }
    if (widgetBlocked) return;
    // A widget open to anyone has no host secret: nothing signs its visitors in.
    const askCredentials = !anyone && (!editing || replaceCredentials);
    if (askCredentials && !credentialsValid(kind, credentials)) {
      setSaveError(t("invalidCredentials"));
      return;
    }
    const config = kind === "widget" ? widgetConfig() : {};
    if (!config) return;
    setSaving(true);
    try {
      const body = editing
        ? {
            name: name.trim(),
            defaultAgentId: agentId,
            ...(askCredentials ? { credentials: credentialBody(kind, credentials) } : {}),
            ...(kind === "widget" ? { config } : {}),
          }
        : {
            kind,
            name: name.trim(),
            defaultAgentId: agentId,
            credentials: anyone ? {} : credentialBody(kind, credentials),
            config,
          };
      const saved = await api<Integration>(
        editing ? `/api/v1/channel-integrations/${editing.id}` : "/api/v1/channel-integrations",
        { method: editing ? "PATCH" : "POST", body: JSON.stringify(body) },
      );
      resetForm();
      setNotice(t("saved"));
      await load();
      setSelectedId(saved.id);
      setFocusDetails(true);
      setQuery("");
      setKindFilter("");
      setStatusFilter("");
      if (saved.id === selectedId) await loadDetail(saved.id);
    } catch (caught) {
      setSaveError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setSaving(false);
    }
  }
  async function setStatus(row: Integration, status: "active" | "disabled") {
    if (saving) return;
    setSaving(true);
    setActionError("");
    setNotice("");
    try {
      await api(`/api/v1/channel-integrations/${encodeURIComponent(row.id)}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setNotice(t(status === "disabled" ? "turnedOff" : "turnedOn", { name: row.name }));
      await load();
      if (row.id === selectedId) await loadDetail(row.id);
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setSaving(false);
    }
  }
  async function remove(row: Integration) {
    setActionError("");
    setNotice("");
    try {
      await api(`/api/v1/channel-integrations/${encodeURIComponent(row.id)}`, {
        method: "DELETE",
      });
      if (editing?.id === row.id) resetForm();
      setNotice(t("deleted", { name: row.name }));
      await load();
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : t("error"));
    }
  }
  async function switchWidget(next: boolean) {
    if (saving) return;
    setSaving(true);
    setActionError("");
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
      setActionError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setSaving(false);
    }
  }
  const chosenVersion = chosenAgent?.publishedVersion ?? chosenAgent?.published?.version ?? null;

  return (
    <AppShell>
      <PageHeader
        title={t("title")}
        body={t("body")}
        actions={<SettingsMode advanced={advanced} onChange={chooseMode} />}
      />
      <ActionStatus busy={saving} notice={notice} />
      <DetailState loading={loading && !canManage} error={error} onRetry={() => void load()} />
      {!loading && !error && !canManage ? <p className="text-sm">{t("denied")}</p> : null}
      {canManage && widgetOn !== null ? (
        <section
          aria-labelledby="widget-feature-title"
          className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
        >
          <div className="min-w-0">
            <h2 className="text-base font-medium" id="widget-feature-title">
              {t("widgetFeature")}
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-[var(--muted-foreground)]">
              {t(widgetOn ? "widgetFeatureOn" : "widgetFeatureOff")}
            </p>
          </div>
          {manageTenant ? (
            <Button
              disabled={saving}
              onClick={() => void switchWidget(!widgetOn)}
              type="button"
              variant={widgetOn ? "outline" : "default"}
            >
              {t(widgetOn ? "widgetTurnOff" : "widgetTurnOn")}
            </Button>
          ) : (
            <p className="text-sm text-[var(--muted-foreground)]">{t("widgetAskAdmin")}</p>
          )}
        </section>
      ) : null}
      {actionError ? (
        <p className="mb-4 text-sm text-[var(--destructive)]" role="alert">
          {actionError}
        </p>
      ) : null}
      {canManage ? (
        <ManagementLayout
          title={t("listTitle")}
          formTitle={editing ? t("editTitle", { name: editing.name }) : t("create")}
          form={
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                void save();
              }}
            >
              <fieldset disabled={saving || loading} className="grid min-w-0 gap-4">
                {editing ? (
                  <p className="text-sm text-[var(--muted-foreground)]">{t("editHelp")}</p>
                ) : null}
                <label className="text-sm" htmlFor="channel-name">
                  {t("name")}
                  <Input
                    ref={nameInput}
                    className="mt-1"
                    id="channel-name"
                    required
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                  />
                </label>
                <label className="text-sm" htmlFor="channel-kind">
                  {t("kind")}
                  <select
                    id="channel-kind"
                    className={`mt-1 ${selectClass}`}
                    disabled={Boolean(editing)}
                    value={kind}
                    onChange={(event) => {
                      setKind(event.target.value as ChannelKind);
                      setCredentials({});
                      setWidgetFields(undefined);
                      setSaveError("");
                    }}
                  >
                    {channelKinds.map((value) => (
                      <option key={value} value={value}>
                        {kindLabel(value)}
                      </option>
                    ))}
                  </select>
                </label>
                {widgetBlocked ? (
                  <p className="text-sm text-[var(--destructive)]" role="alert">
                    {t(manageTenant ? "widgetOffTurnOn" : "widgetOffAsk")}
                  </p>
                ) : null}
                <ReferencePicker<AgentRow>
                  key={editing?.id ?? "new"}
                  label={t("agent")}
                  endpoint="/api/v1/agents"
                  filterRow={isAvailableAgent}
                  emptyMessage={availability("empty")}
                  getDescription={agentDescription}
                  value={agentId}
                  selection={editing?.defaultAgent}
                  onChange={setAgentId}
                  required
                  disabled={saving || loading || !canChooseAgent}
                  help={`${t("agentHelp")} ${availability("help")}`}
                />
                {!canChooseAgent ? (
                  <p className="text-xs text-[var(--muted-foreground)]">{t("agentAccess")}</p>
                ) : null}
                {chosenAgent ? (
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {chosenVersion
                      ? t("agentVersion", { version: chosenVersion })
                      : t("agentUnpublished")}{" "}
                    {chosenAgent.visibility && chosenAgent.visibility !== "tenant" ? (
                      <>
                        {t("agentNotShared")}{" "}
                        <Link className="underline" href={`/agents/${chosenAgent.id}`}>
                          {t("agentOpen", { name: chosenAgent.name || chosenAgent.id })}
                        </Link>
                      </>
                    ) : null}
                  </p>
                ) : null}
                {kind === "widget" ? (
                  <div className="text-sm">
                    <label htmlFor="widget-access">{t("widgetAccess")}</label>
                    <select
                      id="widget-access"
                      className={`mt-1 ${selectClass}`}
                      aria-describedby="widget-access-help"
                      value={access}
                      onChange={(event) => setAccess(event.target.value)}
                    >
                      <option value="signed">{t("widgetAccessSigned")}</option>
                      <option value="public">{t("widgetAccessPublic")}</option>
                    </select>
                    <span
                      id="widget-access-help"
                      className="mt-1 block text-xs text-[var(--muted-foreground)]"
                    >
                      {t(anyone ? "widgetAccessPublicHelp" : "widgetAccessSignedHelp")}
                    </span>
                  </div>
                ) : null}
                {editing && !anyone ? (
                  <label className="text-sm">
                    <input
                      className="mr-2"
                      type="checkbox"
                      checked={replaceCredentials}
                      onChange={(event) => {
                        setReplaceCredentials(event.target.checked);
                        setCredentials({});
                      }}
                    />
                    {t("replaceCredentials")}
                  </label>
                ) : null}
                {editing && !anyone && replaceCredentials ? (
                  <p className="text-xs text-[var(--muted-foreground)]">{t("replaceHelp")}</p>
                ) : null}
                {!anyone && (!editing || replaceCredentials) ? (
                  <CredentialFields
                    kind={kind}
                    values={credentials}
                    advanced={advanced || replaceCredentials}
                    onChange={setCredentials}
                  />
                ) : null}
                {anyone ? (
                  <div className="grid gap-4">
                    <div className="text-sm">
                      <label htmlFor="widget-visitor">{t("widgetVisitor")}</label>
                      <Input
                        className="mt-1"
                        id="widget-visitor"
                        aria-describedby="widget-visitor-help"
                        type="email"
                        value={visitorEmail}
                        onChange={(event) => setVisitorEmail(event.target.value)}
                      />
                      <span
                        id="widget-visitor-help"
                        className="mt-1 block text-xs text-[var(--muted-foreground)]"
                      >
                        {t("widgetVisitorHelp")}
                      </span>
                    </div>
                    <div className="text-sm">
                      <label htmlFor="widget-notice">{t("widgetNotice")}</label>
                      <textarea
                        id="widget-notice"
                        aria-describedby="widget-notice-help"
                        className="mt-1 min-h-16 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                        rows={2}
                        value={visitorNotice}
                        onChange={(event) => setVisitorNotice(event.target.value)}
                      />
                      <span
                        id="widget-notice-help"
                        className="mt-1 block text-xs text-[var(--muted-foreground)]"
                      >
                        {t("widgetNoticeHelp")}
                      </span>
                    </div>
                    <fieldset className="grid min-w-0 gap-3">
                      <legend className="mb-1 text-sm font-medium">{t("widgetLimits")}</legend>
                      <div className="flex flex-wrap gap-4">
                        {LIMIT_FIELDS.map(([key, label, most]) => (
                          <label className="text-sm" htmlFor={`widget-${key}`} key={key}>
                            {t(label)}
                            <Input
                              className="mt-1 w-28"
                              id={`widget-${key}`}
                              max={most}
                              min={1}
                              type="number"
                              value={limits[key]}
                              onChange={(event) =>
                                setLimits((current) => ({ ...current, [key]: event.target.value }))
                              }
                            />
                          </label>
                        ))}
                      </div>
                      <p className="text-xs text-[var(--muted-foreground)]">
                        {t("widgetLimitsHelp")}
                      </p>
                    </fieldset>
                  </div>
                ) : null}
                {kind === "widget" ? (
                  <div>
                    <label className="text-sm" htmlFor="widget-origins">
                      {t("origins")}
                    </label>
                    <textarea
                      className="mt-1 min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                      id="widget-origins"
                      aria-describedby="widget-origins-help"
                      required
                      value={origins}
                      onChange={(event) => setOrigins(event.target.value)}
                    />
                    <p
                      id="widget-origins-help"
                      className="mt-1 text-xs text-[var(--muted-foreground)]"
                    >
                      {t("originsHelp")}
                    </p>
                    <label className="mt-3 flex items-start gap-2 text-sm">
                      <input
                        checked={showSources}
                        className="mt-1"
                        type="checkbox"
                        onChange={(event) => setShowSources(event.target.checked)}
                      />
                      <span>
                        {t("showSources")}
                        <span className="block text-xs text-[var(--muted-foreground)]">
                          {t("showSourcesHelp")}
                        </span>
                      </span>
                    </label>
                  </div>
                ) : null}
                {saveError ? (
                  <p role="alert" className="text-sm text-[var(--destructive)]">
                    {saveError}
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="submit"
                    disabled={saving || loading || !agentId || !name.trim() || widgetBlocked}
                  >
                    {t(editing ? "saveChanges" : "save")}
                  </Button>
                  {editing ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        resetForm();
                        if (editButton.current?.isConnected) editButton.current.focus();
                        else nameInput.current?.focus();
                      }}
                    >
                      {t("cancelEdit")}
                    </Button>
                  ) : null}
                </div>
              </fieldset>
            </form>
          }
        >
          <p className="mb-4 text-sm text-[var(--muted-foreground)]">{t("verificationHelp")}</p>
          {rows.length > 0 ? (
            <fieldset className="mb-4 grid gap-3" aria-label={t("filters")}>
              <Input
                type="search"
                aria-label={t("search")}
                placeholder={t("search")}
                ref={searchInput}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <div className="flex flex-wrap gap-3">
                <label className="text-sm">
                  {t("kind")}
                  <select
                    className={selectClass}
                    value={kindFilter}
                    onChange={(event) => setKindFilter(event.target.value)}
                  >
                    <option value="">{t("allKinds")}</option>
                    {[...new Set(rows.map((row) => row.kind))].sort().map((value) => (
                      <option key={value} value={value}>
                        {kindLabel(value)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm">
                  {t("status")}
                  <select
                    className={selectClass}
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value)}
                  >
                    <option value="">{t("allStatuses")}</option>
                    {statuses.map((value) => (
                      <option key={value} value={value}>
                        {statusLabel(value)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </fieldset>
          ) : null}
          <DetailState loading={loading} error="" />
          {!loading && !error && filtered.length === 0 ? (
            <EmptyState compact title={t(rows.length ? "noMatches" : "empty")} />
          ) : null}
          <ul className="row-list">
            {!loading && !error
              ? pagination.rows.map((row) => (
                  <li className="space-y-3 p-4" key={row.id}>
                    <h2 className="break-words text-sm font-medium">{row.name}</h2>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge>{kindLabel(row.kind)}</Badge>
                      <Badge>{statusLabel(row.status ?? "")}</Badge>
                    </div>
                    <p className="break-words text-sm text-[var(--muted-foreground)]">
                      {t("agent")}: {row.defaultAgent?.name || t("unassigned")} ·{" "}
                      {t("linkedPeople", { count: row.identitiesCount ?? 0 })}
                    </p>
                    <p title={row.id} className="break-all text-xs text-[var(--muted-foreground)]">
                      {t("reference", { id: advanced ? row.id : row.id.slice(-8) })}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        aria-pressed={selectedId === row.id}
                        onClick={(event) => {
                          viewButton.current = event.currentTarget;
                          setSelectedId(row.id);
                          setFocusDetails(true);
                        }}
                      >
                        {t("showDetails")}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        disabled={saving}
                        aria-label={t("editNamed", { name: row.name })}
                        onClick={(event) => void edit(row, event.currentTarget)}
                      >
                        {t("edit")}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        disabled={saving}
                        aria-label={t(row.status === "disabled" ? "turnOnNamed" : "turnOffNamed", {
                          name: row.name,
                        })}
                        onClick={() =>
                          void setStatus(row, row.status === "disabled" ? "active" : "disabled")
                        }
                      >
                        {t(row.status === "disabled" ? "turnOn" : "turnOff")}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        aria-label={t("deleteNamed", { name: row.name })}
                        onClick={() => setRemoving(row)}
                      >
                        {t("delete")}
                      </Button>
                    </div>
                  </li>
                ))
              : null}
          </ul>
          {!loading && !error && rows.length > 0 ? (
            <ListPagination {...pagination} label={t("listTitle")} />
          ) : null}
          {selectedRow ? (
            <section className="mt-8" aria-label={t("details")}>
              <h2
                ref={detailsHeading}
                tabIndex={-1}
                className="mb-3 break-words text-sm font-semibold focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-4"
              >
                {t("detailsFor", { name: selectedRow.name })}
              </h2>
              <Button
                className="mb-4"
                type="button"
                variant="outline"
                onClick={() => {
                  if (viewButton.current?.isConnected) viewButton.current.focus();
                  else searchInput.current?.focus();
                }}
              >
                {t("backToList")}
              </Button>
              <DetailState
                loading={detail.id !== selectedId || detail.loading}
                error={detail.id === selectedId ? detail.error : ""}
                onRetry={() => void loadDetail(selectedId)}
              />
              {selected ? (
                <>
                  {selected.kind === "slack" || selected.kind === "teams" ? (
                    <Button asChild variant="outline">
                      <a href={`/api/v1/channel-integrations/${selected.id}/manifest`}>
                        {t("manifest")}
                      </a>
                    </Button>
                  ) : null}
                  {embed ? (
                    <div className="mb-5 rounded-lg border border-[var(--border)] p-4">
                      <h3 className="text-sm font-medium">{t("embedTitle")}</h3>
                      <p className="mt-2 text-sm text-[var(--muted-foreground)]">
                        {t(selected.config?.access === "public" ? "embedHelpPublic" : "embedHelp")}
                      </p>
                      <div className="mt-3">
                        <CodeSample title={t("embedCode")} value={embed} />
                      </div>
                    </div>
                  ) : null}
                  {selected.kind === "widget" ? (
                    <div className="mt-4">
                      <label className="text-sm font-medium" htmlFor="saved-widget-origins">
                        {t("savedOrigins")}
                      </label>
                      <textarea
                        id="saved-widget-origins"
                        className="mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-xs"
                        rows={3}
                        readOnly
                        value={
                          Array.isArray(selected.config?.allowedOrigins)
                            ? selected.config.allowedOrigins
                                .filter((value): value is string => typeof value === "string")
                                .join("\n")
                            : ""
                        }
                      />
                    </div>
                  ) : null}
                  <h3 className="mt-5 text-sm font-medium">{t("recent")}</h3>
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">{t("postsHelp")}</p>
                  {(selected.recentPosts ?? []).length === 0 ? (
                    <p className="mt-3 text-sm text-[var(--muted-foreground)]">{t("noPosts")}</p>
                  ) : (
                    <ul className="mt-3 space-y-2">
                      {selected.recentPosts?.map((post) => (
                        <li
                          key={post.id}
                          className="whitespace-pre-wrap break-words rounded-lg border border-[var(--border)] p-3 text-sm"
                        >
                          {post.body}
                          {post.status ? (
                            <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                              {t("recordedStatus", { status: post.status })}
                            </p>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              ) : null}
            </section>
          ) : null}
        </ManagementLayout>
      ) : null}
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
