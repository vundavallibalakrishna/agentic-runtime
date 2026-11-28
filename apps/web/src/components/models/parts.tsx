"use client";

import { useTranslations } from "next-intl";
import { type ReactNode, useCallback, useMemo } from "react";

import { ErrorMessage } from "@/components/common/detail-state";
import { ReferencePicker } from "@/components/common/reference-picker";

import { Button } from "@/components/ui/button";

import { MODEL_KINDS, type Model, type TestState } from "./types";

const SELECT =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 text-sm disabled:opacity-60";

export function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-1">
      <label className="text-sm font-medium" htmlFor={id}>
        {label}
      </label>
      {children}
      {hint ? (
        <p className="text-xs leading-relaxed text-[var(--muted-foreground)]" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function Select({
  id,
  value,
  onChange,
  disabled,
  label,
  children,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  label?: string;
  children: ReactNode;
}) {
  return (
    <select
      aria-label={label}
      className={SELECT}
      disabled={disabled}
      id={id}
      onChange={(event) => onChange(event.target.value)}
      value={value}
    >
      {children}
    </select>
  );
}

/** An error the person can act on, with room around it and a way to dismiss or retry. */
export function Problem({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div
      className="flex flex-wrap items-center gap-3 rounded-lg border border-[var(--destructive)] bg-[var(--card)] px-4 py-3 text-sm"
      role="alert"
    >
      <div className="min-w-0 flex-1 leading-relaxed">{children}</div>
      {action}
    </div>
  );
}

/** What a test returned, said in words: it answered, or why it did not. */
export function TestLine({ result }: { result: TestState | undefined }) {
  const t = useTranslations("models");
  if (result === undefined) {
    return null;
  }
  if (result === "running") {
    return (
      <p className="text-xs text-[var(--muted-foreground)]" role="status">
        {t("testing")}
      </p>
    );
  }
  if (result instanceof Error)
    return (
      <div className="mt-2 text-xs" role="alert">
        <p className="mb-1 font-medium">{t("testUnavailable")}</p>
        <ErrorMessage error={result} />
      </div>
    );
  return (
    <p className="mt-1 break-words text-xs leading-relaxed" role="status">
      <span
        className={
          result.ok ? "font-medium text-[var(--success)]" : "font-medium text-[var(--destructive)]"
        }
      >
        {result.ok ? t("testPassed") : t("testFailed")}
      </span>{" "}
      <span className="text-[var(--muted-foreground)]">
        {result.ok
          ? t("testAnswer", { output: result.output, ms: result.latencyMs })
          : result.output}
      </span>
    </p>
  );
}

export function RowActions({ children }: { children: ReactNode }) {
  return <div className="flex shrink-0 flex-wrap items-center gap-1">{children}</div>;
}

export function SmallButton({
  children,
  onClick,
  disabled,
  label,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <Button
      aria-label={label}
      className="px-2 py-1 text-xs"
      disabled={disabled}
      onClick={onClick}
      type="button"
      variant="outline"
    >
      {children}
    </Button>
  );
}

type ModelChoice = Pick<Model, "id" | "name"> &
  Partial<Pick<Model, "kind" | "providerId" | "upstreamModel">>;

/** A model choice keeps provider/upstream context and reuses the shared bounded picker. */
export function ModelPicker({
  models,
  providerNames,
  value,
  selectionName,
  onChange,
  label,
  disabled = false,
  hideLabel = false,
  clearable = true,
  required = false,
  help,
}: {
  models: Model[];
  providerNames: ReadonlyMap<string, string>;
  value: string;
  selectionName?: string | null;
  onChange: (value: string) => void;
  label: string;
  disabled?: boolean;
  hideLabel?: boolean;
  clearable?: boolean;
  required?: boolean;
  help?: string;
}) {
  const t = useTranslations("models");
  const kinds = useMemo(() => new Map(MODEL_KINDS.map((kind) => [kind, t(`kinds.${kind}`)])), [t]);
  const getLabel = useCallback(
    (row: ModelChoice) =>
      [row.name || row.id, row.providerId ? providerNames.get(row.providerId) : null]
        .filter(Boolean)
        .join(" · "),
    [providerNames],
  );
  const getDescription = useCallback(
    (row: ModelChoice) =>
      [row.kind ? kinds.get(row.kind) : null, row.upstreamModel || row.id]
        .filter(Boolean)
        .join(" · "),
    [kinds],
  );
  const selected = value ? models.find((model) => model.id === value) : null;
  const selection =
    selected ?? (value && selectionName ? { id: value, name: selectionName } : null);
  return (
    <ReferencePicker<ModelChoice>
      items={models}
      selection={selection}
      label={label}
      value={value}
      onChange={onChange}
      getLabel={getLabel}
      getDescription={getDescription}
      disabled={disabled}
      hideLabel={hideLabel}
      clearable={clearable}
      required={required}
      help={help}
    />
  );
}
