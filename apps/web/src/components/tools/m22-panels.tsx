"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

type Row = Record<string, unknown>;

function text(value: unknown) {
  return value == null ? "" : String(value);
}

function field(row: Row, camel: string, snake: string) {
  return row[camel] ?? row[snake];
}

export function M22Panels({ tools, onChanged }: { tools: Row[]; onChanged: () => Promise<void> }) {
  const t = useTranslations("tools");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [specUrl, setSpecUrl] = useState("");
  const [specText, setSpecText] = useState("");
  const [specSlug, setSpecSlug] = useState("imported");
  const [specBase, setSpecBase] = useState("");
  const [specConnection, setSpecConnection] = useState("");
  const [operations, setOperations] = useState<Row[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [sentence, setSentence] = useState(
    "GET https://api.github.com/zen and return the plain text.",
  );
  const [draft, setDraft] = useState<Row | null>(null);
  const [testResult, setTestResult] = useState("");

  async function previewSpec() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const body: Record<string, unknown> = { url: specUrl.trim(), baseUrl: specBase.trim() };
      if (specText.trim()) {
        body.document = JSON.parse(specText) as unknown;
      }
      const preview = await api<{ operations?: Row[]; total?: number; baseUrl?: string }>(
        "/api/v1/openapi-imports:preview",
        { method: "POST", body: JSON.stringify(body) },
      );
      setOperations(preview.operations ?? []);
      setPicked([]);
      if (preview.baseUrl) {
        setSpecBase(preview.baseUrl);
      }
      setNotice(t("importCount", { count: preview.total ?? preview.operations?.length ?? 0 }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function importSpec() {
    setBusy(true);
    setError("");
    try {
      const body: Record<string, unknown> = {
        slug: specSlug.trim(),
        name: specSlug.trim(),
        url: specUrl.trim(),
        baseUrl: specBase.trim(),
        connection: specConnection.trim(),
        operations: picked,
      };
      if (specText.trim()) {
        body.document = JSON.parse(specText) as unknown;
      }
      await api("/api/v1/openapi-imports", { method: "POST", body: JSON.stringify(body) });
      setNotice(t("importSaved"));
      await onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function reviewSentence() {
    setBusy(true);
    setError("");
    setTestResult("");
    try {
      const reviewed = await api<Row>("/api/v1/described-tools:preview", {
        method: "POST",
        body: JSON.stringify({ description: sentence }),
      });
      setDraft(reviewed);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function saveSentence() {
    if (!draft) return;
    setBusy(true);
    setError("");
    try {
      await api("/api/v1/described-tools", {
        method: "POST",
        body: JSON.stringify({
          description: sentence,
          slug: text(field(draft, "name", "name")),
          name: text(field(draft, "title", "title")),
          method: text(field(draft, "method", "method")),
          url: text(field(draft, "url", "url")),
          connection: text(field(draft, "connection", "connection")),
          returns: text(field(draft, "returns", "returns")),
        }),
      });
      setNotice(t("describeSaved"));
      await onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function testTool(toolId: string) {
    setBusy(true);
    setError("");
    try {
      const result = await api<Row>(`/api/v1/tools/${toolId}:test`, {
        method: "POST",
        body: JSON.stringify({ arguments: {} }),
      });
      setTestResult(
        `${text(field(result, "status", "status"))} ${text(field(result, "resultPreview", "result_preview"))}`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function toggleTool(tool: Row, enabled: boolean) {
    const id = text(field(tool, "toolId", "tool_id"));
    if (!id) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/tools/${id}:${enabled ? "enable" : "disable"}`, {
        method: "POST",
        body: JSON.stringify(enabled ? {} : { reason: "turned off from the registry" }),
      });
      await onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  function toggleOperation(id: string) {
    setPicked((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  return (
    <div className="mt-8 grid gap-6">
      {error ? (
        <p role="alert" className="text-sm text-[var(--destructive)]">
          {error}
        </p>
      ) : null}
      {notice ? <p role="status">{notice}</p> : null}
      <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-lg font-medium">{t("importTitle")}</h2>
        <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("importBody")}</p>
        <div className="mt-3 grid gap-3">
          <label className="block text-sm" htmlFor="openapi-url">
            {t("importUrl")}
            <Input
              id="openapi-url"
              onChange={(event) => setSpecUrl(event.target.value)}
              value={specUrl}
            />
          </label>
          <label className="block text-sm" htmlFor="openapi-document">
            {t("importDocument")}
            <textarea
              className="mt-1 min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-sm"
              id="openapi-document"
              onChange={(event) => setSpecText(event.target.value)}
              value={specText}
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-3">
              <label className="block text-sm" htmlFor="openapi-slug">
                {t("importSlug")}
              <Input
                id="openapi-slug"
                onChange={(event) => setSpecSlug(event.target.value)}
                value={specSlug}
              />
            </label>
            <label className="block text-sm" htmlFor="openapi-base">
              {t("importBase")}
              <Input
                id="openapi-base"
                onChange={(event) => setSpecBase(event.target.value)}
                value={specBase}
              />
            </label>
            <label className="block text-sm" htmlFor="openapi-connection">
              {t("importConnection")}
              <Input
                id="openapi-connection"
                onChange={(event) => setSpecConnection(event.target.value)}
                value={specConnection}
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={busy}
              onClick={() => void previewSpec()}
              type="button"
              variant="outline"
            >
              {t("importPreview")}
            </Button>
            <Button disabled={busy} onClick={() => void importSpec()} type="button">
              {t("importSave")}
            </Button>
          </div>
          {operations.length > 0 ? (
            <ul className="max-h-48 space-y-1 overflow-auto text-sm">
              {operations.slice(0, 40).map((operation) => {
                const id = text(field(operation, "operationId", "operation_id"));
                return (
                  <li key={id}>
                    <label className="flex items-center gap-2">
                      <input
                        checked={picked.includes(id)}
                        onChange={() => toggleOperation(id)}
                        type="checkbox"
                      />
                      <span>
                        {text(operation.method)} {text(operation.path)} · {id}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
      </section>
      <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-lg font-medium">{t("describeTitle")}</h2>
        <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("describeBody")}</p>
        <label className="mt-3 block text-sm" htmlFor="describe-sentence">
          {t("describeText")}
          <textarea
            className="mt-1 min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-sm"
            id="describe-sentence"
            onChange={(event) => setSentence(event.target.value)}
            value={sentence}
          />
        </label>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            disabled={busy}
            onClick={() => void reviewSentence()}
            type="button"
            variant="outline"
          >
            {t("describeReview")}
          </Button>
          <Button disabled={busy || !draft} onClick={() => void saveSentence()} type="button">
            {t("describeSave")}
          </Button>
        </div>
        {draft ? (
          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--muted)] p-3 text-xs">
            {JSON.stringify(
              {
                name: field(draft, "name", "name"),
                method: field(draft, "method", "method"),
                url: field(draft, "url", "url"),
                connection: field(draft, "connection", "connection"),
                riskClass: field(draft, "riskClass", "risk_class"),
                parameters: field(draft, "parameters", "parameters"),
              },
              null,
              2,
            )}
          </pre>
        ) : null}
      </section>
      <section>
        <h2 className="mb-2 text-lg font-medium">{t("catalogue")}</h2>
        {tools.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
        ) : (
          <ul className="grid gap-2">
            {tools.slice(0, 40).map((tool) => {
              const name = text(field(tool, "qualifiedName", "qualified_name"));
              const risk = text(field(tool, "riskClass", "risk_class"));
              const disabled = Boolean(tool.disabled);
              const id = text(field(tool, "toolId", "tool_id"));
              return (
                <li
                  className="rounded-xl border border-[var(--border)] px-3 py-2 text-sm"
                  key={id || name}
                >
                  <p className="font-medium">{name}</p>
                  <p className="text-[var(--muted-foreground)]">
                    {text(tool.source) || "builtin"} · {text(tool.status)} · {risk}
                    {risk === "W2" || risk === "W3" ? ` · ${t("risky")}` : ""}
                  </p>
                  <p className="text-[var(--muted-foreground)]">
                    {t("callsCount", { count: Number(field(tool, "calls", "calls") ?? 0) })} ·{" "}
                    {t("limits", {
                      timeout: text(field(tool, "timeoutS", "timeout_s")),
                      rate: text(field(tool, "rateLimitPerMinute", "rate_limit_per_minute")),
                      size: text(field(tool, "maxResultBytes", "max_result_bytes")),
                    })}
                  </p>
                  {text(field(tool, "lastError", "last_error")) ? (
                    <p>{text(field(tool, "lastError", "last_error"))}</p>
                  ) : null}
                  {Array.isArray(tool.egress) && tool.egress.length > 0 ? (
                    <p className="text-[var(--muted-foreground)]">{tool.egress.join(", ")}</p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      disabled={busy || !id}
                      onClick={() => void toggleTool(tool, disabled)}
                      type="button"
                      variant="outline"
                    >
                      {disabled ? t("enable") : t("disable")}
                    </Button>
                    {text(tool.source) === "custom" ? (
                      <Button
                        disabled={busy || !id}
                        onClick={() => void testTool(id)}
                        type="button"
                        variant="outline"
                      >
                        {t("describeTest")}
                      </Button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {testResult ? <p role="status">{testResult}</p> : null}
      </section>
    </div>
  );
}
