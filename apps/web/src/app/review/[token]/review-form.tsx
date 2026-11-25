"use client";

import { useTranslations } from "next-intl";
import { type ReactNode, useEffect, useState } from "react";

import { AuthCard } from "@/components/auth-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";

type Schema = {
  type?: string;
  properties?: Record<string, Schema>;
  items?: Schema;
  required?: string[];
};

type Evidence = {
  path?: string;
  quote?: string;
  page?: number | null;
  confidence?: number;
  status?: string;
};

type ReviewItem = {
  qualifiedName?: string;
  status?: string;
  arguments?: Record<string, unknown>;
  schema?: Schema;
  argsHash?: string;
  preview?: { summary?: string; title?: string; fields?: Evidence[] };
};

type Field = { name: string; schema: Schema; required: boolean };

export function ReviewForm({ token }: { token: string }) {
  const t = useTranslations("review");
  const [item, setItem] = useState<ReviewItem | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [reason, setReason] = useState("");
  const [phase, setPhase] = useState<"loading" | "ready" | "missing" | "done">("loading");
  const [done, setDone] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    api<ReviewItem>(`/api/v1/review/${token}`)
      .then((body) => {
        if (!live) return;
        setItem(body);
        setValues(body.arguments ?? {});
        setPhase("ready");
      })
      .catch(() => {
        if (live) setPhase("missing");
      });
    return () => {
      live = false;
    };
  }, [token]);

  const fields = fieldsOf(item?.schema, item?.arguments);

  async function submit(decision: "approve" | "reject") {
    setBusy(true);
    setError("");
    try {
      const changed = JSON.stringify(values) !== JSON.stringify(item?.arguments ?? {});
      const saved = await api<{ status?: string }>(`/api/v1/review/${token}:decide`, {
        method: "POST",
        body: JSON.stringify({
          decision,
          comment: reason,
          argsHash: item?.argsHash ?? "",
          ...(decision === "approve" && changed ? { arguments: values } : {}),
        }),
      });
      if (decision === "approve" && saved?.status === "pending") {
        setDone(t("pending"));
      } else {
        setDone(decision === "approve" ? t("approved") : t("rejected"));
      }
      setPhase("done");
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        setError(t("signIn"));
      } else {
        setError(caught instanceof Error ? caught.message : t("failed"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard body={t("body")} title={t("title")} wide>
      {phase === "loading" ? (
        <p className="text-sm text-[var(--muted-foreground)]" role="status">
          {t("loading")}
        </p>
      ) : null}
      {phase === "missing" ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {t("missing")}
        </p>
      ) : null}
      {phase === "done" ? (
        <p className="rounded-lg bg-[var(--muted)] px-3 py-2 text-sm" role="status">
          {done}
        </p>
      ) : null}
      {phase === "ready" && item ? (
        <form
          className="space-y-4 text-left"
          onSubmit={(event) => {
            event.preventDefault();
            void submit("approve");
          }}
        >
          <p className="text-sm text-[var(--muted-foreground)]">
            {item.preview?.title || item.qualifiedName}
          </p>
          {item.preview?.summary ? <p className="text-sm">{item.preview.summary}</p> : null}
          {fields.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
          ) : (
            fields.map((field) => (
              <div className="space-y-1" key={field.name}>
                <FieldInput
                  field={field}
                  onChange={(next) => setValues((current) => ({ ...current, [field.name]: next }))}
                  value={values[field.name]}
                />
                <EvidenceLine evidence={evidenceFor(item.preview?.fields, field.name)} />
              </div>
            ))
          )}
          <div className="space-y-1.5">
            <label className="block text-sm font-medium" htmlFor="review-reason">
              {t("reason")}
            </label>
            <textarea
              className="min-h-20 w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
              id="review-reason"
              onChange={(event) => setReason(event.target.value)}
              placeholder={t("reasonHint")}
              value={reason}
            />
          </div>
          {error ? (
            <p className="text-sm text-[var(--destructive)]" role="alert">
              {error}
            </p>
          ) : null}
          <div className="flex gap-2">
            <Button className="h-10 flex-1" disabled={busy} type="submit">
              {busy ? t("working") : t("approve")}
            </Button>
            <Button
              className="h-10 flex-1"
              disabled={busy}
              onClick={() => void submit("reject")}
              type="button"
              variant="outline"
            >
              {t("reject")}
            </Button>
          </div>
        </form>
      ) : null}
    </AuthCard>
  );
}

function fieldsOf(
  schema: Schema | undefined,
  values: Record<string, unknown> | undefined,
): Field[] {
  const properties = schema?.properties ?? {};
  const required = new Set(schema?.required ?? []);
  const names = Object.keys(properties);
  const extra = Object.keys(values ?? {}).filter((name) => !names.includes(name));
  return [...names, ...extra].map((name) => ({
    name,
    schema: properties[name] ?? schemaFor(values?.[name]),
    required: required.has(name),
  }));
}

function schemaFor(value: unknown): Schema {
  if (typeof value === "boolean") return { type: "boolean" };
  if (typeof value === "number") return { type: Number.isInteger(value) ? "integer" : "number" };
  if (Array.isArray(value)) return { type: "array", items: { type: "string" } };
  if (value && typeof value === "object") return { type: "object" };
  return { type: "string" };
}

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: Field;
  value: unknown;
  onChange: (next: unknown) => void;
}) {
  const id = `review-${field.name}`;
  const label = field.name;
  const kind = field.schema.type;
  if (kind === "boolean") {
    return (
      <label className="flex items-center gap-2 text-sm" htmlFor={id}>
        <input
          checked={Boolean(value)}
          id={id}
          onChange={(event) => onChange(event.target.checked)}
          type="checkbox"
        />
        {label}
      </label>
    );
  }
  if (kind === "integer" || kind === "number") {
    return (
      <Labeled id={id} label={label} required={field.required}>
        <Input
          id={id}
          onChange={(event) =>
            onChange(
              kind === "integer"
                ? Number.parseInt(event.target.value, 10)
                : Number(event.target.value),
            )
          }
          required={field.required}
          type="number"
          value={value === undefined || value === null ? "" : String(value)}
        />
      </Labeled>
    );
  }
  if (kind === "array") {
    return (
      <ArrayEditor
        field={field}
        id={id}
        onChange={onChange}
        value={Array.isArray(value) ? value : []}
      />
    );
  }
  if (kind === "object") {
    const record =
      value && typeof value === "object" && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : {};
    return <ObjectEditor field={field} id={id} onChange={onChange} value={record} />;
  }
  return (
    <Labeled id={id} label={label} required={field.required}>
      <Input
        id={id}
        onChange={(event) => onChange(event.target.value)}
        required={field.required}
        value={value === undefined || value === null ? "" : String(value)}
      />
    </Labeled>
  );
}

function Labeled({
  id,
  label,
  required,
  children,
}: {
  id: string;
  label: string;
  required: boolean;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium" htmlFor={id}>
        {label}
        {required ? <span className="text-[var(--destructive)]"> *</span> : null}
      </label>
      {children}
    </div>
  );
}

function evidenceFor(fields: Evidence[] | undefined, name: string): Evidence | undefined {
  return fields?.find((item) => item.path === name || item.path?.startsWith(`${name}.`));
}

function EvidenceLine({ evidence }: { evidence: Evidence | undefined }) {
  const t = useTranslations("review");
  if (!evidence) return null;
  return (
    <p className="text-xs text-[var(--muted-foreground)]">
      {t("quote")}: {evidence.quote || "—"} · {t("page")}: {evidence.page ?? "—"} ·{" "}
      {t("confidence")}: {evidence.confidence ?? "—"} · {t("fieldStatus")}: {evidence.status || "—"}
    </p>
  );
}

function ObjectEditor({
  field,
  id,
  value,
  onChange,
}: {
  field: Field;
  id: string;
  value: Record<string, unknown>;
  onChange: (next: unknown) => void;
}) {
  const properties = field.schema.properties ?? {};
  const names = Object.keys(properties).length > 0 ? Object.keys(properties) : Object.keys(value);
  return (
    <fieldset className="space-y-2 rounded-md border border-[var(--border)] p-3" id={id}>
      <legend className="px-1 text-sm font-medium">{field.name}</legend>
      {names.map((name) => (
        <FieldInput
          field={{
            name,
            schema: properties[name] ?? schemaFor(value[name]),
            required: false,
          }}
          key={name}
          onChange={(next) => onChange({ ...value, [name]: next })}
          value={value[name]}
        />
      ))}
    </fieldset>
  );
}

function ArrayEditor({
  field,
  id,
  value,
  onChange,
}: {
  field: Field;
  id: string;
  value: unknown[];
  onChange: (next: unknown) => void;
}) {
  const t = useTranslations("review");
  const itemSchema = field.schema.items ?? { type: "string" };
  return (
    <fieldset className="space-y-2 rounded-md border border-[var(--border)] p-3" id={id}>
      <legend className="px-1 text-sm font-medium">{field.name}</legend>
      {value.map((item, index) => (
        <div className="flex items-start gap-2" key={`${field.name}-${String(item)}`}>
          <div className="min-w-0 flex-1">
            <FieldInput
              field={{ name: String(index + 1), schema: itemSchema, required: false }}
              onChange={(next) =>
                onChange(value.map((current, itemIndex) => (itemIndex === index ? next : current)))
              }
              value={item}
            />
          </div>
          <Button
            onClick={() => onChange(value.filter((_, itemIndex) => itemIndex !== index))}
            type="button"
            variant="outline"
          >
            {t("remove")}
          </Button>
        </div>
      ))}
      <Button
        onClick={() => onChange([...value, itemSchema.type === "object" ? {} : ""])}
        type="button"
        variant="outline"
      >
        {t("add")}
      </Button>
    </fieldset>
  );
}
