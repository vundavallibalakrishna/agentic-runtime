"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

type MemorySettings = {
  enabled?: boolean;
  extraction?: boolean;
  extractionInstructions?: string;
};

const LIMIT = 2000;

/**
 * What an administrator sets for everyone: whether the assistant remembers from
 * conversations, and what the organisation adds to the guidance the model is given.
 */
export function OrganisationMemorySettings() {
  const t = useTranslations("memory");
  const [settings, setSettings] = useState<MemorySettings | null>(null);
  const [extraction, setExtraction] = useState(true);
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    void api<{ settings?: { memory?: MemorySettings } }>("/api/v1/tenant")
      .then((tenant) => {
        if (cancelled) return;
        const memory = tenant.settings?.memory ?? {};
        setSettings(memory);
        setExtraction(memory.extraction !== false);
        setInstructions(memory.extractionInstructions ?? "");
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : t("error"));
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("/api/v1/tenant", {
        method: "PATCH",
        body: JSON.stringify({
          settings: {
            memory: { ...settings, extraction, extractionInstructions: instructions.trim() },
          },
        }),
      });
      setNotice(t("orgSaved"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="memory-organisation" className="mt-10">
      <h2 className="text-sm font-semibold" id="memory-organisation">
        {t("orgTitle")}
      </h2>
      <p className="mb-4 mt-1 max-w-2xl text-sm leading-relaxed text-[var(--muted-foreground)]">
        {t("orgBody")}
      </p>
      <form
        className="grid gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
        onSubmit={(event) => void save(event)}
      >
        <label className="flex items-start gap-2 text-sm">
          <input
            checked={extraction}
            className="mt-1"
            disabled={settings === null}
            onChange={(event) => setExtraction(event.target.checked)}
            type="checkbox"
          />
          <span>
            {t("orgExtraction")}{" "}
            <span className="text-[var(--muted-foreground)]">{t("orgExtractionHint")}</span>
          </span>
        </label>
        <div className="grid gap-1">
          <label className="text-sm font-medium" htmlFor="memory-instructions">
            {t("orgInstructions")}
          </label>
          <textarea
            aria-describedby="memory-instructions-hint"
            className="min-h-28 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
            disabled={settings === null}
            id="memory-instructions"
            maxLength={LIMIT}
            onChange={(event) => setInstructions(event.target.value)}
            value={instructions}
          />
          <p
            className="text-xs leading-relaxed text-[var(--muted-foreground)]"
            id="memory-instructions-hint"
          >
            {t("orgInstructionsHint")}
          </p>
        </div>
        {error ? (
          <p className="text-sm text-[var(--destructive)]" role="alert">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="text-sm" role="status">
            {notice}
          </p>
        ) : null}
        <Button className="justify-self-start" disabled={busy || settings === null} type="submit">
          {t("orgSave")}
        </Button>
      </form>
    </section>
  );
}
