"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Kind = { name: string; source: string; masked: boolean; default: boolean };
type View = {
  enabled: boolean;
  usesDefault: boolean;
  minScore: number;
  defaultMinScore: number;
  kinds: Kind[];
};
type Session = { permissions?: string[] };

const SOURCES = ["format", "language"] as const;

/**
 * What the organisation masks in a tool's result before the model reads it: whether it
 * masks at all, which kinds of personal data, and how sure a match must be.
 */
export function MaskingSettings({ advanced }: { advanced: boolean }) {
  const t = useTranslations("masking");
  const [view, setView] = useState<View | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [chosen, setChosen] = useState<string[]>([]);
  const [score, setScore] = useState("");
  const [canManage, setCanManage] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const show = useCallback((next: View) => {
    setView(next);
    setEnabled(next.enabled);
    setChosen(next.kinds.filter((kind) => kind.masked).map((kind) => kind.name));
    setScore(String(next.minScore));
  }, []);

  const load = useCallback(async () => {
    setLoadError("");
    try {
      const session = await api<Session>("/api/v1/auth/session");
      setCanManage((session.permissions ?? []).includes("tenant:manage"));
      show(await api<View>("/api/v1/tenant/masking"));
    } catch (caught) {
      setLoadError(caught instanceof Error ? caught.message : t("error"));
    }
  }, [show, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function send(privacy: Record<string, unknown>, done: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("/api/v1/tenant", {
        method: "PATCH",
        body: JSON.stringify({ settings: { features: { piiRedaction: enabled }, privacy } }),
      });
      show(await api<View>("/api/v1/tenant/masking"));
      setNotice(done);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  function save(event: FormEvent) {
    event.preventDefault();
    if (!view) return;
    // In Simple mode only the switch is on the page, so the list is left as it is saved.
    const privacy = advanced ? { redactionEntities: chosen, redactionMinScore: Number(score) } : {};
    void send(privacy, t("saved"));
  }

  function toggle(name: string, on: boolean) {
    setChosen((current) => (on ? [...current, name] : current.filter((item) => item !== name)));
  }

  const label = (name: string) => (t.has(`kinds.${name}`) ? t(`kinds.${name}`) : name);
  const locked = !canManage || busy;

  return (
    <section aria-labelledby="masking-title" className="mt-10">
      <h2 className="text-sm font-semibold" id="masking-title">
        {t("title")}
      </h2>
      <p className="mb-4 mt-1 max-w-2xl text-sm leading-relaxed text-[var(--muted-foreground)]">
        {t("body")}
      </p>
      {loadError ? (
        <p role="alert" className="text-sm">
          {loadError}{" "}
          <Button type="button" variant="ghost" onClick={() => void load()}>
            {t("retry")}
          </Button>
        </p>
      ) : null}
      {!view && !loadError ? (
        <div aria-busy="true">
          <span className="sr-only">{t("loading")}</span>
          <Skeleton className="h-24 w-full" />
        </div>
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
              onChange={(event) => setEnabled(event.target.checked)}
              type="checkbox"
            />
            <span>
              {t("enabled")}{" "}
              <span className="text-[var(--muted-foreground)]">{t("enabledHint")}</span>
            </span>
          </label>
          {advanced ? (
            <>
              {SOURCES.map((source) => (
                <fieldset key={source} className="grid gap-2" disabled={locked || !enabled}>
                  <legend className="text-sm font-medium">{t(`source.${source}`)}</legend>
                  <p className="text-xs leading-relaxed text-[var(--muted-foreground)]">
                    {t(`sourceHint.${source}`)}
                  </p>
                  <ul className="grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
                    {view.kinds
                      .filter((kind) => kind.source === source)
                      .map((kind) => (
                        <li key={kind.name}>
                          <label className="flex items-center gap-2 text-sm">
                            <input
                              checked={chosen.includes(kind.name)}
                              onChange={(event) => toggle(kind.name, event.target.checked)}
                              type="checkbox"
                            />
                            {label(kind.name)}
                          </label>
                        </li>
                      ))}
                  </ul>
                </fieldset>
              ))}
              <div className="grid gap-1">
                <label className="text-sm font-medium" htmlFor="masking-score">
                  {t("score")}
                </label>
                <input
                  aria-describedby="masking-score-hint"
                  className="w-28 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
                  disabled={locked || !enabled}
                  id="masking-score"
                  max={1}
                  min={0}
                  onChange={(event) => setScore(event.target.value)}
                  step={0.05}
                  type="number"
                  value={score}
                />
                <p
                  className="max-w-2xl text-xs leading-relaxed text-[var(--muted-foreground)]"
                  id="masking-score-hint"
                >
                  {t("scoreHint", { value: view.defaultMinScore })}
                </p>
              </div>
            </>
          ) : (
            <p className="text-sm text-[var(--muted-foreground)]">
              {view.usesDefault
                ? t("summaryDefault", { count: chosen.length })
                : t("summaryChosen", { count: chosen.length })}
            </p>
          )}
          {!canManage ? <p className="text-sm">{t("readOnly")}</p> : null}
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
          {canManage ? (
            <div className="flex flex-wrap gap-2">
              <Button disabled={busy} type="submit">
                {t("save")}
              </Button>
              {advanced && !view.usesDefault ? (
                <Button
                  disabled={busy}
                  onClick={() =>
                    void send(
                      { redactionEntities: null, redactionMinScore: null },
                      t("defaultRestored"),
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
