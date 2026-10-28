"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { MemoryReview } from "@/components/agent-builder/MemoryReview";
import { ActionStatus, BackButton, DetailState } from "@/components/common/detail-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { definitionToYaml, type JsonValue, yamlToDefinition } from "@/lib/agent-yaml";
import { api } from "@/lib/api";

import type { AgentDetail, Definition, ValidationReport } from "./types";

const ADVANCED = [
  "instructions",
  "model",
  "tools",
  "knowledge",
  "skills",
  "subagents",
  "yaml",
] as const;

export function AgentEditor() {
  const t = useTranslations("agents");
  const detail = useTranslations("detail");
  const [notice, setNotice] = useState("");
  const params = useParams<{ id: string }>();
  const agentId = params.id;
  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [definition, setDefinition] = useState<Definition>({});
  const [yaml, setYaml] = useState("");
  const [yamlError, setYamlError] = useState("");
  const [advanced, setAdvanced] = useState(false);
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
  const [name, setName] = useState("");
  const [servers, setServers] = useState<{ slug: string; name: string }[]>([]);
  const [aliases, setAliases] = useState<string[]>([]);

  const load = useCallback(async () => {
    setAgent(null);
    setLoading(true);
    setError("");
    try {
      const body = await api<AgentDetail>(`/api/v1/agents/${agentId}`);
      const source = body.draft?.definition ?? body.published?.definition ?? {};
      const history = await api<{ items: { version: number; state: string }[] }>(
        `/api/v1/agents/${agentId}/versions`,
      );
      setAgent(body);
      setName(body.name ?? "");
      setDefinition(source);
      setYaml(definitionToYaml(source as JsonValue));
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

  useEffect(() => {
    void api<{ items?: { slug?: string; name?: string }[] }>("/api/v1/tool-servers")
      .then((page) =>
        setServers(
          (page.items ?? [])
            .map((row) => ({
              slug: String(row.slug ?? ""),
              name: String(row.name ?? row.slug ?? ""),
            }))
            .filter((row) => row.slug),
        ),
      )
      .catch(() => setServers([]));
    void api<{ items?: { alias?: string }[] }>("/api/v1/model-aliases")
      .then((page) =>
        setAliases((page.items ?? []).map((row) => String(row.alias ?? "")).filter(Boolean)),
      )
      .catch(() => setAliases([]));
  }, []);

  function budgetValue(key: keyof NonNullable<Definition["budget"]>, fallback: number) {
    return definition.budget?.[key] ?? fallback;
  }

  function setBudget(key: keyof NonNullable<Definition["budget"]>, value: number) {
    updateDefinition({
      ...definition,
      budget: { ...definition.budget, [key]: value },
    });
  }

  function toggleServer(slug: string) {
    const current = definition.tools ?? [];
    const exists = current.some((tool) => tool.server === slug);
    updateDefinition({
      ...definition,
      tools: exists
        ? current.filter((tool) => tool.server !== slug)
        : [...current, { server: slug, version: "*", include: ["*"] }],
    });
  }

  const generalTools = [
    "code",
    "shell",
    "read_file",
    "write_file",
    "list_files",
    "fetch",
    "search",
    "http",
  ] as const;
  const general = (definition.tools ?? []).find((tool) => tool.server === "general");
  const generalInclude = general?.include ?? [];

  function setGeneral(include: string[], overrides = general?.overrides) {
    const rest = (definition.tools ?? []).filter((tool) => tool.server !== "general");
    updateDefinition({
      ...definition,
      tools:
        include.length === 0
          ? rest
          : [...rest, { server: "general", version: "*", include, overrides }],
    });
  }

  function toggleGeneral(name: string) {
    const selected = new Set(generalInclude.filter((item) => item !== "*"));
    if (generalInclude.includes("*") || generalInclude.includes(name)) {
      if (generalInclude.includes("*")) {
        for (const item of generalTools) selected.add(item);
      }
      selected.delete(name);
    } else {
      selected.add(name);
    }
    setGeneral([...selected]);
  }

  function updateDefinition(next: Definition) {
    setReport(null);
    setDefinition(next);
    setYaml(definitionToYaml(next as JsonValue));
    setYamlError("");
  }

  function applyYaml(text: string) {
    setReport(null);
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

  async function persistDraft() {
    if (yamlError) throw new Error(yamlError);
    await api(`/api/v1/agents/${agentId}/versions/draft`, {
      method: "PUT",
      body: JSON.stringify({ definition, changeNote: note }),
    });
  }

  async function save() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await persistDraft();
      await api(`/api/v1/agents/${agentId}`, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      setNotice(detail("saved"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function validate() {
    setBusy(true);
    try {
      await persistDraft();
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
      await persistDraft();
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
      await persistDraft();
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
    setBusy(true);
    setError("");
    try {
      const document = await api<JsonValue>(`/api/v1/bundles:export?ids=${agentId}`, {
        headers: { accept: "application/json" },
      });
      setBundle(definitionToYaml(document));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function importBundle(dryRun: boolean) {
    setBusy(true);
    setError("");
    try {
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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        actions={
          <>
            <Link className="text-sm underline" href={`/chat?agent=${agent?.slug ?? ""}`}>
              {t("useInChat")}
            </Link>
            <Link className="text-sm underline" href={`/agents/${agentId}/evals`}>
              {t("evals")}
            </Link>
            <BackButton href="/agents">{detail("back")}</BackButton>
          </>
        }
        body={agent?.description || t("editorBody")}
        title={agent?.name || t("editorTitle")}
      />
      <DetailState
        loading={loading}
        error={error}
        onRetry={agent ? undefined : () => void load()}
      />
      <ActionStatus busy={busy} notice={notice} />
      {!loading && agent ? (
        <fieldset disabled={busy || agent.canEdit === false} className="min-w-0 space-y-6">
          <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
            <div className="min-w-0 space-y-6">
              <section className="detail-panel">
                <label className="block text-sm font-medium" htmlFor="instructions">
                  {t("instructions")}
                </label>
                <textarea
                  className="mt-2 min-h-48 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                  id="instructions"
                  onChange={(event) =>
                    updateDefinition({ ...definition, instructions: event.target.value })
                  }
                  value={definition.instructions ?? ""}
                />
                <label className="mt-4 block text-sm font-medium" htmlFor="agent-name">
                  {t("name")}
                </label>
                <Input
                  className="mt-1 max-w-md"
                  id="agent-name"
                  onChange={(event) => setName(event.target.value)}
                  value={name}
                />
                <label className="mt-4 block text-sm font-medium" htmlFor="editor-model">
                  {t("modelAlias")}
                </label>
                <select
                  className="mt-1 w-full max-w-xs rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-2 text-sm"
                  id="editor-model"
                  onChange={(event) =>
                    updateDefinition({
                      ...definition,
                      model: { ...definition.model, alias: event.target.value },
                    })
                  }
                  value={definition.model?.alias ?? "reasoning"}
                >
                  <option value="reasoning">reasoning</option>
                  {aliases
                    .filter((alias) => alias !== "reasoning")
                    .map((alias) => (
                      <option key={alias} value={alias}>
                        {alias}
                      </option>
                    ))}
                </select>
                <fieldset className="mt-4">
                  <legend className="text-sm font-medium">{t("toolsAndConnectors")}</legend>
                  {servers.length === 0 ? (
                    <p className="mt-2 text-sm text-[var(--muted-foreground)]">{t("noTools")}</p>
                  ) : (
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      {servers.map((server) => (
                        <label className="flex items-center gap-2 text-sm" key={server.slug}>
                          <input
                            checked={(definition.tools ?? []).some(
                              (tool) => tool.server === server.slug,
                            )}
                            onChange={() => toggleServer(server.slug)}
                            type="checkbox"
                          />
                          {server.name}
                        </label>
                      ))}
                    </div>
                  )}
                </fieldset>
                <fieldset className="mt-4">
                  <legend className="text-sm font-medium">{t("generalTools")}</legend>
                  <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("generalHelp")}</p>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    {generalTools.map((name) => (
                      <label className="flex items-center gap-2 text-sm" key={name}>
                        <input
                          checked={generalInclude.includes("*") || generalInclude.includes(name)}
                          onChange={() => toggleGeneral(name)}
                          type="checkbox"
                        />
                        {t(`tool_${name}`)}
                      </label>
                    ))}
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <label className="block text-sm" htmlFor="general-timeout">
                      {t("toolTimeout")}
                      <Input
                        className="mt-1"
                        id="general-timeout"
                        min={1}
                        max={120}
                        onChange={(event) => {
                          const timeoutS = Number(event.target.value) || 30;
                          const include = generalInclude.length ? generalInclude : ["code"];
                          setGeneral(include.includes("*") ? [...generalTools] : include, {
                            ...general?.overrides,
                            code: { ...general?.overrides?.code, timeoutS },
                            shell: { ...general?.overrides?.shell, timeoutS },
                          });
                        }}
                        type="number"
                        value={general?.overrides?.code?.timeoutS ?? 30}
                      />
                    </label>
                    <label
                      className="mt-6 flex items-center gap-2 text-sm"
                      htmlFor="general-network"
                    >
                      <input
                        checked={general?.overrides?.code?.network === true}
                        id="general-network"
                        onChange={(event) => {
                          const include = generalInclude.length
                            ? generalInclude
                            : ["code", "shell"];
                          setGeneral(include.includes("*") ? [...generalTools] : include, {
                            ...general?.overrides,
                            code: { ...general?.overrides?.code, network: event.target.checked },
                            shell: { ...general?.overrides?.shell, network: event.target.checked },
                          });
                        }}
                        type="checkbox"
                      />
                      {t("toolNetwork")}
                    </label>
                  </div>
                  <label className="mt-3 block text-sm" htmlFor="general-hosts">
                    {t("allowHosts")}
                    <textarea
                      className="mt-1 min-h-16 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                      id="general-hosts"
                      onChange={(event) => {
                        const allowHosts = event.target.value
                          .split("\n")
                          .map((item) => item.trim())
                          .filter(Boolean);
                        const include = generalInclude.length ? generalInclude : ["fetch", "http"];
                        setGeneral(include.includes("*") ? [...generalTools] : include, {
                          ...general?.overrides,
                          fetch: { ...general?.overrides?.fetch, allowHosts },
                          http: { ...general?.overrides?.http, allowHosts },
                        });
                      }}
                      value={(general?.overrides?.fetch?.allowHosts ?? []).join("\n")}
                    />
                  </label>
                </fieldset>
                <label className="mt-4 block text-sm font-medium" htmlFor="editor-skills">
                  {t("skillSlugs")}
                </label>
                <textarea
                  className="mt-1 min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                  id="editor-skills"
                  onChange={(event) =>
                    updateDefinition({
                      ...definition,
                      skills: event.target.value
                        .split("\n")
                        .map((item) => item.trim())
                        .filter(Boolean),
                    })
                  }
                  value={(definition.skills ?? []).join("\n")}
                />
                <fieldset className="mt-4">
                  <legend className="text-sm font-medium">{t("limits")}</legend>
                  <div className="mt-2 grid gap-3 sm:grid-cols-2">
                    {(
                      [
                        ["maxSteps", t("maxSteps"), 8],
                        ["maxToolCalls", t("maxToolCalls"), 8],
                        ["maxWallClockS", t("maxWallClock"), 120],
                        ["maxCostMicros", t("maxCost"), 1_000_000],
                      ] as const
                    ).map(([key, label, fallback]) => (
                      <label className="block text-sm" htmlFor={`limit-${key}`} key={key}>
                        {label}
                        <Input
                          className="mt-1"
                          id={`limit-${key}`}
                          min={0}
                          onChange={(event) => setBudget(key, Number(event.target.value) || 0)}
                          type="number"
                          value={budgetValue(key, fallback)}
                        />
                      </label>
                    ))}
                  </div>
                </fieldset>
              </section>
              <div className="mt-3">
                <Button
                  onClick={() => setAdvanced((current) => !current)}
                  type="button"
                  variant="outline"
                >
                  {advanced ? t("hideAdvanced") : t("showAdvanced")}
                </Button>
              </div>
              {advanced ? (
                <Tabs defaultValue="instructions">
                  <TabsList>
                    {ADVANCED.map((item) => (
                      <TabsTrigger key={item} value={item}>
                        {t(`tab_${item}`)}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                  <TabsContent value="instructions">
                    <p className="mt-3 text-sm text-[var(--muted-foreground)]">
                      {t("tabInstructionsHelp")}
                    </p>
                  </TabsContent>
                  <TabsContent value="model">
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
                  </TabsContent>
                  <TabsContent value="tools">
                    <p className="mt-3 text-sm">
                      {(definition.tools ?? []).map((tool) => tool.server).join(", ") ||
                        t("noTools")}
                    </p>
                  </TabsContent>
                  <TabsContent value="knowledge">
                    <p className="mt-3 text-sm">{t("knowledgeDefault")}</p>
                  </TabsContent>
                  <TabsContent value="skills">
                    <div className="mt-3">
                      <label className="block text-sm" htmlFor="skill-slugs">
                        {t("skillSlugs")}
                      </label>
                      <textarea
                        className="mt-1 min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                        id="skill-slugs"
                        onChange={(event) =>
                          updateDefinition({
                            ...definition,
                            skills: event.target.value
                              .split("\n")
                              .map((item) => item.trim())
                              .filter(Boolean),
                          })
                        }
                        value={(definition.skills ?? []).join("\n")}
                      />
                      <p className="mt-2 text-sm text-[var(--muted-foreground)]">
                        {t("skillsHelp")}
                      </p>
                    </div>
                  </TabsContent>
                  <TabsContent value="subagents">
                    <div className="mt-3">
                      <label className="block text-sm" htmlFor="subagent-slugs">
                        {t("subagentSlugs")}
                      </label>
                      <textarea
                        className="mt-1 min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                        id="subagent-slugs"
                        onChange={(event) =>
                          updateDefinition({
                            ...definition,
                            subagents: {
                              ...definition.subagents,
                              allowed: event.target.value
                                .split("\n")
                                .map((item) => item.trim())
                                .filter(Boolean),
                            },
                          })
                        }
                        value={(definition.subagents?.allowed ?? []).join("\n")}
                      />
                      <div className="mt-3 flex gap-3">
                        <label className="text-sm" htmlFor="max-depth">
                          {t("maxDepth")}
                          <Input
                            className="mt-1 w-24"
                            id="max-depth"
                            min={1}
                            max={3}
                            onChange={(event) =>
                              updateDefinition({
                                ...definition,
                                subagents: {
                                  ...definition.subagents,
                                  maxDepth: Number(event.target.value) || 1,
                                },
                              })
                            }
                            type="number"
                            value={definition.subagents?.maxDepth ?? 1}
                          />
                        </label>
                        <label className="text-sm" htmlFor="max-parallel">
                          {t("maxParallel")}
                          <Input
                            className="mt-1 w-24"
                            id="max-parallel"
                            min={1}
                            onChange={(event) =>
                              updateDefinition({
                                ...definition,
                                subagents: {
                                  ...definition.subagents,
                                  maxParallel: Number(event.target.value) || 1,
                                },
                              })
                            }
                            type="number"
                            value={definition.subagents?.maxParallel ?? 1}
                          />
                        </label>
                      </div>
                      <p className="mt-2 text-sm text-[var(--muted-foreground)]">
                        {t("subagentsHelp")}
                      </p>
                    </div>
                  </TabsContent>
                  <TabsContent value="yaml">
                    <textarea
                      aria-label={t("yaml")}
                      className="mt-3 min-h-48 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 font-mono text-sm"
                      onChange={(event) => applyYaml(event.target.value)}
                      value={yaml}
                    />
                  </TabsContent>
                  {yamlError ? (
                    <p className="mt-2 text-sm text-[var(--destructive)]">{yamlError}</p>
                  ) : null}
                </Tabs>
              ) : null}
              <MemoryReview agentId={agentId} />
            </div>
            <div className="min-w-0 space-y-6 [&>.detail-panel]:p-5">
              <section className="detail-panel">
                <h2 className="text-sm font-medium">{t("publish")}</h2>
                <Input
                  aria-label={t("changeNote")}
                  className="mt-2 max-w-md"
                  onChange={(event) => setNote(event.target.value)}
                  placeholder={t("changeNote")}
                  value={note}
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    disabled={busy || !!yamlError}
                    onClick={() => void save()}
                    type="button"
                    variant="outline"
                  >
                    {t("save")}
                  </Button>
                  <Button
                    disabled={busy || !!yamlError}
                    onClick={() => void validate()}
                    type="button"
                    variant="outline"
                  >
                    {t("validate")}
                  </Button>
                  <Button
                    disabled={busy || !!yamlError}
                    onClick={() => void publish()}
                    type="button"
                  >
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
              <section className="detail-panel">
                <h2 className="text-sm font-medium">{t("versions")}</h2>
                <ul className="mt-2 space-y-2">
                  {versions.map((row) => (
                    <li className="flex items-center gap-2 text-sm" key={row.version}>
                      <span>
                        v{row.version} {row.state}
                      </span>
                      {row.state !== "draft" ? (
                        <Button
                          onClick={() => void rollback(row.version)}
                          type="button"
                          variant="ghost"
                        >
                          {t("rollback")}
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </section>
              <section className="detail-panel">
                <h2 className="text-sm font-medium">{t("testChat")}</h2>
                <textarea
                  aria-label={t("testMessage")}
                  className="mt-2 min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                  onChange={(event) => setChatText(event.target.value)}
                  value={chatText}
                />
                <Button
                  className="mt-2"
                  disabled={busy || !!yamlError || !chatText.trim()}
                  onClick={() => void testChat()}
                  type="button"
                >
                  {t("sendTest")}
                </Button>
                {chatReply ? <p className="mt-3 text-sm">{chatReply}</p> : null}
              </section>
            </div>
          </div>
          <section className="mt-4 flex flex-wrap gap-2">
            <Button onClick={() => void exportBundle()} type="button" variant="outline">
              {t("exportBundle")}
            </Button>
          </section>
          {bundle ? (
            <pre className="mt-3 overflow-auto rounded-lg bg-[var(--muted)] p-3 text-xs">
              {bundle}
            </pre>
          ) : null}
          <section className="detail-panel">
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
              <Button
                disabled={!importText.trim()}
                onClick={() => void importBundle(true)}
                type="button"
                variant="outline"
              >
                {t("dryRun")}
              </Button>
              <Button
                disabled={!importText.trim()}
                onClick={() => void importBundle(false)}
                type="button"
              >
                {t("importApply")}
              </Button>
            </div>
            {importResult ? <p className="mt-2 text-sm">{importResult}</p> : null}
          </section>
        </fieldset>
      ) : null}
    </div>
  );
}
