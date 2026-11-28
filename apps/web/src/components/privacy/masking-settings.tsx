"use client";

import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActionStatus, DetailState, ErrorMessage } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { DisplayError } from "@/lib/api";
import { ApiError, api } from "@/lib/api";
import { loadSession } from "@/lib/session";

type Kind = { name: string; source: string; masked: boolean; default: boolean };
type View = {
  enabled: boolean;
  usesDefault: boolean;
  minScore: number;
  defaultMinScore: number;
  kinds: Kind[];
};
type Privacy = { redactionEntities?: string[] | null; redactionMinScore?: number | null };
type Tenant = { settings?: { features?: { piiRedaction?: boolean }; privacy?: Privacy } };
type Apply = "all" | "switch" | "none";
const sameMembers = (a: string[], b: string[]) => {
  const left = new Set(a);
  const right = new Set(b);
  return left.size === right.size && [...left].every((name) => right.has(name));
};
function isView(value: View): boolean {
  return Boolean(
    value &&
      typeof value.enabled === "boolean" &&
      typeof value.usesDefault === "boolean" &&
      typeof value.minScore === "number" &&
      Number.isFinite(value.minScore) &&
      value.minScore >= 0 &&
      value.minScore <= 1 &&
      typeof value.defaultMinScore === "number" &&
      Number.isFinite(value.defaultMinScore) &&
      value.defaultMinScore >= 0 &&
      value.defaultMinScore <= 1 &&
      Array.isArray(value.kinds) &&
      value.kinds.every(
        (kind) =>
          typeof kind.name === "string" &&
          kind.name &&
          typeof kind.source === "string" &&
          kind.source &&
          typeof kind.masked === "boolean" &&
          typeof kind.default === "boolean",
      ),
  );
}

/** Saved effective settings and a separate editable draft; reads never imply a save. */
export function MaskingSettings({ advanced }: { advanced: boolean }) {
  const t = useTranslations("masking");
  const [view, setView] = useState<View | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [chosen, setChosen] = useState<string[]>([]);
  const [score, setScore] = useState("");
  const [scoreEdited, setScoreEdited] = useState(false);
  const [effectiveDifference, setEffectiveDifference] = useState(false);
  const [canManage, setCanManage] = useState(false);
  const [readDenied, setReadDenied] = useState(false);
  const [loadError, setLoadError] = useState<DisplayError>("");
  const [loading, setLoading] = useState(true);
  const [phase, setPhase] = useState<"saving" | "restoring" | "refreshing" | null>(null);
  const busy = phase !== null;
  const [error, setError] = useState<DisplayError>("");
  const [notice, setNotice] = useState("");
  const [recovery, setRecovery] = useState<{ accepted: boolean; apply: Apply } | null>(null);
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const readRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const feedbackRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (error || effectiveDifference) feedbackRef.current?.focus();
  }, [error, effectiveDifference]);
  const chosenSet = useMemo(() => new Set(chosen), [chosen]);
  const label = useCallback(
    (name: string) => (t.has(`kinds.${name}`) ? t(`kinds.${name}`) : name),
    [t],
  );
  const sources = useMemo(
    () => [...new Set(view?.kinds.map((kind) => kind.source) ?? [])].sort(),
    [view],
  );
  const matching = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return (view?.kinds ?? []).filter(
      (kind) =>
        (!sourceFilter || kind.source === sourceFilter) &&
        (!term ||
          [kind.name, label(kind.name)].some((text) => text.toLocaleLowerCase().includes(term))),
    );
  }, [view, query, sourceFilter, label]);
  const page = usePagedRows(matching, `${query}:${sourceFilter}`);
  const pageSources = [...new Set(page.rows.map((kind) => kind.source))];
  const savedChosen = useMemo(
    () => view?.kinds.filter((kind) => kind.masked).map((kind) => kind.name) ?? [],
    [view],
  );
  const advancedDirty = Boolean(
    view && (!sameMembers(chosen, savedChosen) || scoreEdited || Number(score) !== view.minScore),
  );
  const dirty = Boolean(view && (enabled !== view.enabled || advancedDirty));
  const locked = !canManage || busy || loading || Boolean(loadError) || Boolean(recovery);

  const show = useCallback((next: View, apply: Apply) => {
    setView(next);
    if (apply !== "none") setEnabled(next.enabled);
    if (apply === "all") {
      setChosen(next.kinds.filter((kind) => kind.masked).map((kind) => kind.name));
      setScore(String(next.minScore));
      setScoreEdited(false);
    }
  }, []);
  const load = useCallback(
    async (apply: Apply) => {
      readRequest.current?.abort();
      const request = new AbortController();
      readRequest.current = request;
      setLoadError("");
      setLoading(true);
      setReadDenied(false);
      try {
        const session = await loadSession();
        if (request.signal.aborted) return false;
        const permissions = session.permissions ?? [];
        if (!permissions.includes("tenant:read")) {
          setCanManage(false);
          setReadDenied(true);
          setView(null);
          return false;
        }
        setCanManage(permissions.includes("tenant:manage"));
        const next = await api<View>("/api/v1/tenant/masking", { signal: request.signal });
        if (request.signal.aborted) return false;
        if (!isView(next)) throw new Error(t("unconfirmed"));
        show(next, apply);
        return next;
      } catch (caught) {
        if (!request.signal.aborted) {
          setLoadError(caught instanceof Error ? caught : t("error"));
          if (caught instanceof ApiError && [401, 403, 404].includes(caught.status)) {
            setCanManage(false);
            setView(null);
          }
        }
        return false;
      } finally {
        if (readRequest.current === request) {
          readRequest.current = null;
          setLoading(false);
        }
      }
    },
    [show, t],
  );
  useEffect(() => {
    void load("all");
    return () => {
      readRequest.current?.abort();
      actionRequest.current?.abort();
    };
  }, [load]);

  async function refresh() {
    if (actionRequest.current) return;
    if (await load(recovery?.accepted ? recovery.apply : "none")) {
      setRecovery(null);
      setError("");
      setEffectiveDifference(false);
    }
  }
  async function send(privacy: Privacy, done: string, apply: Apply, reset = false) {
    if (actionRequest.current || readRequest.current || locked || !view) return;
    const request = new AbortController();
    actionRequest.current = request;
    const submittedEnabled = enabled;
    setPhase(reset ? "restoring" : "saving");
    setError("");
    setNotice("");
    setEffectiveDifference(false);
    let accepted = false;
    try {
      const result = await api<Tenant>("/api/v1/tenant", {
        method: "PATCH",
        signal: request.signal,
        body: JSON.stringify({
          settings: { features: { piiRedaction: submittedEnabled }, privacy },
        }),
      });
      if (request.signal.aborted) return;
      const saved = result?.settings;
      const expectedKinds = privacy.redactionEntities;
      const actualKinds = saved?.privacy?.redactionEntities;
      if (
        saved?.features?.piiRedaction !== submittedEnabled ||
        ("redactionMinScore" in privacy &&
          saved?.privacy?.redactionMinScore !== privacy.redactionMinScore) ||
        ("redactionEntities" in privacy &&
          (expectedKinds === null
            ? actualKinds !== null
            : !Array.isArray(actualKinds) || !sameMembers(actualKinds, expectedKinds ?? [])))
      )
        throw new Error(t("saveUnconfirmed"));
      accepted = true;
      setNotice(done);
      setPhase("refreshing");
      const effective = await load(apply);
      if (!request.signal.aborted) {
        if (!effective) setRecovery({ accepted, apply });
        else if (
          Array.isArray(expectedKinds) &&
          !sameMembers(
            effective.kinds.filter((kind) => kind.masked).map((kind) => kind.name),
            expectedKinds,
          )
        )
          setEffectiveDifference(true);
      }
    } catch (caught) {
      if (!request.signal.aborted) {
        setError(caught instanceof Error ? caught : t("error"));
        setRecovery({ accepted, apply });
      }
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setPhase(null);
      }
    }
  }
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (locked || actionRequest.current || readRequest.current || !view) return;
    const value = score.trim() === "" ? null : Number(score);
    if (
      !event.currentTarget.checkValidity() ||
      (advanced && value !== null && (!Number.isFinite(value) || value < 0 || value > 1))
    ) {
      setError(t("scoreInvalid"));
      return;
    }
    const privacy: Privacy = {};
    if (advanced) {
      if (!sameMembers(chosen, savedChosen)) privacy.redactionEntities = chosen;
      if (scoreEdited) privacy.redactionMinScore = value;
    }
    void send(privacy, t("saved"), advanced ? "all" : "switch");
  }
  function clearFeedback() {
    setNotice("");
    if (!recovery) {
      setError("");
      setEffectiveDifference(false);
    }
  }
  function toggle(name: string, on: boolean) {
    clearFeedback();
    setChosen((current) =>
      on ? [...new Set([...current, name])] : current.filter((item) => item !== name),
    );
  }

  const status = (
    <ActionStatus
      busy={busy || loading}
      busyLabel={phase ? t(`progress.${phase}`) : t("loading")}
      notice={notice}
    />
  );
  return (
    <section aria-labelledby="masking-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold" id="masking-title">
          {t("title")}
        </h2>
        <Button
          type="button"
          variant="outline"
          className="size-9 p-0"
          aria-label={t("refresh")}
          title={t("refresh")}
          disabled={busy || loading}
          onClick={() => void refresh()}
        >
          <RefreshCw size={16} aria-hidden="true" />
        </Button>
      </div>
      <p className="mb-4 mt-1 max-w-2xl text-sm leading-relaxed text-[var(--muted-foreground)]">
        {t("body")}
      </p>
      <DetailState
        loading={loading && !view}
        error={loadError}
        onRetry={busy ? undefined : () => void refresh()}
      />
      {!view ? status : null}
      {recovery ? (
        <p className="mb-2 text-sm text-[var(--muted-foreground)]">
          {t(recovery.accepted ? "acceptedRecovery" : "recovery")}
        </p>
      ) : null}
      {error ? (
        <div
          ref={(node) => {
            feedbackRef.current = node;
          }}
          tabIndex={-1}
          className="mb-4 break-words text-sm text-[var(--destructive)]"
          role="alert"
        >
          <ErrorMessage error={error} />
        </div>
      ) : null}
      {readDenied ? <p className="text-sm">{t("readDenied")}</p> : null}
      {effectiveDifference ? (
        <p
          ref={
            error
              ? undefined
              : (node) => {
                  feedbackRef.current = node;
                }
          }
          tabIndex={-1}
          className="mb-4 text-sm"
          role="status"
        >
          {t("effectiveDifference")}
        </p>
      ) : null}
      {view ? (
        <form
          className="grid gap-5 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
          onSubmit={save}
        >
          <label className="flex items-start gap-2 text-sm">
            <input
              checked={enabled}
              className="mt-1"
              disabled={locked}
              onChange={(event) => {
                setEnabled(event.target.checked);
                clearFeedback();
              }}
              type="checkbox"
            />
            <span>
              {t("enabled")}{" "}
              <span className="text-[var(--muted-foreground)]">{t("enabledHint")}</span>
            </span>
          </label>
          {dirty && canManage ? (
            <p className="text-xs text-[var(--muted-foreground)]">
              {t(!advanced && advancedDirty ? "advancedDraft" : "unsaved")}
            </p>
          ) : null}
          {advanced ? (
            <>
              {view.kinds.length > 25 || query || sourceFilter ? (
                <div className="flex flex-wrap gap-3">
                  <Input
                    type="search"
                    className="min-w-0 flex-1"
                    aria-label={t("search")}
                    placeholder={t("search")}
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                  />
                  <select
                    aria-label={t("method")}
                    className="h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
                    value={sourceFilter}
                    onChange={(event) => setSourceFilter(event.target.value)}
                  >
                    <option value="">{t("allMethods")}</option>
                    {sources.map((source) => (
                      <option key={source} value={source}>
                        {t.has(`source.${source}`) ? t(`source.${source}`) : source}
                      </option>
                    ))}
                  </select>
                  {query || sourceFilter ? (
                    <Button
                      variant="outline"
                      type="button"
                      onClick={() => {
                        setQuery("");
                        setSourceFilter("");
                      }}
                    >
                      {t("clearFilters")}
                    </Button>
                  ) : null}
                </div>
              ) : null}
              {!matching.length ? (
                <p className="text-sm">{t(view.kinds.length ? "noMatches" : "noKinds")}</p>
              ) : null}
              {pageSources.map((source) => (
                <fieldset key={source} className="grid gap-2" disabled={locked || !enabled}>
                  <legend className="text-sm font-medium">
                    {t.has(`source.${source}`) ? t(`source.${source}`) : source}
                  </legend>
                  {t.has(`sourceHint.${source}`) ? (
                    <p className="text-xs leading-relaxed text-[var(--muted-foreground)]">
                      {t(`sourceHint.${source}`)}
                    </p>
                  ) : null}
                  <ul className="grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
                    {page.rows
                      .filter((kind) => kind.source === source)
                      .map((kind) => (
                        <li key={kind.name}>
                          <label className="flex items-center gap-2 text-sm">
                            <input
                              checked={chosenSet.has(kind.name)}
                              onChange={(event) => toggle(kind.name, event.target.checked)}
                              type="checkbox"
                            />
                            <span className="min-w-0 break-words">{label(kind.name)}</span>
                          </label>
                        </li>
                      ))}
                  </ul>
                </fieldset>
              ))}
              {view.kinds.length > 25 ? <ListPagination {...page} label={t("kindList")} /> : null}
              <div className="grid gap-1">
                <label className="text-sm font-medium" htmlFor="masking-score">
                  {t("score")}
                </label>
                <Input
                  aria-describedby="masking-score-hint"
                  className="w-28"
                  disabled={locked || !enabled}
                  id="masking-score"
                  max={1}
                  min={0}
                  onChange={(event) => {
                    setScore(event.target.value);
                    setScoreEdited(true);
                    clearFeedback();
                  }}
                  step="any"
                  type="number"
                  value={score}
                  placeholder={String(view.defaultMinScore)}
                />
                <p
                  className="max-w-2xl text-xs leading-relaxed text-[var(--muted-foreground)]"
                  id="masking-score-hint"
                >
                  {t("scoreHint", { value: view.defaultMinScore })} {t("blankScore")}
                </p>
              </div>
            </>
          ) : (
            <p className="text-sm text-[var(--muted-foreground)]">
              {t(
                !view.enabled
                  ? "summaryOff"
                  : view.usesDefault
                    ? "summaryDefault"
                    : "summaryChosen",
                { count: savedChosen.length },
              )}
            </p>
          )}
          {!canManage ? <p className="text-sm">{t("readOnly")}</p> : null}
          {status}
          {canManage ? (
            <div className="flex flex-wrap gap-2">
              <Button disabled={locked} type="submit">
                {t("save")}
              </Button>
              {dirty ? (
                <Button
                  disabled={locked}
                  type="button"
                  variant="outline"
                  onClick={() => {
                    show(view, "all");
                    setError("");
                    setEffectiveDifference(false);
                    setNotice("");
                  }}
                >
                  {t("useSaved")}
                </Button>
              ) : null}
              {advanced && (!view.usesDefault || view.minScore !== view.defaultMinScore) ? (
                <Button
                  disabled={locked}
                  onClick={() =>
                    void send(
                      { redactionEntities: null, redactionMinScore: null },
                      t("defaultRestored"),
                      "all",
                      true,
                    )
                  }
                  type="button"
                  variant="ghost"
                >
                  {t("useDefault")}
                </Button>
              ) : null}
            </div>
          ) : null}
        </form>
      ) : null}
    </section>
  );
}
