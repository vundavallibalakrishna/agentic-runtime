"use client";

import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { ActionStatus, DetailState, ErrorMessage } from "@/components/common/detail-state";
import { Button } from "@/components/ui/button";
import { ApiError, api, type DisplayError } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { loadSession } from "@/lib/session";

type MemorySettings = { enabled: boolean; extraction: boolean; extractionInstructions: string };
type Tenant = { settings?: { memory?: Partial<MemorySettings> } };
const LIMIT = 2000;
const characterCount = (value: string) => Array.from(value).length;
const fields = ["enabled", "extraction", "extractionInstructions"] as const;

function memoryFrom(tenant: Tenant): MemorySettings | null {
  const memory = tenant?.settings?.memory;
  return typeof memory?.enabled === "boolean" &&
    typeof memory.extraction === "boolean" &&
    typeof memory.extractionInstructions === "string" &&
    characterCount(memory.extractionInstructions) <= LIMIT
    ? {
        enabled: memory.enabled,
        extraction: memory.extraction,
        extractionInstructions: memory.extractionInstructions,
      }
    : null;
}

/** Uses the existing tenant memory settings; explicit edits never resend unrelated values. */
export function OrganisationMemorySettings() {
  const t = useTranslations("memory");
  const [settings, setSettings] = useState<MemorySettings | null>(null);
  const [draft, setDraft] = useState<MemorySettings | null>(null);
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [readDenied, setReadDenied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<DisplayError>("");
  const [loadError, setLoadError] = useState<DisplayError>("");
  const [notice, setNotice] = useState("");
  const [recovery, setRecovery] = useState(false);
  const saved = useRef<MemorySettings | null>(null);
  const readRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const feedback = useRef<HTMLDivElement>(null);
  const busy = loading || saving;

  const load = useCallback(
    async (apply = false) => {
      if (readRequest.current || actionRequest.current) return;
      const request = new AbortController();
      readRequest.current = request;
      setLoading(true);
      setLoadError("");
      setNotice("");
      try {
        const session = await loadSession();
        if (request.signal.aborted) return;
        const held = session.permissions ?? [];
        const manage = held.includes("tenant:manage");
        setAllowed(manage);
        setReadDenied(manage && !held.includes("tenant:read"));
        if (!manage || !held.includes("tenant:read")) {
          setSettings(null);
          saved.current = null;
          return;
        }
        const tenant = await api<Tenant>("/api/v1/tenant", { signal: request.signal });
        if (request.signal.aborted) return;
        const memory = memoryFrom(tenant);
        if (!memory) throw new Error(t("orgMetadataError"));
        if (apply || !saved.current) setDraft(memory);
        saved.current = memory;
        setSettings(memory);
        setError("");
        setRecovery(false);
      } catch (caught) {
        if (!request.signal.aborted) {
          setLoadError(caught instanceof Error ? caught : t("error"));
          if (caught instanceof ApiError && [401, 403, 404].includes(caught.status)) {
            setSettings(null);
            saved.current = null;
          }
        }
      } finally {
        if (readRequest.current === request) {
          readRequest.current = null;
          setLoading(false);
        }
      }
    },
    [t],
  );

  useEffect(() => {
    void load(true);
    return () => {
      readRequest.current?.abort();
      readRequest.current = null;
      actionRequest.current?.abort();
      actionRequest.current = null;
    };
  }, [load]);
  useEffect(() => {
    if (error) feedback.current?.focus();
  }, [error]);

  const submitted = draft
    ? { ...draft, extractionInstructions: draft.extractionInstructions.trim() }
    : null;
  const tooLong = Boolean(draft && characterCount(draft.extractionInstructions) > LIMIT);
  const dirty = Boolean(
    settings && submitted && fields.some((field) => settings[field] !== submitted[field]),
  );
  function edit(next: Partial<MemorySettings>) {
    setDraft((current) => (current ? { ...current, ...next } : null));
    setNotice("");
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (
      actionRequest.current ||
      readRequest.current ||
      !allowed ||
      !settings ||
      !submitted ||
      !dirty ||
      loadError ||
      recovery ||
      tooLong
    )
      return;
    const patch = Object.fromEntries(
      fields
        .filter((field) => settings[field] !== submitted[field])
        .map((field) => [field, submitted[field]]),
    );
    const request = new AbortController();
    actionRequest.current = request;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const tenant = await api<Tenant>("/api/v1/tenant", {
        method: "PATCH",
        signal: request.signal,
        body: JSON.stringify({ settings: { memory: patch } }),
      });
      if (request.signal.aborted) return;
      const memory = memoryFrom(tenant);
      if (!memory || fields.some((field) => field in patch && patch[field] !== memory[field]))
        throw new Error(t("orgUnconfirmed"));
      saved.current = memory;
      setSettings(memory);
      setDraft(memory);
      setNotice(t("orgSaved"));
    } catch (caught) {
      if (!request.signal.aborted) {
        setError(caught instanceof Error ? caught : t("error"));
        setRecovery(true);
      }
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setSaving(false);
      }
    }
  }

  if (allowed === false && !loadError) return null;
  return (
    <section aria-labelledby="memory-organisation" className="mt-10">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold" id="memory-organisation">
          {t("orgTitle")}
        </h2>
        <Button
          type="button"
          variant="outline"
          disabled={busy}
          aria-label={t("orgRefresh")}
          onClick={() => void load()}
        >
          <RefreshCw size={16} aria-hidden="true" />
        </Button>
      </div>
      <p className="mb-4 max-w-2xl text-sm leading-relaxed text-[var(--muted-foreground)]">
        {t("orgBody")}
      </p>
      <DetailState
        loading={loading}
        error={loadError}
        onRetry={busy ? undefined : () => void load()}
      />
      {readDenied ? <p className="text-sm">{t("orgReadDenied")}</p> : null}
      {allowed && settings && draft ? (
        <form
          className="grid gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
          onSubmit={(event) => void save(event)}
        >
          <p className="text-sm text-[var(--muted-foreground)]">
            {t("orgSavedSummary", {
              memory: t(settings.enabled ? "orgOn" : "orgOff"),
              automatic: t(settings.extraction ? "orgOn" : "orgOff"),
            })}
          </p>
          <fieldset disabled={busy || Boolean(loadError) || recovery} className="min-w-0 space-y-5">
            <label className="flex items-start gap-3 text-sm">
              <input
                checked={draft.enabled}
                className="mt-1"
                onChange={(event) => edit({ enabled: event.target.checked })}
                type="checkbox"
              />
              <span>
                <span className="block font-medium">{t("orgEnabled")}</span>
                <span className="mt-1 block leading-relaxed text-[var(--muted-foreground)]">
                  {t("orgEnabledHint")}
                </span>
              </span>
            </label>
            <label className="flex items-start gap-3 text-sm">
              <input
                checked={draft.extraction}
                className="mt-1"
                disabled={!draft.enabled}
                onChange={(event) => edit({ extraction: event.target.checked })}
                type="checkbox"
              />
              <span>
                <span className="block font-medium">{t("orgExtraction")}</span>
                <span className="mt-1 block leading-relaxed text-[var(--muted-foreground)]">
                  {t("orgExtractionHint")}
                </span>
              </span>
            </label>
            {!draft.enabled ? (
              <p className="text-sm text-[var(--muted-foreground)]">{t("orgPaused")}</p>
            ) : null}
            <div className="grid gap-1">
              <label className="text-sm font-medium" htmlFor="memory-instructions">
                {t("orgInstructions")}
              </label>
              <textarea
                aria-describedby={`memory-instructions-hint memory-instructions-count${tooLong ? " memory-instructions-error" : ""}`}
                aria-invalid={tooLong}
                className="min-h-28 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
                id="memory-instructions"
                // Native maxLength counts UTF-16 units; validation below counts the API's characters.
                maxLength={LIMIT * 2}
                onChange={(event) => edit({ extractionInstructions: event.target.value })}
                value={draft.extractionInstructions}
              />
              <p
                className="text-xs leading-relaxed text-[var(--muted-foreground)]"
                id="memory-instructions-hint"
              >
                {t("orgInstructionsHint")}
              </p>
              <p className="text-xs text-[var(--muted-foreground)]" id="memory-instructions-count">
                {t("orgCount", {
                  count: formatCount(characterCount(draft.extractionInstructions)),
                  limit: formatCount(LIMIT),
                })}
              </p>
            </div>
            {tooLong ? (
              <p id="memory-instructions-error" className="text-sm text-[var(--destructive)]">
                {t("orgTooLong", { limit: formatCount(LIMIT) })}
              </p>
            ) : null}
          </fieldset>
          {dirty ? (
            <p className="text-sm text-[var(--muted-foreground)]">{t("orgUnsaved")}</p>
          ) : null}
          {recovery ? <p className="text-sm">{t("orgRecovery")}</p> : null}
          {error ? (
            <div
              ref={feedback}
              tabIndex={-1}
              className="break-words text-sm text-[var(--destructive)]"
              role="alert"
            >
              <ErrorMessage error={error} />
            </div>
          ) : null}
          <ActionStatus busy={saving} busyLabel={t("orgSaving")} notice={notice} />
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={busy || Boolean(loadError) || recovery || !dirty || tooLong}
              type="submit"
            >
              {t("orgSave")}
            </Button>
            {dirty ? (
              <Button
                variant="outline"
                type="button"
                disabled={busy}
                onClick={() => {
                  setDraft(settings);
                  setNotice("");
                }}
              >
                {t("orgUseSaved")}
              </Button>
            ) : null}
          </div>
        </form>
      ) : null}
    </section>
  );
}
