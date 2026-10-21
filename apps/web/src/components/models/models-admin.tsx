"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Row = Record<string, unknown>;

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|; )ar_csrf=([^;]*)/);
  return match?.[1] ? decodeURIComponent(match[1]) : "";
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("content-type", "application/json");
  headers.set("x-csrf-token", csrfToken());
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(problem.detail ?? response.statusText);
  }
  return (await response.json()) as T;
}

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
    <main className="mx-auto max-w-5xl p-6">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>
      <p className="mt-1 text-sm text-[var(--muted)]">{t("body")}</p>
      {loading ? <p className="mt-4">{t("loading")}</p> : null}
      {error ? (
        <p className="mt-4" role="alert">
          {error}
        </p>
      ) : null}
      {!loading && providers.length === 0 ? <p className="mt-4">{t("empty")}</p> : null}
      <div className="mt-6 overflow-hidden rounded-md border border-[var(--border)]">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{t("providers")}</caption>
          <thead className="bg-[var(--background)]">
            <tr>
              <th className="p-3">{t("name")}</th>
              <th className="p-3">{t("url")}</th>
              <th className="p-3">{t("scope")}</th>
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
        className="mt-6 grid gap-3 rounded-md border border-[var(--border)] p-4"
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
        <label className="text-sm" htmlFor="provider-url">
          {t("url")}
        </label>
        <Input
          id="provider-url"
          onChange={(event) => setBaseUrl(event.target.value)}
          value={baseUrl}
        />
        <Button type="submit">{t("test")}</Button>
        {sample ? (
          <p>
            {t("sample")}: {sample}
          </p>
        ) : null}
      </form>
      <p className="mt-4 text-sm text-[var(--muted)]">
        {t("counts", { models: models.length, aliases: aliases.length })}
      </p>
      <a className="mt-4 inline-block text-sm underline" href="/chat">
        {t("back")}
      </a>
    </main>
  );
}
