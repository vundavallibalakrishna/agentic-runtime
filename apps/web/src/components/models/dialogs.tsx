"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

import { Field, Problem, Select } from "./parts";
import {
  type Alias,
  fromMicros,
  MODEL_KINDS,
  type Model,
  type ModelKind,
  type Provider,
  type StandardAlias,
  toMicros,
} from "./types";

/** A dialog with a form, its own error and two buttons. The caller's save may fail. */
function FormDialog({
  open,
  title,
  submitLabel,
  onClose,
  onSubmit,
  children,
}: {
  open: boolean;
  title: string;
  submitLabel: string;
  onClose: () => void;
  onSubmit: () => Promise<void>;
  children: ReactNode;
}) {
  const t = useTranslations("models");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setError("");
    }
  }, [open]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSubmit();
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog onOpenChange={(next) => (next ? undefined : onClose())} open={open}>
      <DialogContent title={title}>
        <form className="mt-4 grid gap-4" onSubmit={(event) => void submit(event)}>
          {children}
          {error ? <Problem>{error}</Problem> : null}
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} type="button" variant="outline">
              {t("cancel")}
            </Button>
            <Button disabled={busy} type="submit">
              {submitLabel}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  onClose,
  onConfirm,
}: {
  open: boolean;
  title: string;
  body: string;
  confirmLabel: string;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}) {
  return (
    <FormDialog
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
  provider,
  onClose,
  onSave,
}: {
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
  /** Standard aliases to point at the new model. */
  useFor: string[];
};

/** Add a model to a provider, or change one. `model` is null when adding. */
export function ModelDialog({
  target,
  standard,
  advanced,
  onClose,
  onSave,
}: {
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
  const [useFor, setUseFor] = useState<string[]>([]);

  useEffect(() => {
    setName(model?.name ?? "");
    setUpstream(model?.upstreamModel ?? "");
    setKind(model?.kind ?? "chat");
    setPriceIn(fromMicros(model?.priceInputMicrosPerMtok));
    setPriceOut(fromMicros(model?.priceOutputMicrosPerMtok));
    setDimensions(model?.embeddingDimensions ? String(model.embeddingDimensions) : "");
    setVision((model?.capabilities ?? []).includes("vision"));
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
  return (
    <FormDialog
      onClose={onClose}
      onSubmit={() =>
        onSave({
          name: name.trim() || upstream.trim(),
          upstreamModel: upstream.trim(),
          kind,
          priceIn: toMicros(priceIn),
          priceOut: toMicros(priceOut),
          embeddingDimensions:
            kind === "embedding" && Number.isFinite(parsedDimensions) && parsedDimensions > 0
              ? parsedDimensions
              : null,
          vision: kind === "chat" && vision,
          useFor: model ? [] : useFor.filter((alias) => unset.some((item) => item.alias === alias)),
        })
      }
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
              inputMode="decimal"
              min="0"
              onChange={(event) => setPriceIn(event.target.value)}
              step="0.000001"
              type="number"
              value={priceIn}
            />
          </Field>
          <Field id="model-price-out" label={t("priceOutput")}>
            <Input
              id="model-price-out"
              inputMode="decimal"
              min="0"
              onChange={(event) => setPriceOut(event.target.value)}
              step="0.000001"
              type="number"
              value={priceOut}
            />
          </Field>
          <p className="text-xs leading-relaxed text-[var(--muted-foreground)] sm:col-span-2">
            {t("priceHint")}
          </p>
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
  target,
  models,
  onClose,
  onSave,
}: {
  target: { alias: Alias | null } | null;
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
    setName(alias?.alias ?? "");
    setKind(alias?.kind ?? "chat");
    setModelId(alias?.primaryModelId ?? "");
    const stored = alias?.defaultParams?.temperature;
    setTemperature(typeof stored === "number" ? String(stored) : "");
  }, [alias]);

  const choices = models.filter((model) => model.kind === kind);
  const parsed = Number.parseFloat(temperature);
  return (
    <FormDialog
      onClose={onClose}
      onSubmit={() =>
        onSave({
          alias: name.trim(),
          kind,
          modelId,
          temperature: kind === "chat" && Number.isFinite(parsed) ? parsed : null,
        })
      }
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
          <Field id="alias-kind" label={t("modelKind")}>
            <Select
              id="alias-kind"
              onChange={(next) => {
                setKind(next as ModelKind);
                setModelId("");
              }}
              value={kind}
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
      <Field
        hint={
          choices.length === 0 ? t("noModelOfKind", { kind: t(`kindNames.${kind}`) }) : undefined
        }
        id="alias-model"
        label={t("model")}
      >
        <Select
          disabled={choices.length === 0}
          id="alias-model"
          onChange={setModelId}
          value={modelId}
        >
          <option value="">{t("chooseModel")}</option>
          {choices.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name}
            </option>
          ))}
        </Select>
      </Field>
      {kind === "chat" ? (
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
