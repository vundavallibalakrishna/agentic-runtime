"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Skill = {
  id: string;
  slug: string;
  name: string;
  description?: string;
  status?: string;
  publishedVersion?: number | null;
  usedByCount?: number;
};

const MODE_KEY = "ar-settings-mode";

function slugify(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 62);
  return slug.length < 2 ? "skill" : slug;
}

export function SkillsScreen() {
  const t = useTranslations("skills");
  const [rows, setRows] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [slug, setSlug] = useState("");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const suffix = query.trim() ? `?q=${encodeURIComponent(query.trim())}` : "";
    try {
      const page = await api<{ items: Skill[] }>(`/api/v1/skills${suffix}`);
      setRows(page.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [query, t]);

  useEffect(() => {
    void load();
  }, [load]);

  function choose(next: boolean) {
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }

  async function createSkill() {
    setBusy(true);
    setError("");
    try {
      const created = await api<Skill>("/api/v1/skills", {
        method: "POST",
        body: JSON.stringify({
          slug: slug || slugify(name),
          name,
          description,
          instructionsMd: instructions,
          visibility: "tenant",
        }),
      });
      setName("");
      setDescription("");
      setInstructions("");
      setSlug("");
      window.location.assign(`/skills/${created.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title={t("title")}
        body={t("body")}
        actions={<SettingsMode advanced={advanced} onChange={choose} />}
      />

      {error ? (
        <p className="mb-3 text-sm text-[var(--destructive)]" role="alert">
          {error}{" "}
          <Button onClick={() => void load()} type="button" variant="outline">
            {t("retry")}
          </Button>
        </p>
      ) : null}

      <ManagementLayout
        title={t("listTitle")}
        formTitle={t("create")}
        form={
          <section className="space-y-1">
            <label className="mt-3 block text-sm" htmlFor="skill-name">
              {t("name")}
            </label>
            <Input
              className="mt-1 max-w-md"
              id="skill-name"
              onChange={(event) => setName(event.target.value)}
              value={name}
            />
            <label className="mt-3 block text-sm" htmlFor="skill-description">
              {t("description")}
            </label>
            <Input
              className="mt-1 max-w-xl"
              id="skill-description"
              onChange={(event) => setDescription(event.target.value)}
              value={description}
            />
            <label className="mt-3 block text-sm" htmlFor="skill-instructions">
              {t("instructions")}
            </label>
            <textarea
              className="mt-1 min-h-28 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
              id="skill-instructions"
              onChange={(event) => setInstructions(event.target.value)}
              value={instructions}
            />
            {advanced ? (
              <div className="mt-3">
                <label className="block text-sm" htmlFor="skill-slug">
                  {t("slug")}
                </label>
                <Input
                  className="mt-1 max-w-xs"
                  id="skill-slug"
                  onChange={(event) => setSlug(event.target.value)}
                  value={slug}
                />
              </div>
            ) : null}
            <Button
              className="mt-3"
              disabled={busy || !name.trim() || !description.trim()}
              onClick={() => void createSkill()}
              type="button"
            >
              {t("create")}
            </Button>
          </section>
        }
      >
        <div className="mb-5">
          <label className="sr-only" htmlFor="skill-search">
            {t("search")}
          </label>
          <Input
            className="w-full"
            placeholder={t("search")}
            id="skill-search"
            onChange={(event) => setQuery(event.target.value)}
            value={query}
          />
        </div>
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : null}
        {!loading && !error && rows.length === 0 ? <EmptyState title={t("empty")} /> : null}
        <ul className="space-y-2">
          {rows.map((skill) => (
            <li
              className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
              key={skill.id}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium">{skill.name}</p>
                  <p className="text-sm text-[var(--muted-foreground)]">{skill.description}</p>
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                    {skill.status}
                    {skill.publishedVersion ? ` · v${skill.publishedVersion}` : ""}
                  </p>
                </div>
                <Button asChild variant="outline">
                  <Link href={`/skills/${skill.id}`}>{t("open")}</Link>
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </ManagementLayout>
    </AppShell>
  );
}
