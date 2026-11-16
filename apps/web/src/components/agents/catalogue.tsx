"use client";

import { Bot, MessageSquare, Plus, Search, Star } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableScroll,
} from "@/components/ui/table";
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
      <PageHeader
        actions={
          canCreate ? (
            <Button asChild>
              <Link href="/agents/new" className="gap-2">
                <Plus size={16} aria-hidden="true" />
                {t("create")}
              </Link>
            </Button>
          ) : undefined
        }
        body={t("body")}
        title={t("title")}
      />
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
          className="space-y-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
        >
          {[0, 1, 2].map((id) => (
            <Skeleton className="h-12 w-full" key={id} />
          ))}
        </div>
      ) : null}
      {!loading && !error && agents.length === 0 ? (
        <div className="flex flex-col items-center rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)] px-6 py-16 text-center">
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
      {!loading && agents.length > 0 ? (
        <TableScroll
          className="rounded-xl border border-[var(--border)] bg-[var(--card)]"
          label={t("browse")}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">{t("agentColumn")}</TableHead>
                <TableHead scope="col">{t("status")}</TableHead>
                <TableHead scope="col">{t("owner")}</TableHead>
                <TableHead scope="col">{t("version")}</TableHead>
                <TableHead scope="col">
                  <span className="sr-only">{t("actions")}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {agents.map((agent) => {
                const state = agent.disabled ? "disabled" : (agent.status ?? "draft");
                return (
                  <TableRow className="hover:bg-[var(--muted)]" key={agent.id}>
                    <TableCell className="min-w-56">
                      <div className="flex items-start gap-3">
                        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md border border-[var(--border)] bg-[var(--background)]">
                          <Bot size={17} strokeWidth={1.5} aria-hidden="true" />
                        </span>
                        <div className="min-w-0">
                          <h3 className="font-semibold">
                            <Link href={`/agents/${agent.id}`} className="hover:underline">
                              {agent.name}
                            </Link>
                          </h3>
                          <p className="mt-0.5 line-clamp-2 text-[var(--muted-foreground)]">
                            {agent.description || t("noDescription")}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge tone={statusTone(state)}>
                        {state === "disabled"
                          ? t("disabled")
                          : state === "published"
                            ? t("published")
                            : state === "archived"
                              ? t("archived")
                              : t("draftStatus")}
                      </Badge>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-[var(--muted-foreground)]">
                      {agent.owner?.displayName ?? "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap tabular-nums text-[var(--muted-foreground)]">
                      {agent.publishedVersion ?? "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center justify-end gap-1">
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
                        <button
                          aria-label={`${agent.favourite ? t("unfavourite") : t("favourite")}: ${agent.name}`}
                          aria-pressed={Boolean(agent.favourite)}
                          className="rounded-md p-2 text-[var(--muted-foreground)] hover:bg-[var(--background)]"
                          disabled={pending === agent.id}
                          onClick={() => void act(agent, "favourite")}
                          type="button"
                        >
                          <Star
                            size={16}
                            fill={agent.favourite ? "currentColor" : "none"}
                            aria-hidden="true"
                          />
                        </button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableScroll>
      ) : null}
    </div>
  );
}
