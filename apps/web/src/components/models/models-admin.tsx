"use client";

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
  const [kind, setKind] = useState("fake");
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:8099/v1");
  const [apiKey, setApiKey] = useState("");
  const [upstream, setUpstream] = useState("fake-chat");
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

  function chooseKind(next: string) {
    setKind(next);
    if (next === "openai_compatible" && baseUrl.includes("127.0.0.1")) {
      setBaseUrl("https://api.deepinfra.com/v1/openai");
    }
    if (next === "openai_compatible" && upstream === "fake-chat") {
      setUpstream("Qwen/Qwen3-32B");
    }
    if (next === "fake") {
      setBaseUrl("http://127.0.0.1:8099/v1");
      setUpstream("fake-chat");
      setApiKey("");
    }
  }

  async function registerProvider() {
    setError("");
    const secret = apiKey;
    setApiKey("");
    try {
      const created = await api<Row>("/api/v1/model-providers", {
        method: "POST",
        body: JSON.stringify({
          name,
          kind,
          baseUrl,
          ...(secret ? { apiKey: secret } : {}),
        }),
      });
      const model = await api<Row>("/api/v1/models", {
        method: "POST",
        body: JSON.stringify({
          providerId: created.id,
          name: `${name} chat`,
          upstreamModel: upstream,
          kind: "chat",
        }),
      });
      const reasoning = aliases.find((row) => row.alias === "reasoning" && row.platform !== true);
      if (reasoning && kind !== "fake") {
        await api(`/api/v1/model-aliases/${String(reasoning.id)}`, {
          method: "PATCH",
          body: JSON.stringify({ primaryModelId: model.id }),
        });
      } else if (!reasoning) {
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
      <PageHeader
        title={t("title")}
        body={t("body")}
        actions={<SettingsMode advanced={advanced} onChange={chooseMode} />}
      />

      <ManagementLayout
        title={t("providers")}
        formTitle={t("register")}
        form={
          <form
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              void registerProvider();
            }}
          >
            <label className="text-sm" htmlFor="provider-name">
              {t("name")}
              <Input
                id="provider-name"
                onChange={(event) => setName(event.target.value)}
                value={name}
              />
            </label>
            {advanced ? (
              <>
                <fieldset className="grid gap-2">
                  <legend className="text-sm">{t("kind")}</legend>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      aria-pressed={kind === "fake"}
                      onClick={() => chooseKind("fake")}
                      type="button"
                      variant={kind === "fake" ? "default" : "outline"}
                    >
                      {t("fakeKind")}
                    </Button>
                    <Button
                      aria-pressed={kind === "openai_compatible"}
                      onClick={() => chooseKind("openai_compatible")}
                      type="button"
                      variant={kind === "openai_compatible" ? "default" : "outline"}
                    >
                      {t("openaiKind")}
                    </Button>
                  </div>
                </fieldset>
                <label className="text-sm" htmlFor="provider-url">
                  {t("url")}
                  <Input
                    id="provider-url"
                    onChange={(event) => setBaseUrl(event.target.value)}
                    value={baseUrl}
                  />
                </label>
                <label className="text-sm" htmlFor="provider-model">
                  {t("upstream")}
                  <Input
                    id="provider-model"
                    onChange={(event) => setUpstream(event.target.value)}
                    value={upstream}
                  />
                </label>
                {kind === "openai_compatible" ? (
                  <div className="grid gap-1">
                    <label className="text-sm" htmlFor="provider-key">
                      {t("apiKey")}
                      <Input
                        aria-describedby="provider-key-hint"
                        autoComplete="off"
                        id="provider-key"
                        onChange={(event) => setApiKey(event.target.value)}
                        type="password"
                        value={apiKey}
                      />
                    </label>
                    <p className="text-sm text-[var(--muted-foreground)]" id="provider-key-hint">
                      {t("apiKeyHint")}
                    </p>
                  </div>
                ) : null}
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
        }
      >
        {loading ? (
          <div aria-busy="true" className="space-y-2">
            <p className="sr-only">{t("loading")}</p>
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : null}
        {error ? (
          <p className="mt-4" role="alert">
            {error}{" "}
            <Button variant="outline" onClick={() => void load()}>
              {t("retry")}
            </Button>
          </p>
        ) : null}
        {!loading && !error && providers.length === 0 ? <EmptyState title={t("empty")} /> : null}
        {!loading && !error && providers.length > 0 ? (
          <>
            <ul className="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--card)] md:hidden">
              {providers.map((row) => (
                <li className="px-4 py-3 text-sm" key={String(row.id)}>
                  <p className="font-medium">{String(row.name)}</p>
                  <p className="mt-1 break-all text-[var(--muted-foreground)]">
                    {String(row.baseUrl)}
                  </p>
                  <p className="mt-1 text-[var(--muted-foreground)]">
                    {String(row.kind ?? "")} · {row.platform ? t("platform") : t("tenant")} ·{" "}
                    {row.hasApiKey ? t("keyStored") : t("noKey")}
                  </p>
                </li>
              ))}
            </ul>
            <div className="hidden overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)] md:block">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">{t("providers")}</caption>
                <thead className="text-[var(--muted-foreground)]">
                  <tr>
                    <th className="p-3 font-medium">{t("name")}</th>
                    <th className="p-3 font-medium">{t("kind")}</th>
                    <th className="p-3 font-medium">{t("url")}</th>
                    <th className="p-3 font-medium">{t("scope")}</th>
                    <th className="p-3 font-medium">{t("apiKey")}</th>
                  </tr>
                </thead>
                <tbody>
                  {providers.map((row) => (
                    <tr className="border-t border-[var(--border)]" key={String(row.id)}>
                      <td className="p-3">{String(row.name)}</td>
                      <td className="p-3">{String(row.kind ?? "")}</td>
                      <td className="max-w-xs truncate p-3">{String(row.baseUrl)}</td>
                      <td className="p-3">{row.platform ? t("platform") : t("tenant")}</td>
                      <td className="p-3">{row.hasApiKey ? t("keyStored") : t("noKey")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}

        {!loading && !error ? (
          <p className="mt-4 text-sm text-[var(--muted-foreground)]">
            {t("counts", { models: models.length, aliases: aliases.length })}
          </p>
        ) : null}
      </ManagementLayout>
    </AppShell>
  );
}
