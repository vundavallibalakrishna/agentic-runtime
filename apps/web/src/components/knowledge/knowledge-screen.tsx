"use client";

import Link from "next/link";
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

type Row = Record<string, unknown>;

const MODE_KEY = "ar-settings-mode";

export function KnowledgeScreen() {
  const t = useTranslations("knowledge");
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api<{ items: Row[] }>("/api/v1/knowledge/collections");
      setRows(page.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  function choose(next: boolean) {
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }

  async function save() {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    const derived =
      slug ||
      name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");
    try {
      await api("/api/v1/knowledge/collections", {
        method: "POST",
        body: JSON.stringify({ name, slug: derived, description }),
      });
      setNotice(t("saved"));
      setName("");
      setSlug("");
      setDescription("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
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
          actions={<SettingsMode advanced={advanced} onChange={choose} />}
        />

        {error ? (
          <p role="alert">
            {error}{" "}
            <button className="underline" onClick={() => void load()} type="button">
              {t("retry")}
            </button>
          </p>
        ) : null}
        {notice ? <p role="status">{notice}</p> : null}

        <ManagementLayout
          title={t("listTitle")}
          formTitle={t("save")}
          form={
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                void save();
              }}
            >
              <label htmlFor="knowledge-name">
                {t("name")}
                <Input
                  id="knowledge-name"
                  onChange={(event) => setName(event.target.value)}
                  value={name}
                />
              </label>
              {advanced ? (
                <>
                  <label htmlFor="knowledge-slug">
                    {t("slug")}
                    <Input
                      id="knowledge-slug"
                      onChange={(event) => setSlug(event.target.value)}
                      value={slug}
                    />
                  </label>
                  <label htmlFor="knowledge-description">
                    {t("description")}
                    <Input
                      id="knowledge-description"
                      onChange={(event) => setDescription(event.target.value)}
                      value={description}
                    />
                  </label>
                </>
              ) : null}
              <Button type="submit">{t("save")}</Button>
            </form>
          }
        >
          {loading ? <Skeleton className="h-24 w-full max-w-xl" /> : null}
          {!loading && !error && rows.length === 0 ? <EmptyState title={t("empty")} /> : null}
          <ul className="grid gap-3">
            {rows.map((row) => {
              const id = String(row.id);
              const stats = (row.stats as Row) ?? {};
              return (
                <li key={id}>
                  <Link
                    className="block rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 hover:bg-[var(--muted)]"
                    href={`/knowledge/${id}`}
                  >
                    <h2 className="text-base font-semibold">{String(row.name)}</h2>
                    <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                      {String(row.description || "")}
                    </p>
                    <p className="mt-3 text-xs text-[var(--muted-foreground)]">
                      {String(stats.documents ?? 0)} {t("documents")}
                    </p>
                  </Link>
                </li>
              );
            })}
          </ul>
        </ManagementLayout>
      </fieldset>
    </AppShell>
  );
}
