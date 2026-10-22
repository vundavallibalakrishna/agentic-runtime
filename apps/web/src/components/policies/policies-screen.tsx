"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { confirmStepUp } from "@/lib/step-up";

type Row = Record<string, unknown>;

const MODE_KEY = "ar-settings-mode";

export function PoliciesScreen() {
  const t = useTranslations("policies");
  const shell = useTranslations("shell");
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const [name, setName] = useState("Pet writes");
  const [tool, setTool] = useState("petstore.create_pet");
  const [effect, setEffect] = useState("requireApproval");
  const [message, setMessage] = useState("Ask before creating a pet.");
  const [documentText, setDocumentText] = useState("");
  const [decision, setDecision] = useState("");

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api<{ items: Row[] }>("/api/v1/policies");
      setRows(page.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  function documentBody(): Record<string, unknown> {
    if (advanced && documentText.trim()) {
      return JSON.parse(documentText) as Record<string, unknown>;
    }
    return {
      rules: [{ id: "rule-1", effect, message, match: { tools: [tool] } }],
    };
  }

  async function save() {
    setError("");
    setNotice("");
    try {
      await api("/api/v1/policies", {
        method: "POST",
        body: JSON.stringify({ name, description: message, document: documentBody() }),
      });
      setNotice(t("save"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  async function simulate() {
    setError("");
    try {
      const result = await api<Row>("/api/v1/policies:simulate", {
        method: "POST",
        body: JSON.stringify({ toolQualifiedName: tool, args: {} }),
      });
      setDecision(String(result.decision ?? ""));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  async function activate(row: Row) {
    setError("");
    try {
      await confirmStepUp();
      await api(`/api/v1/policies/${String(row.id)}:activate`, {
        method: "POST",
        body: JSON.stringify({ version: Number(row.latestVersion ?? 1) }),
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  return (
    <AppShell>
      <PageHeader title={t("title")} body={t("body")} />
      <a className="mb-4 inline-block underline" href="/approvals">
        {shell("navApprovals")}
      </a>
      <div className="mb-4 flex gap-2">
        <Button
          type="button"
          variant={advanced ? "outline" : "default"}
          onClick={() => setAdvanced(false)}
        >
          {t("simple")}
        </Button>
        <Button
          type="button"
          variant={advanced ? "default" : "outline"}
          onClick={() => setAdvanced(true)}
        >
          {t("advanced")}
        </Button>
      </div>
      {error ? (
        <p role="alert">
          {error}{" "}
          <button className="underline" type="button" onClick={() => void load()}>
            {t("retry")}
          </button>
        </p>
      ) : null}
      {notice ? <p role="status">{notice}</p> : null}
      <form
        className="mb-6 grid max-w-xl gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label htmlFor="policy-name">
          {t("name")}
          <Input id="policy-name" value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label htmlFor="policy-tool">
          {t("tool")}
          <Input id="policy-tool" value={tool} onChange={(event) => setTool(event.target.value)} />
        </label>
        <label htmlFor="policy-effect">
          {t("effect")}
          <select
            id="policy-effect"
            className="mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
            value={effect}
            onChange={(event) => setEffect(event.target.value)}
          >
            <option value="requireApproval">requireApproval</option>
            <option value="deny">deny</option>
            <option value="allow">allow</option>
          </select>
        </label>
        <label htmlFor="policy-message">
          {t("message")}
          <Input
            id="policy-message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
          />
        </label>
        {advanced ? (
          <label htmlFor="policy-document">
            {t("yaml")}
            <textarea
              id="policy-document"
              className="mt-1 h-40 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 font-mono text-xs"
              value={documentText}
              onChange={(event) => setDocumentText(event.target.value)}
            />
          </label>
        ) : null}
        <div className="flex gap-2">
          <Button type="submit">{t("save")}</Button>
          <Button type="button" variant="outline" onClick={() => void simulate()}>
            {t("simulate")}
          </Button>
        </div>
        {decision ? (
          <p>
            {t("decision")}: {decision}
          </p>
        ) : null}
      </form>
      {loading ? (
        <div aria-busy="true">
          <span className="sr-only">{t("loading")}</span>
          <Skeleton className="h-24 w-full" />
        </div>
      ) : null}
      {!loading && rows.length === 0 ? <p>{t("empty")}</p> : null}
      <ul className="space-y-3">
        {rows.map((row) => (
          <li key={String(row.id)} className="rounded-xl border border-[var(--border)] p-4">
            <h2 className="font-medium">{String(row.name)}</h2>
            <p className="text-sm text-[var(--muted-foreground)]">
              {String(row.status)} · {t("versions")} {String(row.latestVersion ?? "")}
            </p>
            {row.status !== "active" ? (
              <Button className="mt-3" type="button" onClick={() => void activate(row)}>
                {t("activate")}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
