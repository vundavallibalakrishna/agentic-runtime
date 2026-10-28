"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus } from "@/components/common/detail-state";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { exactOrigins } from "@/lib/widget-origins";

type Agent = { id: string; name: string };
type Post = { id: string; body: string; status?: string };
type Integration = {
  id: string;
  kind: string;
  name: string;
  status?: string;
  statusDetail?: string;
  identitiesCount?: number;
  recentPosts?: Post[];
};

const MODE_KEY = "ar-settings-mode";

export function ChannelsScreen() {
  const t = useTranslations("channels");
  const [rows, setRows] = useState<Integration[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState("slack");
  const [token, setToken] = useState("");
  const [origins, setOrigins] = useState("");
  const [embed, setEmbed] = useState("");
  const [routing, setRouting] = useState("");
  const [agentId, setAgentId] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Integration | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [page, agentPage] = await Promise.all([
        api<{ items: Integration[] }>("/api/v1/channel-integrations"),
        api<{ items: Agent[] }>("/api/v1/agents"),
      ]);
      const list = page.items ?? [];
      setRows(list);
      const people = agentPage.items ?? [];
      setAgents(people);
      setAgentId((current) => current || people[0]?.id || "");
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

  async function createChannel() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const requestedOrigins = origins.split(/[\s,]+/).filter(Boolean);
      const allowedOrigins = exactOrigins(requestedOrigins);
      if (
        kind === "widget" &&
        (!allowedOrigins.length || allowedOrigins.length !== new Set(requestedOrigins).size)
      )
        throw new Error(t("invalidOrigins"));
      const credentials =
        kind === "slack"
          ? { botToken: token, signingSecret: "demo-signing-secret" }
          : kind === "teams"
            ? { appId: "app", appPassword: token }
            : kind === "email"
              ? { username: "agent", password: token }
              : { widgetSecret: token };
      const created = await api<Integration>("/api/v1/channel-integrations", {
        method: "POST",
        body: JSON.stringify({
          kind,
          name,
          defaultAgentId: agentId || undefined,
          credentials,
          agentRouting: advanced && routing ? JSON.parse(routing) : [],
          config:
            kind === "widget" ? { allowedOrigins } : { command: "/agent", allowedChannelIds: [] },
        }),
      });
      setEmbed(
        kind === "widget"
          ? `<script src="${window.location.origin}/widget.js" data-integration="${created.id}"></script>`
          : "",
      );
      setName("");
      setToken("");
      setNotice(t("saved"));
      await load();
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
        {notice ? <p className="mb-3 text-sm text-[var(--muted-foreground)]">{notice}</p> : null}

        {embed && (
          <section
            className="mb-6 rounded-xl border border-border bg-card p-4"
            aria-label={t("embedTitle")}
          >
            <h2 className="text-base font-medium">{t("embedTitle")}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{t("embedHelp")}</p>
            <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-all rounded-lg bg-muted p-3 text-xs">
              {embed}
            </pre>
          </section>
        )}
        <ManagementLayout
          title={t("listTitle")}
          formTitle={t("create")}
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
                id="channel-kind"
                onChange={(event) => setKind(event.target.value)}
                value={kind}
              >
                <option value="slack">Slack</option>
                <option value="teams">Teams</option>
                <option value="email">Email</option>
                <option value="widget">Widget</option>
              </select>
              <label className="mt-3 block text-sm" htmlFor="channel-token">
                {kind === "widget" ? t("widgetSecret") : t("token")}
              </label>
              <Input
                className="mt-1 max-w-md"
                id="channel-token"
                onChange={(event) => setToken(event.target.value)}
                type="password"
                value={token}
              />
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
                </div>
              )}
              {advanced || kind === "widget" ? (
                <div className="mt-3">
                  <label className="block text-sm" htmlFor="channel-agent">
                    {t("agent")}
                  </label>
                  <select
                    className="mt-1 max-w-md rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 text-sm"
                    id="channel-agent"
                    onChange={(event) => setAgentId(event.target.value)}
                    value={agentId}
                  >
                    {agents.map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.name}
                      </option>
                    ))}
                  </select>
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
              <Button
                className="mt-4"
                disabled={busy || !name}
                onClick={() => void createChannel()}
                type="button"
              >
                {t("save")}
              </Button>
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
          <ul className="space-y-3">
            {rows.map((row) => (
              <li
                className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
                key={row.id}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-base font-medium">{row.name}</h2>
                    <p className="text-sm text-[var(--muted-foreground)]">
                      {row.kind} · {t("status")} {row.status} · {row.identitiesCount ?? 0}{" "}
                      {t("identities")}
                    </p>
                  </div>
                  <Button
                    onClick={() => void testConnection(row.id)}
                    type="button"
                    variant="outline"
                  >
                    {t("test")}
                  </Button>
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
    </AppShell>
  );
}
