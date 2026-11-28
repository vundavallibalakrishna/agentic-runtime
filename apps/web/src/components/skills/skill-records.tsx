"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

import { DetailState } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

function useSkillRecord<T>(path: string) {
  const t = useTranslations("skills");
  const [body, setBody] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);
  const load = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError("");
    try {
      const saved = await api<T>(path, { signal: controller.signal });
      if (!controller.signal.aborted) setBody(saved);
    } catch (caught) {
      if (!controller.signal.aborted)
        setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [path, t]);
  useEffect(() => {
    void load();
    return () => request.current?.abort();
  }, [load]);
  return { body, loading, error, load };
}

type Version = { version: number; instructionsMd?: string; hash?: string; createdAt?: string };
export function SkillHistory({ skillId }: { skillId: string }) {
  const t = useTranslations("skills");
  const { body, loading, error, load } = useSkillRecord<{ items: Version[] }>(
    `/api/v1/skills/${skillId}/versions`,
  );
  const rows = body?.items ?? [];
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Version | null>(null);
  const opener = useRef<HTMLButtonElement>(null);
  const matching = rows.filter((row) =>
    [`v${row.version}`, row.hash, row.createdAt].some((value) =>
      value?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
    ),
  );
  const pagination = usePagedRows(matching, query);
  function close() {
    setSelected(null);
    requestAnimationFrame(() => opener.current?.focus());
  }
  return (
    <section aria-label={t("versions")} className="detail-panel">
      <p className="mb-4 text-sm text-[var(--muted-foreground)]">{t("historyHelp")}</p>
      <Input
        type="search"
        aria-label={t("versionSearch")}
        placeholder={t("versionSearch")}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <div className="mt-4">
        <DetailState loading={loading} error={error} onRetry={() => void load()} />
      </div>
      {!loading && !error && !matching.length ? (
        <EmptyState compact title={t(rows.length ? "noVersionMatches" : "noVersions")} />
      ) : null}
      <ul className="row-list mt-4">
        {!loading && !error
          ? pagination.rows.map((row) => (
              <li
                key={row.version}
                className="flex flex-wrap items-center justify-between gap-3 p-4 text-sm"
              >
                <div className="min-w-0">
                  <p className="font-medium">v{row.version}</p>
                  {row.createdAt ? (
                    <time
                      className="text-xs text-[var(--muted-foreground)]"
                      dateTime={row.createdAt}
                    >
                      {new Date(row.createdAt).toLocaleString()}
                    </time>
                  ) : null}
                  {row.hash ? (
                    <p
                      title={row.hash}
                      className="mt-1 break-all text-xs text-[var(--muted-foreground)]"
                    >
                      {row.hash.slice(0, 16)}
                    </p>
                  ) : null}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  aria-label={t("viewVersionNamed", { version: row.version })}
                  onClick={(event) => {
                    opener.current = event.currentTarget;
                    setSelected(row);
                  }}
                >
                  {t("viewVersion")}
                </Button>
              </li>
            ))
          : null}
      </ul>
      {!loading && !error && rows.length ? (
        <ListPagination {...pagination} label={t("versions")} />
      ) : null}
      <Dialog
        open={Boolean(selected)}
        onOpenChange={(open) => {
          if (!open) close();
        }}
      >
        <DialogContent
          title={selected ? t("versionTitle", { version: selected.version }) : t("versions")}
        >
          <p className="mt-4 text-sm text-[var(--muted-foreground)]">{t("historyHelp")}</p>
          <div className="prose-sm mt-4 min-w-0 overflow-auto break-words text-sm [&_pre]:overflow-auto [&_a]:break-all">
            <ReactMarkdown>{selected?.instructionsMd || t("noInstructions")}</ReactMarkdown>
          </div>
          {selected?.hash ? (
            <p className="mt-4 break-all text-xs text-[var(--muted-foreground)]">
              {t("contentHash")}: {selected.hash}
            </p>
          ) : null}
          <div className="mt-4 flex justify-end">
            <Button type="button" variant="outline" onClick={close}>
              {t("close")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}

type Dependant = {
  agentId?: string;
  slug?: string;
  name?: string;
  state?: string;
  updateAvailable?: boolean;
};
export function SkillDependants({
  skillId,
  canOpenAgent,
}: {
  skillId: string;
  canOpenAgent: boolean;
}) {
  const t = useTranslations("skills");
  const { body, loading, error, load } = useSkillRecord<{ agents?: Dependant[] }>(
    `/api/v1/skills/${skillId}/where-used`,
  );
  const rows = body?.agents ?? [];
  const [query, setQuery] = useState("");
  const [state, setState] = useState("");
  const [updates, setUpdates] = useState(false);
  const matching = rows.filter(
    (row) =>
      (!state || row.state === state) &&
      (!updates || row.updateAvailable) &&
      [row.agentId, row.slug, row.name].some((value) =>
        value?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
      ),
  );
  const pagination = usePagedRows(matching, `${query}::${state}::${updates}`);
  return (
    <section aria-label={t("whereUsed")} className="detail-panel">
      <p className="mb-4 text-sm text-[var(--muted-foreground)]">{t("dependantsHelp")}</p>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <Input
          className="min-w-0 shrink-0 sm:w-auto sm:flex-1"
          type="search"
          aria-label={t("dependantSearch")}
          placeholder={t("dependantSearch")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <label className="flex items-center gap-2 text-sm">
          {t("agentState")}
          <select
            className="h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
            value={state}
            onChange={(event) => setState(event.target.value)}
          >
            <option value="">{t("allStates")}</option>
            {[...new Set(rows.flatMap((row) => (row.state ? [row.state] : [])))]
              .sort()
              .map((value) => (
                <option key={value} value={value}>
                  {t.has(`states.${value}`) ? t(`states.${value}`) : value}
                </option>
              ))}
          </select>
        </label>
      </div>
      <label className="mb-4 flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={updates}
          onChange={(event) => setUpdates(event.target.checked)}
        />
        {t("updatesOnly")}
      </label>
      <DetailState loading={loading} error={error} onRetry={() => void load()} />
      {!loading && !error && !matching.length ? (
        <EmptyState compact title={t(rows.length ? "noDependantMatches" : "unused")} />
      ) : null}
      <ul className="row-list">
        {!loading && !error
          ? pagination.rows.map((row) => (
              <li key={`${row.agentId || row.slug}-${row.state}`} className="space-y-2 p-4 text-sm">
                <p className="break-words font-medium">{row.name || row.slug || row.agentId}</p>
                <div className="flex flex-wrap gap-2">
                  <Badge tone={statusTone(row.state)}>
                    {row.state && t.has(`states.${row.state}`)
                      ? t(`states.${row.state}`)
                      : row.state}
                  </Badge>
                  {row.updateAvailable ? (
                    <Badge tone="warning">{t("updateAvailable")}</Badge>
                  ) : null}
                </div>
                {canOpenAgent && row.agentId ? (
                  <Link className="inline-block underline" href={`/agents/${row.agentId}`}>
                    {t("reviewAgent")}
                  </Link>
                ) : null}
              </li>
            ))
          : null}
      </ul>
      {!loading && !error && rows.length ? (
        <ListPagination {...pagination} label={t("whereUsed")} />
      ) : null}
    </section>
  );
}
