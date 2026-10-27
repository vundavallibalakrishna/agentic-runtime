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

type Row = Record<string, unknown>;

const MODE_KEY = "ar-settings-mode";

export function ComputersScreen() {
  const t = useTranslations("computers");
  const [templates, setTemplates] = useState<Row[]>([]);
  const [live, setLive] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [name, setName] = useState("Project computer");
  const [slug, setSlug] = useState("project");
  const [cpu, setCpu] = useState("2000");
  const [memory, setMemory] = useState("4096");
  const [packages, setPackages] = useState(false);

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const templatePage = await api<{ items: Row[] }>("/api/v1/sandbox-templates");
      const sandboxPage = await api<{ items: Row[] }>("/api/v1/sandboxes");
      setTemplates(templatePage.items ?? []);
      setLive(sandboxPage.items ?? []);
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
    try {
      await api("/api/v1/sandbox-templates", {
        method: "POST",
        body: JSON.stringify({
          slug,
          name,
          cpuMillis: Number(cpu),
          memoryMb: Number(memory),
          allowPackages: packages,
        }),
      });
      setNotice(t("saved"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function terminate(id: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/sandboxes/${id}:terminate`, { method: "POST" });
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
          formTitle={t("createTitle")}
          form={
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                void save();
              }}
            >
              <label htmlFor="computer-name">
                {t("name")}
                <Input
                  id="computer-name"
                  onChange={(event) => setName(event.target.value)}
                  value={name}
                />
              </label>
              <label htmlFor="computer-slug">
                {t("slug")}
                <Input
                  id="computer-slug"
                  onChange={(event) => setSlug(event.target.value)}
                  value={slug}
                />
              </label>
              {advanced ? (
                <>
                  <label htmlFor="computer-cpu">
                    {t("cpu")}
                    <Input
                      id="computer-cpu"
                      onChange={(event) => setCpu(event.target.value)}
                      value={cpu}
                    />
                  </label>
                  <label htmlFor="computer-memory">
                    {t("memory")}
                    <Input
                      id="computer-memory"
                      onChange={(event) => setMemory(event.target.value)}
                      value={memory}
                    />
                  </label>
                  <label className="flex items-center gap-2 text-sm" htmlFor="computer-packages">
                    <input
                      checked={packages}
                      id="computer-packages"
                      onChange={(event) => setPackages(event.target.checked)}
                      type="checkbox"
                    />
                    {t("packages")}
                  </label>
                </>
              ) : null}
              <Button type="submit">{t("save")}</Button>
            </form>
          }
        >
          {loading ? (
            <div aria-busy="true">
              <span className="sr-only">{t("loading")}</span>
              <Skeleton className="h-24 w-full" />
            </div>
          ) : null}
          {!loading && !error && templates.length === 0 ? <EmptyState title={t("empty")} /> : null}
          <ul className="mb-8 space-y-3">
            {templates.map((row) => (
              <li
                className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
                key={String(row.id)}
              >
                <h2 className="font-medium">{String(row.name)}</h2>
                <p className="text-sm text-[var(--muted-foreground)]">
                  {String(row.slug)} · {String(row.cpuMillis)} {t("cpuUnit")} ·{" "}
                  {String(row.memoryMb)} {t("memoryUnit")}
                </p>
              </li>
            ))}
          </ul>
          <h2 className="mb-3 text-sm font-medium">{t("live")}</h2>
          {!loading && !error && live.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">{t("emptyLive")}</p>
          ) : null}
          <ul className="space-y-3">
            {live.map((row) => (
              <li
                className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
                key={String(row.id)}
              >
                <p className="font-medium">{String(row.templateSlug || row.scopeKey)}</p>
                <p className="text-sm text-[var(--muted-foreground)]">{String(row.status)}</p>
                {row.status !== "terminated" ? (
                  <Button
                    className="mt-3"
                    onClick={() => void terminate(String(row.id))}
                    type="button"
                    variant="outline"
                  >
                    {t("terminate")}
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        </ManagementLayout>
      </fieldset>
    </AppShell>
  );
}
