"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Fact = {
  id: string;
  content: string;
  scope: string;
  category: string;
  status: string;
};

type Team = {
  id: string;
  name: string;
  items: Fact[];
};

const MODE_KEY = "ar-settings-mode";

export function MemoryScreen() {
  const t = useTranslations("memory");
  const [rows, setRows] = useState<Fact[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [content, setContent] = useState("");
  const [editing, setEditing] = useState("");
  const [draft, setDraft] = useState("");
  const [confirmForget, setConfirmForget] = useState(false);
  const [scope, setScope] = useState("");
  const [category, setCategory] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (scope) {
      params.set("scope", scope);
    }
    if (category) {
      params.set("category", category);
    }
    if (query.trim()) {
      params.set("q", query.trim());
    }
    const suffix = params.size ? `?${params.toString()}` : "";
    try {
      const page = await api<{ items: Fact[]; memoryEnabled: boolean; teams: Team[] }>(
        `/api/v1/memory${suffix}`,
      );
      setRows(page.items ?? []);
      setTeams(page.teams ?? []);
      setEnabled(page.memoryEnabled !== false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [category, query, scope, t]);

  useEffect(() => {
    void load();
  }, [load]);

  function choose(next: boolean) {
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }

  async function toggle(next: boolean) {
    setEnabled(next);
    setError("");
    try {
      await api("/api/v1/memory/settings", {
        method: "PATCH",
        body: JSON.stringify({ enabled: next }),
      });
    } catch (caught) {
      setEnabled(!next);
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  async function save() {
    setError("");
    setNotice("");
    try {
      await api("/api/v1/memory", {
        method: "POST",
        body: JSON.stringify({ content, scope: "user" }),
      });
      setContent("");
      setNotice(t("saved"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  async function saveEdit(id: string) {
    setError("");
    await api(`/api/v1/memory/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ content: draft }),
    });
    setEditing("");
    setNotice(t("saved"));
    await load();
  }

  async function remove(id: string) {
    setError("");
    await api(`/api/v1/memory/${id}`, { method: "DELETE" });
    setNotice(t("deleted"));
    await load();
  }

  async function forgetAll() {
    setError("");
    try {
      await api("/api/v1/memory", {
        method: "DELETE",
        headers: { "X-Confirm": "delete-all-memory" },
      });
      setConfirmForget(false);
      setNotice(t("forgotten"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  return (
    <AppShell>
      <PageHeader body={t("body")} title={t("title")} />
      <div className="mb-4 flex gap-2">
        <Button
          onClick={() => choose(false)}
          type="button"
          variant={advanced ? "outline" : "default"}
        >
          {t("simple")}
        </Button>
        <Button
          onClick={() => choose(true)}
          type="button"
          variant={advanced ? "default" : "outline"}
        >
          {t("advanced")}
        </Button>
      </div>
      <label className="mb-4 flex items-center gap-2 text-sm">
        <input
          checked={enabled}
          onChange={(event) => void toggle(event.target.checked)}
          type="checkbox"
        />
        {t("enabled")}
      </label>
      {error ? (
        <p role="alert">
          {error}{" "}
          <button className="underline" onClick={() => void load()} type="button">
            {t("retry")}
          </button>
        </p>
      ) : null}
      {notice ? <p role="status">{notice}</p> : null}
      <form
        className="mb-6 grid max-w-xl gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label htmlFor="memory-content">
          {t("content")}
          <Input
            id="memory-content"
            onChange={(event) => setContent(event.target.value)}
            value={content}
          />
        </label>
        <Button type="submit">{t("save")}</Button>
      </form>
      {advanced ? (
        <div className="mb-6 flex flex-wrap gap-2">
          <label className="text-sm" htmlFor="memory-scope">
            {t("scope")}
            <select
              className="ml-2 h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
              id="memory-scope"
              onChange={(event) => setScope(event.target.value)}
              value={scope}
            >
              <option value="">All</option>
              <option value="user">user</option>
              <option value="agent_user">agent_user</option>
            </select>
          </label>
          <label className="text-sm" htmlFor="memory-category">
            {t("category")}
            <select
              className="ml-2 h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
              id="memory-category"
              onChange={(event) => setCategory(event.target.value)}
              value={category}
            >
              <option value="">All</option>
              <option value="preference">preference</option>
              <option value="fact">fact</option>
              <option value="instruction">instruction</option>
              <option value="lesson">lesson</option>
            </select>
          </label>
          <Input
            aria-label={t("search")}
            className="max-w-xs"
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("search")}
            value={query}
          />
        </div>
      ) : null}
      {loading ? <Skeleton className="h-24 w-full max-w-xl" /> : null}
      {!loading && !error && rows.length === 0 ? <p>{t("empty")}</p> : null}
      <h2 className="mb-2 font-serif text-xl">{t("yours")}</h2>
      <ul className="grid max-w-3xl gap-3">
        {rows.map((row) => (
          <li
            className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
            key={row.id}
          >
            {editing === row.id ? (
              <form
                className="grid gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  void saveEdit(row.id);
                }}
              >
                <Input
                  aria-label={t("content")}
                  onChange={(event) => setDraft(event.target.value)}
                  value={draft}
                />
                <Button type="submit">{t("save")}</Button>
              </form>
            ) : (
              <>
                <p>{row.content}</p>
                <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                  {row.category}
                  {row.status === "pending_review" ? ` · ${t("pending")}` : ""}
                </p>
                <div className="mt-3 flex gap-2">
                  <Button
                    onClick={() => {
                      setEditing(row.id);
                      setDraft(row.content);
                    }}
                    type="button"
                    variant="outline"
                  >
                    {t("edit")}
                  </Button>
                  <Button onClick={() => void remove(row.id)} type="button" variant="outline">
                    {t("delete")}
                  </Button>
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-6">
        {confirmForget ? (
          <div className="flex gap-2">
            <Button
              className="text-[var(--destructive)]"
              onClick={() => void forgetAll()}
              type="button"
              variant="outline"
            >
              {t("confirmForget")}
            </Button>
            <Button onClick={() => setConfirmForget(false)} type="button" variant="outline">
              {t("cancel")}
            </Button>
          </div>
        ) : (
          <Button onClick={() => setConfirmForget(true)} type="button" variant="outline">
            {t("forget")}
          </Button>
        )}
      </div>
      {teams.map((team) => (
        <section className="mt-8" key={team.id}>
          <h2 className="font-serif text-xl">
            {t("team")}: {team.name}
          </h2>
          {team.items.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--muted-foreground)]">{t("teamEmpty")}</p>
          ) : (
            <ul className="mt-3 grid max-w-3xl gap-3">
              {team.items.map((row) => (
                <li
                  className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
                  key={row.id}
                >
                  <p>{row.content}</p>
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">{row.category}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </AppShell>
  );
}
