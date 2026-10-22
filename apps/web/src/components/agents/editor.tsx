"use client";

import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { MemoryReview } from "@/components/agent-builder/MemoryReview";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { definitionToYaml, type JsonValue, yamlToDefinition } from "@/lib/agent-yaml";
import { api } from "@/lib/api";

import type { AgentDetail, Definition, ValidationReport } from "./types";

const ADVANCED = ["instructions", "model", "tools", "knowledge", "yaml"] as const;

export function AgentEditor() {
  const t = useTranslations("agents");
  const params = useParams<{ id: string }>();
  const agentId = params.id;
  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [definition, setDefinition] = useState<Definition>({});
  const [yaml, setYaml] = useState("");
  const [yamlError, setYamlError] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [tab, setTab] = useState<(typeof ADVANCED)[number]>("instructions");
  const [note, setNote] = useState("");
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [versions, setVersions] = useState<{ version: number; state: string }[]>([]);
  const [chatText, setChatText] = useState("");
  const [chatReply, setChatReply] = useState("");
  const [bundle, setBundle] = useState("");
  const [importText, setImportText] = useState("");
  const [importResult, setImportResult] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const body = await api<AgentDetail>(`/api/v1/agents/${agentId}`);
      const source = body.draft?.definition ?? body.published?.definition ?? {};
      setAgent(body);
      setDefinition(source);
      setYaml(definitionToYaml(source as JsonValue));
      const history = await api<{ items: { version: number; state: string }[] }>(
        `/api/v1/agents/${agentId}/versions`,
      );
      setVersions(history.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [agentId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  function updateDefinition(next: Definition) {
    setDefinition(next);
    setYaml(definitionToYaml(next as JsonValue));
    setYamlError("");
  }

  function applyYaml(text: string) {
    setYaml(text);
    try {
      const parsed = yamlToDefinition(text);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error(t("yamlInvalid"));
      }
      setDefinition(parsed as Definition);
      setYamlError("");
    } catch (caught) {
      setYamlError(caught instanceof Error ? caught.message : t("yamlInvalid"));
    }
  }

  async function save() {
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/agents/${agentId}/versions/draft`, {
        method: "PUT",
        body: JSON.stringify({ definition, changeNote: note }),
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function validate() {
    setBusy(true);
    try {
      await save();
      setReport(
        await api<ValidationReport>(`/api/v1/agents/${agentId}:validate`, {
          method: "POST",
          body: "{}",
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    setBusy(true);
    setError("");
    try {
      await save();
      await api(`/api/v1/agents/${agentId}:publish`, {
        method: "POST",
        body: JSON.stringify({ changeNote: note || t("publishedNote") }),
      });
      setNote("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function rollback(version: number) {
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/agents/${agentId}:rollback`, {
        method: "POST",
        body: JSON.stringify({ version, changeNote: t("rollbackNote") }),
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function testChat() {
    setBusy(true);
    setChatReply("");
    setError("");
    try {
      await save();
      const fresh = await api<AgentDetail>(`/api/v1/agents/${agentId}`);
      const versionId = fresh.draft?.id;
      const conversation = await api<{ id: string }>("/api/v1/conversations", {
        method: "POST",
        body: JSON.stringify({ agentVersionId: versionId }),
      });
      const posted = await api<{ run: { id: string } }>(
        `/api/v1/conversations/${conversation.id}/messages`,
        {
          method: "POST",
          body: JSON.stringify({ text: chatText }),
        },
      );
      const runId = posted.run.id;
      let summary = "";
      for (let attempt = 0; attempt < 20; attempt += 1) {
        const run = await api<{ status: string; resultSummary?: string }>(`/api/v1/runs/${runId}`);
        if (run.status === "completed" || run.status === "failed") {
          summary = run.resultSummary ?? run.status;
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
      setChatReply(summary || t("chatWaiting"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function exportBundle() {
    const document = await api<JsonValue>(`/api/v1/bundles:export?ids=${agentId}`, {
      headers: { accept: "application/json" },
    });
    setBundle(definitionToYaml(document));
  }

  async function importBundle(dryRun: boolean) {
    const result = await api<{ results?: { action?: string; key?: string }[] }>(
      "/api/v1/bundles:import",
      {
        method: "POST",
        body: JSON.stringify({ yamlText: importText, dryRun }),
      },
    );
    const line = (result.results ?? [])
      .map((item) => `${item.key ?? "agent"} ${item.action}`)
      .join(", ");
    setImportResult(line || t("importEmpty"));
  }

  if (loading) {
    return <p className="text-sm text-[var(--muted-foreground)]">{t("loading")}</p>;
  }
  if (error && !agent) {
    return (
      <p className="text-sm text-[var(--destructive)]" role="alert">
        {error}
      </p>
    );
  }

  return (
    <div>
      <PageHeader
        body={agent?.description || t("editorBody")}
        title={agent?.name || t("editorTitle")}
      />
      {error ? (
        <p className="mb-3 text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      <label className="block text-sm font-medium" htmlFor="instructions">
        {t("instructions")}
      </label>
      <textarea
        className="mt-2 min-h-32 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
        id="instructions"
        onChange={(event) => updateDefinition({ ...definition, instructions: event.target.value })}
        value={definition.instructions ?? ""}
      />
      <MemoryReview agentId={agentId} />
      <div className="mt-3">
        <Button onClick={() => setAdvanced((current) => !current)} type="button" variant="outline">
          {advanced ? t("hideAdvanced") : t("showAdvanced")}
        </Button>
      </div>
      {advanced ? (
        <div className="mt-4">
          <div className="flex flex-wrap gap-2" role="tablist">
            {ADVANCED.map((item) => (
              <button
                aria-selected={tab === item}
                className="rounded-md px-3 py-1 text-sm"
                key={item}
                onClick={() => setTab(item)}
                role="tab"
                type="button"
              >
                {t(`tab_${item}`)}
              </button>
            ))}
          </div>
          {tab === "instructions" ? (
            <p className="mt-3 text-sm text-[var(--muted-foreground)]">
              {t("tabInstructionsHelp")}
            </p>
          ) : null}
          {tab === "model" ? (
            <div className="mt-3">
              <label className="block text-sm" htmlFor="model-alias">
                {t("modelAlias")}
              </label>
              <Input
                className="mt-1 max-w-xs"
                id="model-alias"
                onChange={(event) =>
                  updateDefinition({
                    ...definition,
                    model: { ...definition.model, alias: event.target.value },
                  })
                }
                value={definition.model?.alias ?? "reasoning"}
              />
            </div>
          ) : null}
          {tab === "tools" ? (
            <p className="mt-3 text-sm">
              {(definition.tools ?? []).map((tool) => tool.server).join(", ") || t("noTools")}
            </p>
          ) : null}
          {tab === "knowledge" ? <p className="mt-3 text-sm">{t("knowledgeDefault")}</p> : null}
          {tab === "yaml" ? (
            <textarea
              aria-label={t("yaml")}
              className="mt-3 min-h-48 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 font-mono text-sm"
              onChange={(event) => applyYaml(event.target.value)}
              value={yaml}
            />
          ) : null}
          {yamlError ? <p className="mt-2 text-sm text-[var(--destructive)]">{yamlError}</p> : null}
        </div>
      ) : null}
      <section className="mt-6 rounded-xl border border-[var(--border)] p-4">
        <h2 className="text-sm font-medium">{t("publish")}</h2>
        <Input
          aria-label={t("changeNote")}
          className="mt-2 max-w-md"
          onChange={(event) => setNote(event.target.value)}
          placeholder={t("changeNote")}
          value={note}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <Button disabled={busy} onClick={() => void validate()} type="button" variant="outline">
            {t("validate")}
          </Button>
          <Button disabled={busy} onClick={() => void publish()} type="button">
            {t("publish")}
          </Button>
        </div>
        {report ? (
          <section aria-label={t("validation")} className="mt-3 text-sm">
            <p>{report.valid ? t("valid") : t("invalid")}</p>
            {(report.warnings ?? []).map((item) => (
              <p key={item.msg}>{item.msg}</p>
            ))}
            {(report.errors ?? []).map((item) => (
              <p key={item.msg}>{item.msg}</p>
            ))}
          </section>
        ) : null}
      </section>
      <section className="mt-4">
        <h2 className="text-sm font-medium">{t("versions")}</h2>
        <ul className="mt-2 space-y-2">
          {versions.map((row) => (
            <li className="flex items-center gap-2 text-sm" key={row.version}>
              <span>
                v{row.version} {row.state}
              </span>
              {row.state !== "draft" ? (
                <Button onClick={() => void rollback(row.version)} type="button" variant="ghost">
                  {t("rollback")}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
      <section className="mt-4 rounded-xl border border-[var(--border)] p-4">
        <h2 className="text-sm font-medium">{t("testChat")}</h2>
        <textarea
          aria-label={t("testMessage")}
          className="mt-2 min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
          onChange={(event) => setChatText(event.target.value)}
          value={chatText}
        />
        <Button
          className="mt-2"
          disabled={busy || !chatText.trim()}
          onClick={() => void testChat()}
          type="button"
        >
          {t("sendTest")}
        </Button>
        {chatReply ? <p className="mt-3 text-sm">{chatReply}</p> : null}
      </section>
      <section className="mt-4 flex flex-wrap gap-2">
        <Button onClick={() => void exportBundle()} type="button" variant="outline">
          {t("exportBundle")}
        </Button>
      </section>
      {bundle ? (
        <pre className="mt-3 overflow-auto rounded-lg bg-[var(--muted)] p-3 text-xs">{bundle}</pre>
      ) : null}
      <section className="mt-4">
        <label className="text-sm font-medium" htmlFor="import-bundle">
          {t("importBundle")}
        </label>
        <textarea
          className="mt-2 min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 font-mono text-xs"
          id="import-bundle"
          onChange={(event) => setImportText(event.target.value)}
          value={importText}
        />
        <div className="mt-2 flex gap-2">
          <Button onClick={() => void importBundle(true)} type="button" variant="outline">
            {t("dryRun")}
          </Button>
          <Button onClick={() => void importBundle(false)} type="button">
            {t("importApply")}
          </Button>
        </div>
        {importResult ? <p className="mt-2 text-sm">{importResult}</p> : null}
      </section>
    </div>
  );
}
