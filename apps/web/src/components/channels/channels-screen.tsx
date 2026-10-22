"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

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

  function toggleMode() {
    const next = !advanced;
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }

  async function createChannel() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const credentials =
        kind === "slack"
          ? { botToken: token, signingSecret: "demo-signing-secret" }
          : kind === "teams"
            ? { appId: "app", appPassword: token }
            : kind === "email"
              ? { username: "agent", password: token }
              : { widgetSecret: token };
      await api("/api/v1/channel-integrations", {
        method: "POST",
        body: JSON.stringify({
          kind,
          name,
          defaultAgentId: agentId || undefined,
          credentials,
          agentRouting: advanced && routing ? JSON.parse(routing) : [],
          config: { command: "/agent", allowedChannelIds: [] },
        }),
      });
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
    }
  }

  return (
    <AppShell>
      <PageHeader body={t("body")} title={t("title")} />
      <div className="mb-4">
        <Button onClick={toggleMode} type="button" variant="outline">
          {advanced ? t("simple") : t("advanced")}
        </Button>
      </div>
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
        <h2 className="text-sm font-medium">{t("create")}</h2>
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
          {t("token")}
        </label>
        <Input
          className="mt-1 max-w-md"
          id="channel-token"
          onChange={(event) => setToken(event.target.value)}
          type="password"
          value={token}
        />
        {advanced ? (
          <div className="mt-3">
            <label className="block text-sm" htmlFor="channel-agent">
              Agent
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
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">{t("routingHelp")}</p>
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
      {loading ? (
        <div className="space-y-2" aria-busy="true">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <p className="sr-only">{t("loading")}</p>
        </div>
      ) : null}
      {!loading && rows.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
      ) : null}
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
              <Button onClick={() => void testConnection(row.id)} type="button" variant="outline">
                {t("test")}
              </Button>
            </div>
          </li>
        ))}
      </ul>
      {selected ? (
        <section className="mt-6">
          <h2 className="text-sm font-medium">{t("recent")}</h2>
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
    </AppShell>
  );
}
