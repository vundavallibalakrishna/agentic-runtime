"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ManagementLayout } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Session } from "@/lib/api";

import {
  type AliasChange,
  AliasDialog,
  ConfirmDialog,
  type ModelChange,
  ModelDialog,
  type ProviderChange,
  ProviderDialog,
} from "./dialogs";
import { Field, Problem, Select } from "./parts";
import { AliasesSection, ProvidersSection, UsesSection } from "./sections";
import type { Alias, Model, Provider, StandardAlias, TestResult, Tests } from "./types";

const MODE_KEY = "ar-settings-mode";
const PROVIDER_KINDS = ["openai_compatible", "vllm", "tei"];

type Page<T> = { items?: T[] };
type Removal = { title: string; body: string; run: () => Promise<void> };

function post<T>(path: string, body: unknown = {}): Promise<T> {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}

function patch<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
}

function remove(path: string): Promise<unknown> {
  return api(path, { method: "DELETE" });
}

export function ModelsAdmin() {
  const t = useTranslations("models");
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [aliases, setAliases] = useState<Alias[]>([]);
  const [standard, setStandard] = useState<StandardAlias[]>([]);
  const [canManage, setCanManage] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [tests, setTests] = useState<Tests>({});
  const [advanced, setAdvanced] = useState(false);

  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [kind, setKind] = useState(PROVIDER_KINDS[0] ?? "");
  const [adding, setAdding] = useState(false);

  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);
  const [modelTarget, setModelTarget] = useState<{
    provider: Provider;
    model: Model | null;
  } | null>(null);
  const [aliasTarget, setAliasTarget] = useState<{ alias: Alias | null } | null>(null);
  const [removal, setRemoval] = useState<Removal | null>(null);

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const refresh = useCallback(async () => {
    const [providerPage, modelPage, aliasPage] = await Promise.all([
      api<Page<Provider>>("/api/v1/model-providers"),
      api<Page<Model>>("/api/v1/models"),
      api<Page<Alias> & { standard?: StandardAlias[] }>("/api/v1/model-aliases"),
    ]);
    setProviders(providerPage.items ?? []);
    setModels(modelPage.items ?? []);
    setAliases(aliasPage.items ?? []);
    setStandard(aliasPage.standard ?? []);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const session = await api<Session>("/api/v1/auth/session");
      setCanManage((session.permissions ?? []).includes("models:manage"));
      await refresh();
    } catch (caught) {
      setLoadError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [refresh, t]);

  useEffect(() => {
    void load();
  }, [load]);

  function chooseMode(next: boolean) {
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }

  /** Run a change made straight from the page, show why it failed, and reload. */
  async function act(change: () => Promise<unknown>) {
    setError("");
    try {
      await change();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
    await refresh().catch(() => undefined);
  }

  /** Run a change made in a dialog. A failure stays in the dialog. */
  async function save(change: () => Promise<unknown>) {
    try {
      await change();
    } finally {
      await refresh().catch(() => undefined);
    }
  }

  async function runTest(key: string, path: string) {
    setTests((current) => ({ ...current, [key]: "running" }));
    try {
      const result = await post<TestResult>(path);
      setTests((current) => ({ ...current, [key]: result }));
    } catch (caught) {
      const output = caught instanceof Error ? caught.message : t("error");
      setTests((current) => ({ ...current, [key]: { ok: false, output, latencyMs: 0 } }));
    }
  }

  async function addProvider(event: FormEvent) {
    event.preventDefault();
    const secret = apiKey;
    setAdding(true);
    setError("");
    try {
      const created = await post<Provider>("/api/v1/model-providers", {
        name: name.trim(),
        kind,
        baseUrl: baseUrl.trim(),
        ...(secret ? { apiKey: secret } : {}),
      });
      setName("");
      setBaseUrl("");
      setApiKey("");
      await refresh();
      // The next step is a model, so the person is taken straight to it.
      setModelTarget({ provider: created, model: null });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setAdding(false);
    }
  }

  async function saveProvider(provider: Provider, change: ProviderChange) {
    await patch(`/api/v1/model-providers/${provider.id}`, {
      name: change.name.trim(),
      baseUrl: change.baseUrl.trim(),
      ...(change.apiKey ? { apiKey: change.apiKey } : {}),
    });
  }

  async function saveModel(
    target: { provider: Provider; model: Model | null },
    change: ModelChange,
  ) {
    // What the model can do is kept, except for reading images, which the person sets here.
    const kept = (target.model?.capabilities ?? []).filter((item) => item !== "vision");
    const body = {
      name: change.name,
      upstreamModel: change.upstreamModel,
      priceInputMicrosPerMtok: change.priceIn,
      priceOutputMicrosPerMtok: change.priceOut,
      embeddingDimensions: change.embeddingDimensions,
      ...(change.kind === "rerank" || target.model?.kind === "rerank"
        ? { requestOptions: { ...(target.model?.requestOptions ?? {}), rerank: change.rerank } }
        : {}),
      ...(target.model || change.vision
        ? { capabilities: change.vision ? [...kept, "vision"] : kept }
        : {}),
    };
    if (target.model) {
      await patch(`/api/v1/models/${target.model.id}`, body);
      return;
    }
    const created = await post<Model>("/api/v1/models", {
      ...body,
      providerId: target.provider.id,
      kind: change.kind,
    });
    for (const alias of change.useFor) {
      const item = standard.find((entry) => entry.alias === alias);
      if (item) {
        await point(item, created.id);
      }
    }
  }

  /** Point a name the product uses at a model: change the tenant's alias, or make it. */
  async function point(item: StandardAlias, modelId: string) {
    if (item.aliasId && !item.platform) {
      await patch(`/api/v1/model-aliases/${item.aliasId}`, { primaryModelId: modelId });
      return;
    }
    await post("/api/v1/model-aliases", {
      alias: item.alias,
      kind: item.kind,
      primaryModelId: modelId,
    });
  }

  async function saveAlias(target: { alias: Alias | null }, change: AliasChange) {
    const params =
      change.temperature === null
        ? undefined
        : { ...(target.alias?.defaultParams ?? {}), temperature: change.temperature };
    if (target.alias) {
      await patch(`/api/v1/model-aliases/${target.alias.id}`, {
        primaryModelId: change.modelId,
        ...(params ? { defaultParams: params } : {}),
      });
      return;
    }
    await post("/api/v1/model-aliases", {
      alias: change.alias,
      kind: change.kind,
      primaryModelId: change.modelId,
      ...(params ? { defaultParams: params } : {}),
    });
  }

  const standardNames = new Set(standard.map((item) => item.alias));
  const otherAliases = aliases.filter((alias) => !standardNames.has(alias.alias));
  const byId = (id: string) => aliases.find((alias) => alias.id === id) ?? null;

  return (
    <AppShell>
      <PageHeader
        actions={<SettingsMode advanced={advanced} onChange={chooseMode} />}
        body={t("body")}
        title={t("title")}
      />

      {loading ? (
        <div aria-busy="true" className="space-y-3">
          <p className="sr-only">{t("loading")}</p>
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : null}

      {!loading && loadError ? (
        <Problem
          action={
            <Button onClick={() => void load()} type="button" variant="outline">
              {t("retry")}
            </Button>
          }
        >
          {loadError}
        </Problem>
      ) : null}

      {!loading && !loadError ? (
        <ManagementLayout
          form={
            canManage ? (
              <form className="grid gap-4" onSubmit={(event) => void addProvider(event)}>
                <Field id="provider-name" label={t("name")}>
                  <Input
                    id="provider-name"
                    onChange={(event) => setName(event.target.value)}
                    required
                    value={name}
                  />
                </Field>
                <Field hint={t("urlHint")} id="provider-url" label={t("url")}>
                  <Input
                    aria-describedby="provider-url-hint"
                    id="provider-url"
                    inputMode="url"
                    onChange={(event) => setBaseUrl(event.target.value)}
                    required
                    value={baseUrl}
                  />
                </Field>
                <Field hint={t("apiKeyHint")} id="provider-key" label={t("apiKey")}>
                  <Input
                    aria-describedby="provider-key-hint"
                    autoComplete="off"
                    id="provider-key"
                    onChange={(event) => setApiKey(event.target.value)}
                    type="password"
                    value={apiKey}
                  />
                </Field>
                {advanced ? (
                  <Field hint={t("providerKindHint")} id="provider-kind" label={t("kind")}>
                    <Select id="provider-kind" onChange={setKind} value={kind}>
                      {PROVIDER_KINDS.map((item) => (
                        <option key={item} value={item}>
                          {t(`providerKinds.${item}`)}
                        </option>
                      ))}
                    </Select>
                  </Field>
                ) : null}
                <Button className="justify-self-start" disabled={adding} type="submit">
                  {t("addProvider")}
                </Button>
              </form>
            ) : (
              <p className="text-sm leading-relaxed text-[var(--muted-foreground)]">
                {t("readOnly")}
              </p>
            )
          }
          formTitle={t("addProviderTitle")}
        >
          {error ? (
            <div className="mb-6">
              <Problem
                action={
                  <Button onClick={() => setError("")} type="button" variant="outline">
                    {t("dismiss")}
                  </Button>
                }
              >
                {error}
              </Problem>
            </div>
          ) : null}
          <UsesSection
            advanced={advanced}
            canManage={canManage}
            models={models}
            onClear={(item) =>
              setRemoval({
                title: t("clearTitle", { name: t(`uses.${item.alias}.title`) }),
                body: t("clearBody"),
                run: () => remove(`/api/v1/model-aliases/${item.aliasId}`).then(() => undefined),
              })
            }
            onOptions={(aliasId) => setAliasTarget({ alias: byId(aliasId) })}
            onPoint={(item, modelId) => void act(() => point(item, modelId))}
            onTest={(aliasId) =>
              void runTest(`alias:${aliasId}`, `/api/v1/model-aliases/${aliasId}:test`)
            }
            standard={standard}
            tests={tests}
          />
          <ProvidersSection
            advanced={advanced}
            canManage={canManage}
            models={models}
            onAddModel={(provider) => setModelTarget({ provider, model: null })}
            onEditModel={(provider, model) => setModelTarget({ provider, model })}
            onEditProvider={setEditingProvider}
            onRemoveModel={(model) =>
              setRemoval({
                title: t("removeTitle", { name: model.name }),
                body: t("removeModelBody"),
                run: () => remove(`/api/v1/models/${model.id}`).then(() => undefined),
              })
            }
            onRemoveProvider={(provider) =>
              setRemoval({
                title: t("removeTitle", { name: provider.name }),
                body: t("removeProviderBody"),
                run: () => remove(`/api/v1/model-providers/${provider.id}`).then(() => undefined),
              })
            }
            onTestModel={(model) =>
              void runTest(`model:${model.id}`, `/api/v1/models/${model.id}:test`)
            }
            onTestProvider={(provider) =>
              void runTest(`provider:${provider.id}`, `/api/v1/model-providers/${provider.id}:test`)
            }
            providers={providers}
            tests={tests}
          />
          {advanced ? (
            <AliasesSection
              aliases={otherAliases}
              canManage={canManage}
              models={models}
              onAdd={() => setAliasTarget({ alias: null })}
              onEdit={(alias) => setAliasTarget({ alias })}
              onRemove={(alias) =>
                setRemoval({
                  title: t("removeTitle", { name: alias.alias }),
                  body: t("removeAliasBody"),
                  run: () => remove(`/api/v1/model-aliases/${alias.id}`).then(() => undefined),
                })
              }
              onTest={(alias) =>
                void runTest(`alias:${alias.id}`, `/api/v1/model-aliases/${alias.id}:test`)
              }
              tests={tests}
            />
          ) : null}
        </ManagementLayout>
      ) : null}

      <ProviderDialog
        onClose={() => setEditingProvider(null)}
        onSave={(change) =>
          save(() => (editingProvider ? saveProvider(editingProvider, change) : Promise.resolve()))
        }
        provider={editingProvider}
      />
      <ModelDialog
        advanced={advanced}
        onClose={() => setModelTarget(null)}
        onSave={(change) =>
          save(() => (modelTarget ? saveModel(modelTarget, change) : Promise.resolve()))
        }
        standard={standard}
        target={modelTarget}
      />
      <AliasDialog
        models={models}
        onClose={() => setAliasTarget(null)}
        onSave={(change) =>
          save(() => (aliasTarget ? saveAlias(aliasTarget, change) : Promise.resolve()))
        }
        target={aliasTarget}
      />
      <ConfirmDialog
        body={removal?.body ?? ""}
        confirmLabel={t("remove")}
        onClose={() => setRemoval(null)}
        onConfirm={() => save(() => (removal ? removal.run() : Promise.resolve()))}
        open={removal !== null}
        title={removal?.title ?? ""}
      />
    </AppShell>
  );
}
