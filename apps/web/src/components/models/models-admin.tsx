"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Row = Record<string, unknown>;

const MODE_KEY = "ar-settings-mode";

export function ModelsAdmin() {
  const t = useTranslations("models");
  const [providers, setProviders] = useState<Row[]>([]);
  const [models, setModels] = useState<Row[]>([]);
  const [aliases, setAliases] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("Local fake");
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:8099/v1");
  const [sample, setSample] = useState("");
  const [advanced, setAdvanced] = useState(false);

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [providerPage, modelPage, aliasPage] = await Promise.all([
        api<{ items: Row[] }>("/api/v1/model-providers"),
        api<{ items: Row[] }>("/api/v1/models"),
        api<{ items: Row[] }>("/api/v1/model-aliases"),
      ]);
      setProviders(providerPage.items ?? []);
      setModels(modelPage.items ?? []);
      setAliases(aliasPage.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  function chooseMode(next: boolean) {
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }

  async function registerProvider() {
    setError("");
    try {
      const created = await api<Row>("/api/v1/model-providers", {
        method: "POST",
        body: JSON.stringify({ name, kind: "fake", baseUrl }),
      });
      const model = await api<Row>("/api/v1/models", {
        method: "POST",
        body: JSON.stringify({
          providerId: created.id,
          name: `${name} chat`,
          upstreamModel: "fake-chat",
          kind: "chat",
        }),
      });
      const reasoning = aliases.find((row) => row.alias === "reasoning" && row.platform !== true);
      if (!reasoning) {
        await api("/api/v1/model-aliases", {
          method: "POST",
          body: JSON.stringify({
            alias: "reasoning",
            kind: "chat",
            primaryModelId: model.id,
          }),
        });
      }
      const tested = await api<{ output: string; latencyMs: number }>(
        `/api/v1/model-providers/${String(created.id)}:test`,
        { method: "POST", body: "{}" },
      );
      setSample(`${tested.output} (${tested.latencyMs} ms)`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  return (
    <AppShell>
      <PageHeader body={t("body")} title={t("title")} />
      <fieldset className="mb-4 flex gap-2 border-0 p-0">
        <legend className="sr-only">{t("modeLabel")}</legend>
        <Button
          onClick={() => chooseMode(false)}
          type="button"
          variant={advanced ? "outline" : "default"}
        >
          {t("simple")}
        </Button>
        <Button
          onClick={() => chooseMode(true)}
          type="button"
          variant={advanced ? "default" : "outline"}
        >
          {t("advanced")}
        </Button>
      </fieldset>
      {loading ? (
        <div aria-busy="true" className="space-y-2">
          <p className="sr-only">{t("loading")}</p>
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : null}
      {error ? (
        <p className="mt-4" role="alert">
          {error}
        </p>
      ) : null}
      {!loading && providers.length === 0 ? <p className="mt-4">{t("empty")}</p> : null}
      <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{t("providers")}</caption>
          <thead className="text-[var(--muted-foreground)]">
            <tr>
              <th className="p-3 font-medium">{t("name")}</th>
              <th className="p-3 font-medium">{t("url")}</th>
              <th className="p-3 font-medium">{t("scope")}</th>
            </tr>
          </thead>
          <tbody>
            {providers.map((row) => (
              <tr className="border-t border-[var(--border)]" key={String(row.id)}>
                <td className="p-3">{String(row.name)}</td>
                <td className="p-3">{String(row.baseUrl)}</td>
                <td className="p-3">{row.platform ? t("platform") : t("tenant")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form
        className="mt-6 grid gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
        onSubmit={(event) => {
          event.preventDefault();
          void registerProvider();
        }}
      >
        <h2 className="font-medium">{t("register")}</h2>
        <label className="text-sm" htmlFor="provider-name">
          {t("name")}
        </label>
        <Input id="provider-name" onChange={(event) => setName(event.target.value)} value={name} />
        {advanced ? (
          <>
            <label className="text-sm" htmlFor="provider-url">
              {t("url")}
            </label>
            <Input
              id="provider-url"
              onChange={(event) => setBaseUrl(event.target.value)}
              value={baseUrl}
            />
          </>
        ) : null}
        <Button className="justify-self-start" type="submit">
          {t("test")}
        </Button>
        {sample ? (
          <p>
            {t("sample")}: {sample}
          </p>
        ) : null}
      </form>
      <p className="mt-4 text-sm text-[var(--muted-foreground)]">
        {t("counts", { models: models.length, aliases: aliases.length })}
      </p>
    </AppShell>
  );
}
