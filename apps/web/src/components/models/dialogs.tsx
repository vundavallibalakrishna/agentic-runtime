"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { ActionStatus, ErrorMessage } from "@/components/common/detail-state";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { DisplayError } from "@/lib/api";
import { CURRENCY_AMOUNT_PATTERN, fromMicros, toMicros } from "@/lib/format";

import { Field, ModelPicker, Problem, Select } from "./parts";
import {
  type Alias,
  DEFAULT_RERANK_FLOOR,
  MODEL_KINDS,
  type Model,
  type ModelKind,
  modelsFor,
  type Provider,
  type RerankRoute,
  rerankRoute,
  type StandardAlias,
} from "./types";

/** A dialog with a form, its own error and two buttons. The caller's save may fail. */
/** A typed bar between 0 and 1; anything else is the product's default. */
function floorOf(text: string): number {
  const value = Number.parseFloat(text);
  return Number.isFinite(value) && value >= 0 && value <= 1 ? value : DEFAULT_RERANK_FLOOR;
}

function FormDialog({
  blocked = false,
  open,
  title,
  submitLabel,
  onClose,
  onSubmit,
  children,
}: {
  blocked?: boolean;
  open: boolean;
  title: string;
  submitLabel: string;
  onClose: () => void;
  onSubmit: () => Promise<void>;
  children: ReactNode;
}) {
  const t = useTranslations("models");
  const [busy, setBusy] = useState(false);
  const returnFocus = useRef<HTMLElement | null>(null);
  const [error, setError] = useState<DisplayError>("");

  useEffect(() => {
    if (open) {
      setError("");
    }
  }, [open]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || blocked) return;
    setBusy(true);
    setError("");
    try {
      await onSubmit();
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught : t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog onOpenChange={(next) => (next ? undefined : onClose())} open={open}>
      <DialogContent
        title={title}
        onOpenAutoFocus={() => {
          returnFocus.current =
            document.activeElement instanceof HTMLElement ? document.activeElement : null;
        }}
        onCloseAutoFocus={(event) => {
          const opener = returnFocus.current;
          const target =
            opener?.isConnected && !opener.matches(":disabled") && opener !== document.body
              ? opener
              : document.getElementById("main-content");
          if (target) {
            event.preventDefault();
            target.focus({ preventScroll: true });
          }
        }}
      >
        <form className="mt-4 grid gap-4" onSubmit={(event) => void submit(event)}>
          <fieldset disabled={busy || blocked} aria-label={title} className="min-w-0 grid gap-4">
            {children}
          </fieldset>
          <ActionStatus busy={busy} />
          {error ? (
            <Problem>
              <ErrorMessage error={error} />
            </Problem>
          ) : null}
          {blocked ? <Problem>{t("refreshRequired")}</Problem> : null}
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} type="button" variant="outline">
              {t("cancel")}
            </Button>
            <Button disabled={busy || blocked} type="submit">
              {submitLabel}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ConfirmDialog({
  blocked = false,
  open,
  title,
  body,
  confirmLabel,
  onClose,
  onConfirm,
}: {
  blocked?: boolean;
  open: boolean;
  title: string;
  body: string;
  confirmLabel: string;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}) {
  return (
    <FormDialog
      blocked={blocked}
      onClose={onClose}
      onSubmit={onConfirm}
      open={open}
      submitLabel={confirmLabel}
      title={title}
    >
      <p className="text-sm leading-relaxed text-[var(--muted-foreground)]">{body}</p>
    </FormDialog>
  );
}

export type ProviderChange = { name: string; baseUrl: string; apiKey: string };

export function ProviderDialog({
  blocked = false,
  provider,
  onClose,
  onSave,
}: {
  blocked?: boolean;
  provider: Provider | null;
  onClose: () => void;
  onSave: (change: ProviderChange) => Promise<void>;
}) {
  const t = useTranslations("models");
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");

  useEffect(() => {
    setName(provider?.name ?? "");
    setBaseUrl(provider?.baseUrl ?? "");
    setApiKey("");
  }, [provider]);

  return (
    <FormDialog
      blocked={blocked}
      onClose={onClose}
      onSubmit={() => onSave({ name, baseUrl, apiKey })}
      open={provider !== null}
      submitLabel={t("save")}
      title={t("editProvider")}
    >
      <Field id="edit-provider-name" label={t("name")}>
        <Input
          id="edit-provider-name"
          onChange={(event) => setName(event.target.value)}
          required
          value={name}
        />
      </Field>
      <Field id="edit-provider-url" label={t("url")}>
        <Input
          id="edit-provider-url"
          inputMode="url"
          onChange={(event) => setBaseUrl(event.target.value)}
          required
          value={baseUrl}
        />
      </Field>
      <Field
        hint={provider?.hasApiKey ? t("replaceKeyHint") : t("apiKeyHint")}
        id="edit-provider-key"
        label={provider?.hasApiKey ? t("replaceKey") : t("apiKey")}
      >
        <Input
          aria-describedby="edit-provider-key-hint"
          autoComplete="off"
          id="edit-provider-key"
          onChange={(event) => setApiKey(event.target.value)}
          type="password"
          value={apiKey}
        />
      </Field>
    </FormDialog>
  );
}

export type ModelChange = {
  name: string;
  upstreamModel: string;
  kind: ModelKind;
  priceIn: number;
  priceOut: number;
  embeddingDimensions: number | null;
  /** True when the tenant says this chat model can read images. */
  vision: boolean;
  /** Where a rerank model is called and how the request is shaped. */
  rerank: RerankRoute;
  /** Standard aliases to point at the new model. */
  useFor: string[];
  /** Extra fields sent to the provider with each request. Null leaves them as they are. */
  requestOptions: Record<string, unknown> | null;
};

/** The model's own request options, without the rerank route the dialog edits elsewhere. */
function optionsText(model: Model | null): string {
  const { rerank: _rerank, ...rest } = model?.requestOptions ?? {};
  return Object.keys(rest).length > 0 ? JSON.stringify(rest, null, 2) : "";
}

/** The typed options as an object, or null when the text is not a JSON object. */
function parsedOptions(text: string): Record<string, unknown> | null {
  if (!text.trim()) return {};
  try {
    const value: unknown = JSON.parse(text);
    return value && typeof value === "object" && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

/** Add a model to a provider, or change one. `model` is null when adding. */
export function ModelDialog({
  blocked = false,
  target,
  standard,
  advanced,
  onClose,
  onSave,
}: {
  blocked?: boolean;
  target: { provider: Provider; model: Model | null } | null;
  standard: StandardAlias[];
  advanced: boolean;
  onClose: () => void;
  onSave: (change: ModelChange) => Promise<void>;
}) {
  const t = useTranslations("models");
  const model = target?.model ?? null;
  const [name, setName] = useState("");
  const [upstream, setUpstream] = useState("");
  const [kind, setKind] = useState<ModelKind>("chat");
  const [priceIn, setPriceIn] = useState("");
  const [priceOut, setPriceOut] = useState("");
  const [dimensions, setDimensions] = useState("");
  const [vision, setVision] = useState(false);
  const [rerankPath, setRerankPath] = useState("/rerank");
  const [rerankBody, setRerankBody] = useState<"query" | "queries">("query");
  const [rerankFloor, setRerankFloor] = useState(String(DEFAULT_RERANK_FLOOR));
  const [useFor, setUseFor] = useState<string[]>([]);
  const [options, setOptions] = useState("");

  useEffect(() => {
    setOptions(optionsText(model));
    setName(model?.name ?? "");
    setUpstream(model?.upstreamModel ?? "");
    setKind(model?.kind ?? "chat");
    setPriceIn(fromMicros(model?.priceInputMicrosPerMtok));
    setPriceOut(fromMicros(model?.priceOutputMicrosPerMtok));
    setDimensions(model?.embeddingDimensions ? String(model.embeddingDimensions) : "");
    setVision((model?.capabilities ?? []).includes("vision"));
    const route = rerankRoute(model);
    setRerankPath(route.path);
    setRerankBody(route.body);
    setRerankFloor(String(route.min_score));
  }, [model]);

  // Offer the names the product uses that still have no model of this kind.
  const unset = standard.filter(
    (item) => item.kind === kind && !item.set && (!item.capability || vision),
  );
  const offered = unset.map((item) => item.alias).join(",");
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset the choice when the offer changes
  useEffect(() => {
    setUseFor(model ? [] : unset.filter((item) => item.required).map((item) => item.alias));
  }, [offered, model]);

  function toggle(alias: string) {
    setUseFor((current) =>
      current.includes(alias) ? current.filter((item) => item !== alias) : [...current, alias],
    );
  }

  const parsedDimensions = Number.parseInt(dimensions, 10);
  const typedOptions = parsedOptions(options);
  return (
    <FormDialog
      blocked={blocked}
      onClose={onClose}
      onSubmit={async () => {
        if (typedOptions === null) throw new Error(t("requestOptionsInvalid"));
        const inputPrice = priceIn.trim() ? toMicros(priceIn) : 0;
        const outputPrice = priceOut.trim() ? toMicros(priceOut) : 0;
        if (inputPrice === null || outputPrice === null) throw new Error(t("invalidPrice"));
        await onSave({
          requestOptions: advanced && kind === "chat" ? typedOptions : null,
          name: name.trim() || upstream.trim(),
          upstreamModel: upstream.trim(),
          kind,
          priceIn: inputPrice,
          priceOut: outputPrice,
          embeddingDimensions:
            kind === "embedding" && Number.isFinite(parsedDimensions) && parsedDimensions > 0
              ? parsedDimensions
              : null,
          vision: kind === "chat" && vision,
          rerank: {
            path: rerankPath.trim() || "/rerank",
            body: rerankBody,
            min_score: floorOf(rerankFloor),
          },
          useFor: model ? [] : useFor.filter((alias) => unset.some((item) => item.alias === alias)),
        });
      }}
      open={target !== null}
      submitLabel={model ? t("save") : t("addModel")}
      title={model ? t("editModel") : t("addModelTo", { provider: target?.provider.name ?? "" })}
    >
      <Field hint={t("upstreamHint")} id="model-upstream" label={t("upstream")}>
        <Input
          aria-describedby="model-upstream-hint"
          id="model-upstream"
          onChange={(event) => setUpstream(event.target.value)}
          required
          value={upstream}
        />
      </Field>
      <Field hint={t("modelNameHint")} id="model-name" label={t("modelName")}>
        <Input
          aria-describedby="model-name-hint"
          id="model-name"
          onChange={(event) => setName(event.target.value)}
          value={name}
        />
      </Field>
      {model ? null : (
        <Field hint={t(`kindHint.${kind}`)} id="model-kind" label={t("modelKind")}>
          <Select id="model-kind" onChange={(next) => setKind(next as ModelKind)} value={kind}>
            {MODEL_KINDS.map((item) => (
              <option key={item} value={item}>
                {t(`kinds.${item}`)}
              </option>
            ))}
          </Select>
        </Field>
      )}
      {kind === "chat" ? (
        <label className="flex items-start gap-2 text-sm">
          <input
            checked={vision}
            className="mt-1"
            onChange={(event) => setVision(event.target.checked)}
            type="checkbox"
          />
          <span>
            {t("canReadImages")}{" "}
            <span className="text-[var(--muted-foreground)]">{t("canReadImagesHint")}</span>
          </span>
        </label>
      ) : null}
      {!model && unset.length > 0 ? (
        <fieldset className="grid gap-2">
          <legend className="text-sm font-medium">{t("useFor")}</legend>
          {unset.map((item) => (
            <label className="flex items-start gap-2 text-sm" key={item.alias}>
              <input
                checked={useFor.includes(item.alias)}
                className="mt-1"
                onChange={() => toggle(item.alias)}
                type="checkbox"
              />
              <span>
                {t(`uses.${item.alias}.title`)}{" "}
                <span className="text-[var(--muted-foreground)]">
                  {t(`uses.${item.alias}.body`)}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
      ) : null}
      {advanced && kind === "chat" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field id="model-price-in" label={t("priceInput")}>
            <Input
              id="model-price-in"
              aria-describedby="model-price-help"
              title={t("invalidPrice")}
              inputMode="decimal"
              onChange={(event) => setPriceIn(event.target.value)}
              pattern={CURRENCY_AMOUNT_PATTERN}
              type="text"
              value={priceIn}
            />
          </Field>
          <Field id="model-price-out" label={t("priceOutput")}>
            <Input
              id="model-price-out"
              aria-describedby="model-price-help"
              title={t("invalidPrice")}
              inputMode="decimal"
              onChange={(event) => setPriceOut(event.target.value)}
              pattern={CURRENCY_AMOUNT_PATTERN}
              type="text"
              value={priceOut}
            />
          </Field>
          <p
            id="model-price-help"
            className="text-xs leading-relaxed text-[var(--muted-foreground)] sm:col-span-2"
          >
            {t("priceHint")}
          </p>
          <div className="sm:col-span-2">
            <Field hint={t("requestOptionsHint")} id="model-options" label={t("requestOptions")}>
              <textarea
                aria-describedby="model-options-hint"
                aria-invalid={typedOptions === null}
                className="min-h-28 w-full rounded-md border border-[var(--border)] bg-[var(--background)] p-3 font-mono text-sm"
                id="model-options"
                onChange={(event) => setOptions(event.target.value)}
                spellCheck={false}
                value={options}
              />
            </Field>
            {typedOptions === null ? (
              <p className="mt-1 text-sm text-[var(--destructive)]" role="alert">
                {t("requestOptionsInvalid")}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
      {advanced && kind === "rerank" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field hint={t("rerankPathHint")} id="model-rerank-path" label={t("rerankPath")}>
            <Input
              aria-describedby="model-rerank-path-hint"
              id="model-rerank-path"
              onChange={(event) => setRerankPath(event.target.value)}
              value={rerankPath}
            />
          </Field>
          <Field hint={t("rerankBodyHint")} id="model-rerank-body" label={t("rerankBody")}>
            <Select
              id="model-rerank-body"
              onChange={(next) => setRerankBody(next === "queries" ? "queries" : "query")}
              value={rerankBody}
            >
              <option value="query">{t("rerankBodyQuery")}</option>
              <option value="queries">{t("rerankBodyQueries")}</option>
            </Select>
          </Field>
          <Field hint={t("rerankFloorHint")} id="model-rerank-floor" label={t("rerankFloor")}>
            <Input
              aria-describedby="model-rerank-floor-hint"
              id="model-rerank-floor"
              inputMode="decimal"
              max={1}
              min={0}
              onChange={(event) => setRerankFloor(event.target.value)}
              step="0.01"
              type="number"
              value={rerankFloor}
            />
          </Field>
        </div>
      ) : null}
      {advanced && kind === "embedding" ? (
        <Field hint={t("dimensionsHint")} id="model-dimensions" label={t("dimensions")}>
          <Input
            aria-describedby="model-dimensions-hint"
            id="model-dimensions"
            inputMode="numeric"
            min="1"
            onChange={(event) => setDimensions(event.target.value)}
            type="number"
            value={dimensions}
          />
        </Field>
      ) : null}
    </FormDialog>
  );
}

export type AliasChange = {
  alias: string;
  kind: ModelKind;
  modelId: string;
  temperature: number | null;
};

/** Add an alias of the tenant's own, or change what one points at and sends. */
export function AliasDialog({
  blocked = false,
  target,
  providerNames,
  standard,
  models,
  onClose,
  onSave,
}: {
  blocked?: boolean;
  target: { alias: Alias | null } | null;
  providerNames: ReadonlyMap<string, string>;
  standard: StandardAlias[];
  models: Model[];
  onClose: () => void;
  onSave: (change: AliasChange) => Promise<void>;
}) {
  const t = useTranslations("models");
  const alias = target?.alias ?? null;
  const [name, setName] = useState("");
  const [kind, setKind] = useState<ModelKind>("chat");
  const [modelId, setModelId] = useState("");
  const [temperature, setTemperature] = useState("");

  useEffect(() => {
    const current = target?.alias;
    setName(current?.alias ?? "");
    setKind(current?.kind ?? "chat");
    setModelId(current?.primaryModelId ?? "");
    const stored = current?.defaultParams?.temperature;
    setTemperature(typeof stored === "number" ? String(stored) : "");
  }, [target]);

  const standardUse = standard.find((item) => item.alias === (alias?.alias ?? name.trim()));
  const effectiveKind = standardUse?.kind ?? kind;
  const choices = standardUse
    ? modelsFor(standardUse, models)
    : models.filter((model) => model.kind === effectiveKind);
  const parsed = Number.parseFloat(temperature);
  return (
    <FormDialog
      blocked={blocked}
      onClose={onClose}
      onSubmit={async () => {
        if (!modelId || !choices.some((model) => model.id === modelId))
          throw new Error(t("chooseModel"));
        await onSave({
          alias: name.trim(),
          kind: effectiveKind,
          modelId,
          temperature: effectiveKind === "chat" && Number.isFinite(parsed) ? parsed : null,
        });
      }}
      open={target !== null}
      submitLabel={alias ? t("save") : t("addAlias")}
      title={alias ? t("editAlias", { alias: alias.alias }) : t("addAlias")}
    >
      {alias ? null : (
        <>
          <Field hint={t("aliasNameHint")} id="alias-name" label={t("aliasName")}>
            <Input
              aria-describedby="alias-name-hint"
              id="alias-name"
              onChange={(event) => setName(event.target.value)}
              pattern="[a-z][a-z0-9_\-]{1,40}"
              required
              value={name}
            />
          </Field>
          <Field
            id="alias-kind"
            label={t("modelKind")}
            hint={standardUse ? t("standardKindHelp") : undefined}
          >
            <Select
              id="alias-kind"
              disabled={Boolean(standardUse)}
              onChange={(next) => {
                setKind(next as ModelKind);
                setModelId("");
              }}
              value={effectiveKind}
            >
              {MODEL_KINDS.map((item) => (
                <option key={item} value={item}>
                  {t(`kinds.${item}`)}
                </option>
              ))}
            </Select>
          </Field>
        </>
      )}
      <div className="grid gap-1">
        <ModelPicker
          models={choices}
          providerNames={providerNames}
          label={t("model")}
          value={modelId}
          selectionName={modelId ? models.find((model) => model.id === modelId)?.name : null}
          disabled={choices.length === 0}
          required
          onChange={setModelId}
          help={t("pickerDraftHelp")}
        />
        {choices.length === 0 ? (
          <p className="text-xs text-[var(--muted-foreground)]">
            {standardUse?.capability
              ? t(`needs.${standardUse.capability}`)
              : t("noModelOfKind", { kind: t(`kindNames.${effectiveKind}`) })}
          </p>
        ) : null}
        {modelId && !choices.some((model) => model.id === modelId) ? (
          <p className="text-xs text-[var(--destructive)]">{t("incompatibleAssignment")}</p>
        ) : null}
      </div>
      {effectiveKind === "chat" ? (
        <Field hint={t("temperatureHint")} id="alias-temperature" label={t("temperature")}>
          <Input
            aria-describedby="alias-temperature-hint"
            id="alias-temperature"
            inputMode="decimal"
            max="2"
            min="0"
            onChange={(event) => setTemperature(event.target.value)}
            step="0.1"
            type="number"
            value={temperature}
          />
        </Field>
      ) : null}
    </FormDialog>
  );
}
