"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

import type { Definition } from "./types";

const TEMPLATES = ["blank", "assistant", "researcher", "analyst", "support"] as const;

type Proposal = {
  resources?: { spec?: Definition; metadata?: { name?: string } }[];
};

type SessionView = {
  proposal?: Proposal;
  validation?: { errors?: { msg?: string }[]; warnings?: { msg?: string }[] };
};

export function BuilderScreen() {
  const t = useTranslations("agents");
  const router = useRouter();
  const [instruction, setInstruction] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [view, setView] = useState<SessionView | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const spec = view?.proposal?.resources?.[0]?.spec;

  async function draft() {
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
      <PageHeader body={t("builderBody")} title={t("builderTitle")} />
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
            <Button disabled={busy} onClick={() => void apply()} type="button">
              {t("apply")}
            </Button>
          </div>
        </section>
      ) : null}
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
    </div>
  );
}
