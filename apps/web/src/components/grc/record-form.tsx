"use client";

import type { FormEvent } from "react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export type Field = {
  name: string;
  label: string;
  required?: boolean;
  type?: "text" | "textarea" | "select" | "date" | "datetime" | "number";
  options?: { value: string; label: string }[];
  hint?: string;
};

const areaClass =
  "mt-1 min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--foreground)]";
const selectClass =
  "mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)]";

export function RecordForm({
  id,
  title,
  hint,
  fields,
  submitLabel,
  requiredMessage,
  onSubmit,
}: {
  id: string;
  title: string;
  hint?: string;
  fields: Field[];
  submitLabel: string;
  requiredMessage: (label: string) => string;
  onSubmit: (values: Record<string, string>) => Promise<void>;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function setValue(name: string, value: string) {
    setValues((current) => ({ ...current, [name]: value }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const missing = fields.find((field) => field.required && !(values[field.name] || "").trim());
    if (missing) {
      setError(requiredMessage(missing.label));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onSubmit(values);
      setValues({});
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : requiredMessage(title));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      aria-labelledby={`${id}-heading`}
      className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
      onSubmit={(event) => void submit(event)}
    >
      <h2 className="text-base font-semibold" id={`${id}-heading`}>
        {title}
      </h2>
      {hint ? <p className="text-sm text-[var(--muted-foreground)]">{hint}</p> : null}
      {fields.map((field) => {
        const fieldId = `${id}-${field.name}`;
        const value = values[field.name] ?? "";
        return (
          <label className="block text-sm" htmlFor={fieldId} key={field.name}>
            {field.label}
            {field.required ? <span className="text-[var(--destructive)]"> *</span> : null}
            {field.type === "textarea" ? (
              <textarea
                className={areaClass}
                id={fieldId}
                onChange={(event) => setValue(field.name, event.target.value)}
                aria-required={field.required || undefined}
                value={value}
              />
            ) : field.type === "select" ? (
              <select
                aria-required={field.required || undefined}
                className={selectClass}
                id={fieldId}
                onChange={(event) => setValue(field.name, event.target.value)}
                value={value}
              >
                <option value="">Select</option>
                {(field.options ?? []).map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : (
              <Input
                className="mt-1"
                id={fieldId}
                onChange={(event) => setValue(field.name, event.target.value)}
                aria-required={field.required || undefined}
                type={
                  field.type === "datetime"
                    ? "datetime-local"
                    : field.type === "date"
                      ? "date"
                      : field.type === "number"
                        ? "number"
                        : "text"
                }
                value={value}
              />
            )}
            {field.hint ? (
              <span className="mt-1 block text-xs text-[var(--muted-foreground)]">
                {field.hint}
              </span>
            ) : null}
          </label>
        );
      })}
      {error ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      <Button disabled={busy} type="submit">
        {submitLabel}
      </Button>
    </form>
  );
}

export function localIso(value: string | undefined) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toISOString();
}
