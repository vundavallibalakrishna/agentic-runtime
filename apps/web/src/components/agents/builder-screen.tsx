"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { ActionStatus, BackButton } from "@/components/common/detail-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

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
] as const;

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
  const [formModel, setFormModel] = useState("reasoning");
  const [enabledTools, setEnabledTools] = useState<string[]>([...GENERAL_TOOLS]);
  const [toolTimeout, setToolTimeout] = useState(30);
  const [toolNetwork, setToolNetwork] = useState(false);

  const spec = view?.proposal?.resources?.[0]?.spec;

  async function draft() {
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
    if (!sessionId || !followUp.trim()) {
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
              { server: "control", version: "*", include: ["plan_update", "search", "checkpoint"] },
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
            ],
            budget: {
              maxSteps: 8,
              maxToolCalls: 8,
              maxWallClockS: 120,
              maxCostMicros: 1_000_000,
              maxTokens: 16000,
            },
          },
        }),
      });
      await api(`/api/v1/agents/${created.id}:publish`, {
        method: "POST",
        body: JSON.stringify({ changeNote: t("publishedNote"), skipEvalGate: true }),
      });
      router.push(`/chat?agent=${slug.slice(0, 63)}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
      setBusy(false);
    }
  }

  async function fromTemplate(template: string) {
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
      <fieldset disabled={busy} className="min-w-0">
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
          <section className="mt-6 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h2 className="text-base font-medium">{t("preview")}</h2>
            <p className="mt-2 text-sm">
              {t("persona")}: {spec.persona?.displayName}
            </p>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">{spec.persona?.greeting}</p>
            <p className="mt-3 text-sm">{spec.instructions}</p>
            <ul className="mt-3 text-sm">
              {(spec.tools ?? []).map((tool) => (
                <li key={tool.server}>
                  {t("toolSlot")}: {tool.server}
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
        <section className="detail-panel mt-8">
          <h2 className="text-sm font-medium">{t("createForm")}</h2>
          <label className="mt-3 block text-sm font-medium" htmlFor="agent-form-name">
            {t("name")}
          </label>
          <input
            className="mt-1 w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
            id="agent-form-name"
            onChange={(event) => setFormName(event.target.value)}
            value={formName}
          />
          <label className="mt-3 block text-sm font-medium" htmlFor="agent-form-instructions">
            {t("instructions")}
          </label>
          <textarea
            className="mt-1 min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
            id="agent-form-instructions"
            onChange={(event) => setFormInstructions(event.target.value)}
            value={formInstructions}
          />
          <label className="mt-3 block text-sm font-medium" htmlFor="agent-form-model">
            {t("modelAlias")}
          </label>
          <select
            className="mt-1 rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-2 text-sm"
            id="agent-form-model"
            onChange={(event) => setFormModel(event.target.value)}
            value={formModel}
          >
            <option value="reasoning">reasoning</option>
            <option value="fast">fast</option>
          </select>
          <fieldset className="mt-4">
            <legend className="text-sm font-medium">{t("generalTools")}</legend>
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
                className="mt-1 w-full max-w-xs rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
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
          <Button
            className="mt-3"
            disabled={busy || formName.trim().length < 2 || formInstructions.trim().length < 8}
            onClick={() => void createDirect()}
            type="button"
          >
            {t("createUse")}
          </Button>
        </section>
        <section className="mt-8">
          <h2 className="text-sm font-medium text-[var(--muted-foreground)]">{t("templates")}</h2>
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
      </fieldset>
    </div>
  );
}
