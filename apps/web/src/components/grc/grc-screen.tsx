"use client";

import { notFound } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/common/management-layout";
import { GrcNav } from "@/components/grc/grc-nav";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api } from "@/lib/api";

type Framework = {
  id: string;
  key?: string;
  name?: string;
  version?: string;
  licence?: string;
  requirementCount?: number;
  controlCount?: number;
};
type Control = {
  id: string;
  key?: string;
  title?: string;
  statement?: string;
  frameworkId?: string | null;
  mappings?: { id: string; status?: string; confidence?: number; rationale?: string }[];
  evidenceLinkCount?: number;
};
type EvidenceLink = { id: string; controlId?: string; stale?: boolean; freshnessDays?: number };
type Evidence = { id: string; sourceSystem?: string };
type PackRow = { packId?: string; enabled?: boolean };

export function GrcScreen({ section }: { section: "frameworks" | "controls" | "evidence" }) {
  const t = useTranslations("grc");
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [frameworks, setFrameworks] = useState<Framework[]>([]);
  const [controls, setControls] = useState<Control[]>([]);
  const [links, setLinks] = useState<EvidenceLink[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [selected, setSelected] = useState<Control | null>(null);
  const [query, setQuery] = useState("");
  const [controlId, setControlId] = useState("");
  const [evidenceId, setEvidenceId] = useState("");
  const [days, setDays] = useState("90");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const packs = await api<{ items?: PackRow[] }>("/api/v1/tenant/packs");
      const enabled = (packs.items ?? []).some((row) => row.packId === "grc" && row.enabled);
      if (!enabled) {
        setMissing(true);
        return;
      }
      setMissing(false);
      const [frameworkPage, controlPage, linkPage, evidencePage] = await Promise.all([
        api<{ items: Framework[] }>("/api/v1/ext/grc/frameworks"),
        api<{ items: Control[] }>(
          `/api/v1/ext/grc/controls${query ? `?q=${encodeURIComponent(query)}` : ""}`,
        ),
        api<{ items: EvidenceLink[] }>("/api/v1/ext/grc/evidence-links"),
        api<{ items: Evidence[] }>("/api/v1/evidence").catch(() => ({ items: [] as Evidence[] })),
      ]);
      setFrameworks(frameworkPage.items ?? []);
      setControls(controlPage.items ?? []);
      setLinks(linkPage.items ?? []);
      setEvidence(evidencePage.items ?? []);
      setControlId((current) => current || controlPage.items?.[0]?.id || "");
      setEvidenceId((current) => current || evidencePage.items?.[0]?.id || "");
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 404) {
        setMissing(true);
        return;
      }
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [query, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function importOscal(file: File) {
    setNotice("");
    setError("");
    const body = new FormData();
    body.set("upload", file);
    body.set("mime_type", "text/plain");
    try {
      const uploaded = await api<{ id: string }>("/api/v1/files:upload", { method: "POST", body });
      await api("/api/v1/ext/grc/frameworks:import-oscal", {
        method: "POST",
        body: JSON.stringify({ fileId: uploaded.id }),
      });
      setNotice(t("imported"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  async function linkEvidence() {
    setNotice("");
    setError("");
    try {
      await api("/api/v1/ext/grc/evidence-links", {
        method: "POST",
        body: JSON.stringify({
          controlId,
          evidenceItemId: evidenceId,
          freshnessDays: Number(days) || 90,
        }),
      });
      setNotice(t("linked"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  async function openControl(id: string) {
    setError("");
    try {
      setSelected(await api<Control>(`/api/v1/ext/grc/controls/${id}`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  if (!loading && missing) {
    notFound();
    return null;
  }

  return (
    <AppShell>
      <PageHeader
        title={t("title")}
        body={t("body")}
        actions={
          section === "frameworks" ? (
            <label className="inline-flex">
              <span className="sr-only">{t("import")}</span>
              <input
                aria-label={t("import")}
                className="sr-only"
                type="file"
                accept="application/json,text/plain,.json"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void importOscal(file);
                }}
              />
              <span className="inline-flex h-10 cursor-pointer items-center rounded-lg bg-[var(--primary)] px-4 text-sm font-medium text-[var(--primary-foreground)]">
                {t("import")}
              </span>
            </label>
          ) : null
        }
      />
      <GrcNav section={section} />
      {notice ? (
        <p className="mb-4 text-sm" role="status">
          {notice}
        </p>
      ) : null}
      {loading ? (
        <div aria-busy="true" className="space-y-3" role="status">
          <span className="sr-only">{t("loading")}</span>
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : error ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : section === "frameworks" ? (
        frameworks.length === 0 ? (
          <EmptyState title={t("emptyFrameworks")} />
        ) : (
          <ul className="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--card)]">
            {frameworks.map((item) => (
              <li className="flex items-start justify-between gap-4 px-4 py-3" key={item.id}>
                <div>
                  <p className="font-medium">{item.name}</p>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    {item.key} · {item.version}
                  </p>
                  {item.licence === "skeleton" ? (
                    <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("skeleton")}</p>
                  ) : null}
                </div>
                <span className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">
                  {item.licence}
                </span>
              </li>
            ))}
          </ul>
        )
      ) : section === "controls" ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div>
            <label className="mb-3 block text-sm" htmlFor="grc-search">
              {t("search")}
            </label>
            <Input
              id="grc-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            {controls.length === 0 ? (
              <div className="mt-4">
                <EmptyState title={t("emptyControls")} />
              </div>
            ) : (
              <ul className="mt-4 divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--card)]">
                {controls.map((item) => (
                  <li key={item.id}>
                    <button
                      className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--muted)]"
                      onClick={() => void openControl(item.id)}
                      type="button"
                    >
                      <span>
                        <span className="block font-medium">{item.title}</span>
                        <span className="text-sm text-[var(--muted-foreground)]">{item.key}</span>
                      </span>
                      <span className="text-xs text-[var(--muted-foreground)]">{t("open")}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {selected ? (
            <aside className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
              <h2 className="text-base font-semibold">{selected.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-[var(--muted-foreground)]">
                {selected.statement || t("skeleton")}
              </p>
              <h3 className="mt-4 text-sm font-semibold">{t("mappings")}</h3>
              <ul className="mt-2 space-y-2 text-sm">
                {(selected.mappings ?? []).map((mapping) => (
                  <li key={mapping.id}>
                    {mapping.status} · {mapping.confidence}
                  </li>
                ))}
              </ul>
              <button
                className="mt-4 text-sm underline"
                onClick={() => setSelected(null)}
                type="button"
              >
                {t("close")}
              </button>
            </aside>
          ) : null}
        </div>
      ) : links.length === 0 && evidence.length === 0 ? (
        <EmptyState title={t("emptyEvidence")} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
          {links.length === 0 ? (
            <EmptyState title={t("emptyEvidence")} />
          ) : (
            <ul className="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--card)]">
              {links.map((item) => (
                <li className="px-4 py-3 text-sm" key={item.id}>
                  {item.controlId} · {item.stale ? t("stale") : t("fresh")}
                </li>
              ))}
            </ul>
          )}
          <form
            className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
            onSubmit={(event) => {
              event.preventDefault();
              void linkEvidence();
            }}
          >
            <h2 className="text-base font-semibold">{t("link")}</h2>
            <label className="block text-sm" htmlFor="grc-control">
              {t("control")}
            </label>
            <select
              className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
              id="grc-control"
              onChange={(event) => setControlId(event.target.value)}
              value={controlId}
            >
              {controls.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.key}
                </option>
              ))}
            </select>
            <label className="block text-sm" htmlFor="grc-evidence">
              {t("evidenceItem")}
            </label>
            <select
              className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
              id="grc-evidence"
              onChange={(event) => setEvidenceId(event.target.value)}
              value={evidenceId}
            >
              {evidence.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.sourceSystem ?? item.id}
                </option>
              ))}
            </select>
            <label className="block text-sm" htmlFor="grc-days">
              {t("freshness")}
            </label>
            <Input id="grc-days" value={days} onChange={(event) => setDays(event.target.value)} />
            <Button type="submit">{t("link")}</Button>
          </form>
        </div>
      )}
    </AppShell>
  );
}
