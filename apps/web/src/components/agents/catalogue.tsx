"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

import type { AgentSummary } from "./types";

export function AgentCatalogue() {
  const t = useTranslations("agents");
  const router = useRouter();
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (query.trim()) {
      params.set("q", query.trim());
    }
    if (status) {
      params.set("status", status);
    }
    const suffix = params.size ? `?${params.toString()}` : "";
    try {
      const page = await api<{ items: AgentSummary[] }>(`/api/v1/agents${suffix}`);
      setAgents(page.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [query, status, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function favourite(agent: AgentSummary) {
    await api("/api/v1/me/agent-favourites", {
      method: "PUT",
      body: JSON.stringify({ agentId: agent.id, favourite: !agent.favourite }),
    });
    await load();
  }

  async function chat(agent: AgentSummary) {
    const created = await api<{ id: string }>("/api/v1/conversations", {
      method: "POST",
      body: JSON.stringify({ agentId: agent.id }),
    });
    router.push(`/chat?conversation=${created.id}`);
  }

  return (
    <div>
      <PageHeader body={t("body")} title={t("title")} />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Input
          aria-label={t("search")}
          className="max-w-sm"
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("search")}
          value={query}
        />
        <select
          aria-label={t("status")}
          className="h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
          onChange={(event) => setStatus(event.target.value)}
          value={status}
        >
          <option value="">{t("anyStatus")}</option>
          <option value="published">{t("published")}</option>
          <option value="draft">{t("draftStatus")}</option>
          <option value="archived">{t("archived")}</option>
        </select>
        <Button onClick={() => router.push("/agents/new")} type="button">
          {t("create")}
        </Button>
      </div>
      {loading ? <p className="text-sm text-[var(--muted-foreground)]">{t("loading")}</p> : null}
      {error ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      {!loading && !error && agents.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
      ) : null}
      <ul className="grid gap-3 sm:grid-cols-2">
        {agents.map((agent) => (
          <li
            className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
            key={agent.id}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="text-base font-medium">{agent.name}</h2>
                <p className="text-sm text-[var(--muted-foreground)]">{agent.description}</p>
              </div>
              <span className="rounded-full bg-[var(--muted)] px-2 py-1 text-xs">
                {agent.status}
              </span>
            </div>
            {agent.greeting ? <p className="mt-3 text-sm">{agent.greeting}</p> : null}
            <p className="mt-3 text-xs text-[var(--muted-foreground)]">
              {t("owner")} {agent.owner?.displayName ?? t("unknownOwner")} · {t("version")}{" "}
              {agent.publishedVersion ?? "—"}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                onClick={() => router.push(`/agents/${agent.id}`)}
                type="button"
                variant="outline"
              >
                {t("open")}
              </Button>
              {agent.status === "published" ? (
                <Button onClick={() => void chat(agent)} type="button">
                  {t("chat")}
                </Button>
              ) : null}
              <Button onClick={() => void favourite(agent)} type="button" variant="ghost">
                {agent.favourite ? t("unfavourite") : t("favourite")}
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
