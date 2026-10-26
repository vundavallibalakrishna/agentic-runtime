"use client";

import {
  ArrowRight,
  ArrowUpRight,
  Bot,
  MessageSquare,
  Plus,
  Search,
  Sparkles,
  Star,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Session } from "@/lib/api";

import type { AgentSummary } from "./types";

export function AgentCatalogue() {
  const t = useTranslations("agents");
  const router = useRouter();
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [canCreate, setCanCreate] = useState(false);
  const [canChat, setCanChat] = useState(false);
  const [pending, setPending] = useState("");

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
      const [page, session] = await Promise.all([
        api<{ items: AgentSummary[] }>(`/api/v1/agents${suffix}`),
        api<Session>("/api/v1/auth/session"),
      ]);
      setCanCreate(session.permissions?.includes("agents:create") ?? false);
      setCanChat(session.permissions?.includes("chat:use") ?? false);
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

  async function act(agent: AgentSummary, action: "favourite" | "chat") {
    setPending(agent.id);
    setError("");
    try {
      if (action === "favourite") {
        await api("/api/v1/me/agent-favourites", {
          method: "PUT",
          body: JSON.stringify({ agentId: agent.id, favourite: !agent.favourite }),
        });
        setAgents((current) =>
          current.map((item) =>
            item.id === agent.id ? { ...item, favourite: !item.favourite } : item,
          ),
        );
      } else {
        const created = await api<{ id: string }>("/api/v1/conversations", {
          method: "POST",
          body: JSON.stringify({ agentId: agent.id }),
        });
        router.push(`/chat?conversation=${created.id}`);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setPending("");
    }
  }

  return (
    <div>
      <header className="mb-8 flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted-foreground)]">
            {t("eyebrow")}
          </p>
          <h1 className="text-3xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-[var(--muted-foreground)]">
            {t("body")}
          </p>
        </div>
        {canCreate ? (
          <Button asChild>
            <Link href="/agents/new" className="gap-2">
              <Plus size={16} aria-hidden="true" />
              {t("create")}
            </Link>
          </Button>
        ) : null}
      </header>
      {canCreate ? (
        <Link
          href="/agents/new"
          className="mb-8 flex items-center gap-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-[var(--shadow-xs)] hover:border-[var(--muted-foreground)] md:p-6"
        >
          <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-[var(--muted)]">
            <Sparkles size={23} strokeWidth={1.4} aria-hidden="true" />
          </span>
          <span className="flex-1">
            <span className="block text-base font-medium">{t("createHint")}</span>
            <span className="mt-1 block text-sm text-[var(--muted-foreground)]">
              {t("createBody")}
            </span>
          </span>
          <ArrowUpRight size={19} aria-hidden="true" />
        </Link>
      ) : null}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-sm font-semibold">
          {t("browse")}
          <span className="ml-2 font-normal text-[var(--muted-foreground)]">
            {!loading && !error ? t("results", { count: agents.length }) : ""}
          </span>
        </h2>
        <div className="flex w-full gap-2 sm:w-auto">
          <div className="relative min-w-0 flex-1">
            <Search
              size={15}
              aria-hidden="true"
              className="absolute left-3 top-3 text-[var(--muted-foreground)]"
            />
            <Input
              aria-label={t("search")}
              className="h-10 pl-9 sm:w-56"
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("search")}
              value={query}
            />
          </div>
          <select
            aria-label={t("status")}
            className="h-10 max-w-36 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-xs"
            onChange={(event) => setStatus(event.target.value)}
            value={status}
          >
            <option value="">{t("anyStatus")}</option>
            <option value="published">{t("published")}</option>
            <option value="draft">{t("draftStatus")}</option>
            <option value="archived">{t("archived")}</option>
          </select>
        </div>
      </div>
      {error ? (
        <div
          className="mb-5 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
          role="alert"
        >
          <p className="text-sm text-[var(--destructive)]">{error}</p>
          <Button className="mt-3" onClick={() => void load()} type="button" variant="outline">
            {t("retry")}
          </Button>
        </div>
      ) : null}
      {loading ? (
        <div
          role="status"
          aria-busy="true"
          aria-label={t("catalogueLoading")}
          className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
        >
          {[0, 1, 2].map((id) => (
            <div
              key={id}
              className="space-y-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5"
            >
              <Skeleton className="size-10 rounded-xl" />
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ))}
        </div>
      ) : null}
      {!loading && !error && agents.length === 0 ? (
        <div className="flex flex-col items-center rounded-2xl border border-dashed border-[var(--border)] px-6 py-16 text-center">
          <Bot
            size={30}
            strokeWidth={1.4}
            className="mb-4 text-[var(--muted-foreground)]"
            aria-hidden="true"
          />
          <p className="max-w-sm text-sm text-[var(--muted-foreground)]">
            {query || status ? t("emptyFiltered") : t("emptyTitle")}
          </p>
          {query || status ? (
            <Button
              className="mt-5"
              onClick={() => {
                setQuery("");
                setStatus("");
              }}
              type="button"
              variant="outline"
            >
              {t("clearFilters")}
            </Button>
          ) : canCreate ? (
            <Button className="mt-5" asChild>
              <Link href="/agents/new">{t("create")}</Link>
            </Button>
          ) : null}
        </div>
      ) : null}
      {!loading ? (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {agents.map((agent) => (
            <li
              className="flex min-w-0 flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-[var(--shadow-xs)]"
              key={agent.id}
            >
              <div className="mb-5 flex items-center justify-between">
                <span className="flex size-11 items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--background)]">
                  <Bot size={23} strokeWidth={1.4} aria-hidden="true" />
                </span>
                <button
                  aria-label={`${agent.favourite ? t("unfavourite") : t("favourite")}: ${agent.name}`}
                  aria-pressed={Boolean(agent.favourite)}
                  className="rounded-lg p-2 text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                  disabled={pending === agent.id}
                  onClick={() => void act(agent, "favourite")}
                  type="button"
                >
                  <Star
                    size={17}
                    fill={agent.favourite ? "currentColor" : "none"}
                    aria-hidden="true"
                  />
                </button>
              </div>
              <h3 className="text-lg font-semibold tracking-tight">
                <Link href={`/agents/${agent.id}`} className="hover:underline">
                  {agent.name}
                </Link>
              </h3>
              <p className="mt-2 min-h-16 text-sm leading-relaxed text-[var(--muted-foreground)]">
                {agent.description || t("noDescription")}
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-[var(--muted-foreground)]">
                <span className="rounded-md border border-[var(--border)] px-2 py-0.5">
                  {agent.disabled
                    ? t("disabled")
                    : agent.status === "published"
                      ? t("published")
                      : agent.status === "archived"
                        ? t("archived")
                        : t("draftStatus")}
                </span>
                <span>
                  {t("version")} {agent.publishedVersion ?? "—"}
                </span>
              </div>
              <p className="mb-5 mt-3 truncate text-[11px] text-[var(--muted-foreground)]">
                {t("owner")} {agent.owner?.displayName ?? t("unknownOwner")}
              </p>
              <div className="mt-auto flex items-center justify-between gap-2 border-t border-[var(--border)] pt-4">
                <Link
                  href={`/agents/${agent.id}`}
                  className="flex items-center gap-1 text-xs font-medium hover:underline"
                >
                  {t("details")}
                  <ArrowRight size={13} aria-hidden="true" />
                </Link>
                {canChat && agent.status === "published" && !agent.disabled ? (
                  <Button
                    className="h-8 gap-1.5 text-xs"
                    disabled={pending === agent.id}
                    onClick={() => void act(agent, "chat")}
                    type="button"
                    variant="outline"
                  >
                    <MessageSquare size={13} aria-hidden="true" />
                    {t("chat")}
                  </Button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
