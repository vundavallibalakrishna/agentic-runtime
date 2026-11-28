"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ActionStatus, BackButton } from "@/components/common/detail-state";
import { ReferencePicker } from "@/components/common/reference-picker";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { chatAliases } from "@/lib/model-aliases";

import type { Definition } from "./types";

const TEMPLATES = ["blank", "assistant", "researcher", "analyst", "support"] as const;
const GENERAL_TOOLS = [
  "code",
  "shell",
  "read_file",
  "write_file",
  "list_files",
  "fetch",
  "search",
  "http",
  "inspect_table",
  "query_table",
  "sample_table",
  "save_query",
  "list_saved_queries",
  "run_saved_query",
  "export_table",
  "chart",
] as const;
const DATA_TOOLS = ["list_schemas", "list_tables", "describe_table", "query"] as const;

type Proposal = {
  resources?: { spec?: Definition; metadata?: { name?: string } }[];
};

type SessionView = {
  proposal?: Proposal;
  validation?: { errors?: { msg?: string }[]; warnings?: { msg?: string }[] };
};

export function BuilderScreen() {
  const t = useTranslations("agents");
  const detail = useTranslations("detail");
  const router = useRouter();
  const [instruction, setInstruction] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [view, setView] = useState<SessionView | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [formName, setFormName] = useState("");
  const [formInstructions, setFormInstructions] = useState("");
  const [formModel, setFormModel] = useState("");
  const [modelsLoading, setModelsLoading] = useState(true);
  const [aliases, setAliases] = useState<string[]>([]);
  const aliasChoices = useMemo(
    () => aliases.map((alias) => ({ id: alias, name: alias })),
    [aliases],
  );
  const [enabledTools, setEnabledTools] = useState<string[]>([...GENERAL_TOOLS]);
  const [dataTools, setDataTools] = useState<string[]>([]);
  const [rowLimit, setRowLimit] = useState(1000);
  const [toolTimeout, setToolTimeout] = useState(30);
  const [toolNetwork, setToolNetwork] = useState(false);

  const loadModels = useCallback(async () => {
    setModelsLoading(true);
    const available = await chatAliases();
    setAliases(available);
    setFormModel((current) => (available.includes(current) ? current : (available[0] ?? "")));
    setModelsLoading(false);
  }, []);
  useEffect(() => {
    void loadModels();
  }, [loadModels]);

  const spec = view?.proposal?.resources?.[0]?.spec;

  async function draft() {
    if (busy || instruction.trim().length < 8) return;
    setView(null);
    setSessionId("");
    setBusy(true);
    setError("");
    try {
      const started = await api<{ sessionId: string }>("/api/v1/builder/sessions", {
        method: "POST",
        body: JSON.stringify({ instruction }),
      });
      setSessionId(started.sessionId);
      setView(await api<SessionView>(`/api/v1/builder/sessions/${started.sessionId}`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function revise() {
    if (busy || !sessionId || !followUp.trim()) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/builder/sessions/${sessionId}/messages`, {
        method: "POST",
        body: JSON.stringify({ text: followUp }),
      });
      setView(await api<SessionView>(`/api/v1/builder/sessions/${sessionId}`));
      setFollowUp("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    if (busy || !sessionId || !spec || view?.validation?.errors?.length) return;
    setBusy(true);
    setError("");
    try {
      const applied = await api<{ agentId: string }>(
        `/api/v1/builder/sessions/${sessionId}:apply`,
        {
          method: "POST",
          body: JSON.stringify({ mode: "create" }),
        },
      );
      router.push(`/agents/${applied.agentId}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
      setBusy(false);
    }
  }

  async function createDirect() {
    if (
      busy ||
      formName.trim().length < 2 ||
      formInstructions.trim().length < 8 ||
      !aliases.includes(formModel) ||
      !Number.isInteger(toolTimeout) ||
      toolTimeout < 1 ||
      toolTimeout > 120 ||
      !Number.isInteger(rowLimit) ||
      rowLimit < 1 ||
      rowLimit > 5000
    )
      return;
    setBusy(true);
    setError("");
    const slug = `${formName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 40)}-${Date.now().toString(36)}`.replace(/--+/g, "-");
    try {
      const created = await api<{ id: string; slug?: string }>("/api/v1/agents", {
        method: "POST",
        body: JSON.stringify({
          slug: slug.slice(0, 63),
          name: formName.trim(),
          visibility: "private",
          definition: {
            instructions: formInstructions.trim(),
            model: { alias: formModel },
            tools: [
              { server: "session", version: "*", include: ["plan_update", "search"] },
              ...(enabledTools.length
                ? [
                    {
                      server: "general",
                      version: "*",
                      include: enabledTools,
                      overrides: {
                        code: { timeoutS: toolTimeout, network: toolNetwork },
                        shell: { timeoutS: toolTimeout, network: toolNetwork },
                      },
                    },
                  ]
                : []),
              ...(dataTools.length
                ? [
                    {
                      server: "data",
                      version: "*",
                      include: dataTools,
                      overrides: { query: { rowLimit } },
                    },
                  ]
                : []),
            ],
            budget: {
              maxSteps: 16,
              maxToolCalls: 16,
              maxWallClockS: 600,
              maxCostMicros: 4_000_000,
              maxTokens: 80_000,
            },
          },
        }),
      });
      router.push(`/agents/${created.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
      setBusy(false);
    }
  }

  async function fromTemplate(template: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    const slug = `${template}-${Date.now().toString(36)}`.slice(0, 40);
    try {
      const created = await api<{ id: string }>("/api/v1/agents", {
        method: "POST",
        body: JSON.stringify({
          slug,
          name: template[0]?.toUpperCase() + template.slice(1),
          template,
          visibility: "private",
        }),
      });
      router.push(`/agents/${created.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        body={t("builderBody")}
        title={t("builderTitle")}
        actions={<BackButton href="/agents">{detail("back")}</BackButton>}
      />
      <ActionStatus busy={busy} />
      <fieldset
        disabled={busy}
        className="grid min-w-0 items-start gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]"
      >
        <div className="min-w-0 space-y-6">
          <section className="detail-panel">
            <label className="block text-sm font-medium" htmlFor="instruction">
              {t("instruction")}
            </label>
            <textarea
              className="mt-2 min-h-28 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
              id="instruction"
              onChange={(event) => setInstruction(event.target.value)}
              placeholder={t("instructionPlaceholder")}
              value={instruction}
            />
            <Button
              className="mt-3"
              disabled={busy || instruction.trim().length < 8}
              onClick={() => void draft()}
              type="button"
            >
              {t("draft")}
            </Button>
          </section>
          {error ? (
            <p className="mt-3 text-sm text-[var(--destructive)]" role="alert">
              {error}
            </p>
          ) : null}
          {spec ? (
            <section className="detail-panel">
              <h2 className="text-base font-semibold">{t("preview")}</h2>
              <p className="mt-2 text-sm">
                {t("persona")}: {spec.persona?.displayName}
              </p>
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                {spec.persona?.greeting}
              </p>
              <p className="mt-3 text-sm">{spec.instructions}</p>
              <ul aria-label={t("toolsAndConnectors")} className="mt-3 flex flex-wrap gap-1.5">
                {(spec.tools ?? []).map((tool) => (
                  <li key={tool.server}>
                    <Badge>
                      {t("toolSlot")}: {tool.server}
                    </Badge>
                  </li>
                ))}
              </ul>
              <section aria-label={t("validation")} className="mt-3">
                <p className="text-sm font-medium">{t("validation")}</p>
                {(view?.validation?.warnings ?? []).map((item) => (
                  <p className="text-sm text-[var(--muted-foreground)]" key={item.msg}>
                    {item.msg}
                  </p>
                ))}
                {(view?.validation?.errors ?? []).map((item) => (
                  <p className="text-sm text-[var(--destructive)]" key={item.msg}>
                    {item.msg}
                  </p>
                ))}
                {(view?.validation?.errors ?? []).length === 0 ? (
                  <p className="text-sm">{t("noErrors")}</p>
                ) : null}
              </section>
              <label className="mt-4 block text-sm font-medium" htmlFor="follow-up">
                {t("followUp")}
              </label>
              <textarea
                className="mt-2 min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-sm"
                id="follow-up"
                onChange={(event) => setFollowUp(event.target.value)}
                value={followUp}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  disabled={busy || !followUp.trim()}
                  onClick={() => void revise()}
                  type="button"
                  variant="outline"
                >
                  {t("updateDraft")}
                </Button>
                <Button
                  disabled={busy || !!error || !!view?.validation?.errors?.length}
                  onClick={() => void apply()}
                  type="button"
                >
                  {t("apply")}
                </Button>
              </div>
            </section>
          ) : null}
          <section className="detail-panel">
            <h2 className="text-sm font-semibold">{t("templates")}</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              {TEMPLATES.map((template) => (
                <Button
                  key={template}
                  onClick={() => void fromTemplate(template)}
                  type="button"
                  variant="outline"
                >
                  {template === "blank"
                    ? t("template_blank")
                    : template === "assistant"
                      ? t("template_assistant")
                      : template === "researcher"
                        ? t("template_researcher")
                        : template === "analyst"
                          ? t("template_analyst")
                          : t("template_support")}
                </Button>
              ))}
            </div>
          </section>
        </div>
        <details className="detail-panel form-sections">
          <summary className="cursor-pointer text-base font-semibold">{t("createForm")}</summary>
          <p className="mt-3 text-sm text-[var(--muted-foreground)]">{t("createFormHelp")}</p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void createDirect();
            }}
          >
            <label className="mt-3 block text-sm font-medium" htmlFor="agent-form-name">
              {t("name")}
            </label>
            <input
              className="mt-1 w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
              id="agent-form-name"
              required
              minLength={2}
              onChange={(event) => setFormName(event.target.value)}
              value={formName}
            />
            <label className="mt-3 block text-sm font-medium" htmlFor="agent-form-instructions">
              {t("instructions")}
            </label>
            <textarea
              className="mt-1 min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
              id="agent-form-instructions"
              required
              minLength={8}
              onChange={(event) => setFormInstructions(event.target.value)}
              value={formInstructions}
            />
            <div className="mt-3">
              <ReferencePicker
                label={t("modelAlias")}
                items={aliasChoices}
                getDescription={() => ""}
                required
                clearable={false}
                disabled={busy || modelsLoading || aliases.length === 0}
                onChange={setFormModel}
                value={formModel}
              />
            </div>
            {modelsLoading ? (
              <p className="mt-2 text-sm" role="status">
                {t("loadingModels")}
              </p>
            ) : aliases.length === 0 ? (
              <p className="mt-2 text-sm text-[var(--muted-foreground)]" role="status">
                {t("noCreateModels")}{" "}
                <Button type="button" variant="ghost" onClick={() => void loadModels()}>
                  {t("retry")}
                </Button>
              </p>
            ) : null}
            <details className="mt-4 rounded-lg border border-[var(--border)]">
              <summary className="cursor-pointer px-3 py-3 text-sm font-medium">
                {t("generalTools")} · {t("selectedTools", { count: enabledTools.length })}
              </summary>
              <fieldset className="min-w-0 p-3 pt-0">
                <legend className="sr-only">{t("generalTools")}</legend>
                <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("generalHelp")}</p>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {GENERAL_TOOLS.map((name) => (
                    <label className="flex items-center gap-2 text-sm" key={name}>
                      <input
                        checked={enabledTools.includes(name)}
                        onChange={() =>
                          setEnabledTools((current) =>
                            current.includes(name)
                              ? current.filter((item) => item !== name)
                              : [...current, name],
                          )
                        }
                        type="checkbox"
                      />
                      {t(`tool_${name}`)}
                    </label>
                  ))}
                </div>
                <label className="mt-3 block text-sm" htmlFor="create-timeout">
                  {t("toolTimeout")}
                  <input
                    className="mt-1 block w-full max-w-xs rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
                    id="create-timeout"
                    min={1}
                    max={120}
                    onChange={(event) => setToolTimeout(Number(event.target.value) || 30)}
                    type="number"
                    value={toolTimeout}
                  />
                </label>
                <label className="mt-3 flex items-center gap-2 text-sm" htmlFor="create-network">
                  <input
                    checked={toolNetwork}
                    id="create-network"
                    onChange={(event) => setToolNetwork(event.target.checked)}
                    type="checkbox"
                  />
                  {t("toolNetwork")}
                </label>
              </fieldset>
            </details>
            <details className="mt-4 rounded-lg border border-[var(--border)]">
              <summary className="cursor-pointer px-3 py-3 text-sm font-medium">
                {t("dataTools")} · {t("selectedTools", { count: dataTools.length })}
              </summary>
              <fieldset className="min-w-0 p-3 pt-0">
                <legend className="sr-only">{t("dataTools")}</legend>
                <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("dataHelp")}</p>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {DATA_TOOLS.map((name) => (
                    <label className="flex items-center gap-2 text-sm" key={name}>
                      <input
                        checked={dataTools.includes(name)}
                        onChange={() =>
                          setDataTools((current) =>
                            current.includes(name)
                              ? current.filter((item) => item !== name)
                              : [...current, name],
                          )
                        }
                        type="checkbox"
                      />
                      {t(`tool_${name}`)}
                    </label>
                  ))}
                </div>
                <label className="mt-3 block text-sm" htmlFor="create-row-limit">
                  {t("rowLimit")}
                  <input
                    className="mt-1 block w-full max-w-xs rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
                    id="create-row-limit"
                    max={5000}
                    min={1}
                    onChange={(event) => setRowLimit(Number(event.target.value) || 1000)}
                    type="number"
                    value={rowLimit}
                  />
                </label>
              </fieldset>
            </details>
            <Button
              className="mt-3"
              disabled={
                busy ||
                modelsLoading ||
                !aliases.includes(formModel) ||
                formName.trim().length < 2 ||
                formInstructions.trim().length < 8
              }
              type="submit"
            >
              {t("createDraft")}
            </Button>
          </form>
        </details>
      </fieldset>
    </div>
  );
}
