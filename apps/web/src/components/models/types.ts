export type ModelKind = "chat" | "embedding" | "rerank";

export const MODEL_KINDS: ModelKind[] = ["chat", "embedding", "rerank"];

export type Provider = {
  id: string;
  name: string;
  kind: string;
  baseUrl: string;
  hasApiKey: boolean;
  platform: boolean;
};

export type Model = {
  id: string;
  providerId: string;
  name: string;
  upstreamModel: string;
  kind: ModelKind;
  platform: boolean;
  embeddingDimensions?: number | null;
  /** What the tenant says the model can do, for example `vision`. */
  capabilities?: string[];
  priceInputMicrosPerMtok?: number;
  priceOutputMicrosPerMtok?: number;
};

export type Alias = {
  id: string;
  alias: string;
  kind: ModelKind;
  primaryModelId: string;
  platform: boolean;
  defaultParams?: Record<string, unknown>;
};

/** An alias the product itself asks for, and the model the tenant pointed it at. */
export type StandardAlias = {
  alias: string;
  kind: ModelKind;
  required: boolean;
  /** What the model must be able to do, beyond being of the kind. */
  capability?: string | null;
  set: boolean;
  aliasId: string | null;
  platform: boolean;
  modelId: string | null;
  modelName: string | null;
};

export type TestResult = { ok: boolean; output: string; latencyMs: number };

/** A test that is running, or what it returned. Keyed by `provider:id`, `model:id`, `alias:id`. */
export type Tests = Record<string, TestResult | "running">;

/** The models an alias the product uses may point at. */
export function modelsFor(item: StandardAlias, models: Model[]): Model[] {
  return models.filter(
    (model) =>
      model.kind === item.kind &&
      (!item.capability || (model.capabilities ?? []).includes(item.capability)),
  );
}

/** Price per million tokens in the tenant currency, stored as integer micros. */
export function toMicros(value: string): number {
  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 0;
  }
  return Math.round(parsed * 1_000_000);
}

export function fromMicros(value: number | undefined): string {
  return value ? String(value / 1_000_000) : "";
}
