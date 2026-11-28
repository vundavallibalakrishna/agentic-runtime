"use client";

import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, DetailState, ErrorMessage } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { OrganisationMemorySettings } from "@/components/memory/organisation-settings";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, api, type DisplayError } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { loadSession } from "@/lib/session";

type Fact = {
  id: string;
  content: string;
  scope: string;
  category: string;
  status: string;
  agent?: { id: string; name?: string } | null;
};
type Team = { id: string; name: string; items: Fact[] };
type MemoryPage = { items: Fact[]; teams: Team[]; memoryEnabled: boolean };
type Filters = { query: string; scope: string; category: string };
type Operation =
  | { kind: "add"; content: string }
  | { kind: "edit"; fact: Fact; content: string }
  | { kind: "delete"; fact: Fact }
  | { kind: "toggle"; enabled: boolean };
type Issue = { accepted: boolean; error: DisplayError };
const MODE_KEY = "ar-settings-mode";
const CONTENT_LIMIT = 500;
const count = (value: string) => Array.from(value).length;
// Stored facts collapse Python whitespace; use that form only to verify the returned receipt.
const storedText = (value: string) =>
  // biome-ignore lint/suspicious/noControlCharactersInRegex: Python also treats these four separators as whitespace.
  value.replace(/[\p{White_Space}\u001c-\u001f]+/gu, " ").replace(/^ | $/g, "");
const nonempty = (value: unknown): value is string =>
  typeof value === "string" && Boolean(value.trim());
const editable = (fact: Fact) => fact.scope === "user" || fact.scope === "agent_user";
function validFact(fact: Fact): boolean {
  return Boolean(
    fact &&
      [fact.id, fact.scope, fact.category, fact.status].every(nonempty) &&
      typeof fact.content === "string" &&
      count(fact.content) <= CONTENT_LIMIT &&
      nonempty(fact.content) &&
      (fact.agent == null ||
        (nonempty(fact.agent.id) &&
          (fact.agent.name === undefined || typeof fact.agent.name === "string"))),
  );
}
function validPage(page: MemoryPage): boolean {
  return Boolean(
    page &&
      typeof page.memoryEnabled === "boolean" &&
      Array.isArray(page.items) &&
      page.items.every(validFact) &&
      Array.isArray(page.teams) &&
      page.teams.every(
        (team) =>
          team &&
          nonempty(team.id) &&
          nonempty(team.name) &&
          Array.isArray(team.items) &&
          team.items.every(validFact),
      ),
  );
}
const filterKey = (filters: Filters) => JSON.stringify(filters);

export function MemoryScreen() {
  const t = useTranslations("memory");
  const [page, setPage] = useState<MemoryPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<DisplayError>("");
  const [issue, setIssue] = useState<Issue | null>(null);
  const [phase, setPhase] = useState<{ kind: Operation["kind"]; id?: string } | null>(null);
  const [notice, setNotice] = useState("");
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [canManageTenant, setCanManageTenant] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [advancedOpened, setAdvancedOpened] = useState(false);
  const [content, setContent] = useState("");
  const [editor, setEditor] = useState<{ fact: Fact; content: string } | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [scope, setScope] = useState("");
  const [category, setCategory] = useState("");
  const filters = useMemo(() => ({ query: search, scope, category }), [search, scope, category]);
  const currentFilters = useRef(filters);
  currentFilters.current = filters;
  const [loadedFilters, setLoadedFilters] = useState<Filters | null>(null);
  const readRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const feedback = useRef<HTMLDivElement>(null);
  const editField = useRef<HTMLTextAreaElement>(null);
  const previousEditor = useRef("");
  const busy = phase !== null;
  const held = busy || loading || Boolean(loadError) || issue !== null || page === null || !allowed;
  const pagination = usePagedRows(page?.items ?? [], filterKey(filters));
  const filtered = Boolean(search || scope || category);
  const categoryLabel = (value: string) =>
    t.has(`categories.${value}`) ? t(`categories.${value}`) : value;
  const scopeLabel = (value: string) => (t.has(`scopes.${value}`) ? t(`scopes.${value}`) : value);

  useEffect(() => {
    const initial = window.localStorage.getItem(MODE_KEY) === "advanced";
    setAdvanced(initial);
    setAdvancedOpened(initial);
    return () => {
      actionRequest.current?.abort();
      actionRequest.current = null;
    };
  }, []);
  useEffect(() => {
    if (issue) feedback.current?.focus();
  }, [issue]);

  const editingId = editor?.fact.id ?? "";
  useEffect(() => {
    if (editingId && previousEditor.current !== editingId) {
      previousEditor.current = editingId;
      editField.current?.focus();
    } else if (!editingId && previousEditor.current && !busy && !issue) {
      const target =
        document.getElementById(`edit-memory-${previousEditor.current}`) ??
        document.getElementById("memory-search");
      target?.focus();
      previousEditor.current = "";
    }
  }, [editingId, busy, issue]);

  const read = useCallback(
    async (signal: AbortSignal, selected: Filters) => {
      try {
        const session = await loadSession();
        if (signal.aborted) return null;
        const permissions = session.permissions ?? [];
        const canUse = permissions.includes("chat:use");
        setAllowed(canUse);
        setCanManageTenant(permissions.includes("tenant:manage"));
        if (!canUse) {
          setPage(null);
          return null;
        }
        const params = new URLSearchParams();
        if (selected.query) params.set("q", selected.query);
        if (selected.scope) params.set("scope", selected.scope);
        if (selected.category) params.set("category", selected.category);
        const next = await api<MemoryPage>(`/api/v1/memory${params.size ? `?${params}` : ""}`, {
          signal,
        });
        if (signal.aborted) return null;
        if (!validPage(next)) throw new Error(t("metadataError"));
        return next;
      } catch (caught) {
        if (
          !signal.aborted &&
          caught instanceof ApiError &&
          [401, 403, 404].includes(caught.status)
        ) {
          setPage(null);
          setAllowed(false);
          setCanManageTenant(false);
        }
        throw caught;
      }
    },
    [t],
  );

  const load = useCallback(async () => {
    if (actionRequest.current || readRequest.current) return;
    const request = new AbortController();
    readRequest.current = request;
    setLoading(true);
    setLoadError("");
    try {
      const next = await read(request.signal, filters);
      if (request.signal.aborted) return;
      setPage(next);
      setLoadedFilters(filters);
      setIssue(null);
    } catch (caught) {
      if (!request.signal.aborted) setLoadError(caught instanceof Error ? caught : t("error"));
    } finally {
      if (readRequest.current === request) {
        readRequest.current = null;
        setLoading(false);
      }
    }
  }, [filters, read, t]);
  useEffect(() => {
    void load();
    return () => {
      readRequest.current?.abort();
      readRequest.current = null;
    };
  }, [load]);

  function choose(next: boolean) {
    setAdvanced(next);
    if (next) setAdvancedOpened(true);
    else {
      setScope("");
      setCategory("");
    }
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }
  async function change(operation: Operation) {
    if (held || readRequest.current || actionRequest.current || !page) return;
    if (
      (operation.kind === "add" || operation.kind === "edit") &&
      (!nonempty(storedText(operation.content)) || count(operation.content) > CONTENT_LIMIT)
    )
      return;
    if (
      (operation.kind === "edit" || operation.kind === "delete") &&
      (!editable(operation.fact) || !nonempty(operation.fact.id))
    )
      return;
    const request = new AbortController();
    actionRequest.current = request;
    setPhase({ kind: operation.kind, id: "fact" in operation ? operation.fact.id : undefined });
    setNotice("");
    let accepted = false;
    try {
      if (operation.kind === "toggle") {
        const result = await api<{ memoryEnabled?: boolean }>("/api/v1/memory/settings", {
          method: "PATCH",
          signal: request.signal,
          body: JSON.stringify({ enabled: operation.enabled }),
        });
        if (request.signal.aborted) return;
        if (result?.memoryEnabled !== operation.enabled)
          throw new Error(t("preferenceUnconfirmed"));
        setPage((current) =>
          current ? { ...current, memoryEnabled: operation.enabled } : current,
        );
      } else if (operation.kind === "delete") {
        const result = await api<{ deleted?: boolean }>(
          `/api/v1/memory/${encodeURIComponent(operation.fact.id)}`,
          { method: "DELETE", signal: request.signal },
        );
        if (request.signal.aborted) return;
        if (result?.deleted !== true) throw new Error(t("deleteUnconfirmed"));
      } else {
        const endpoint =
          operation.kind === "add"
            ? "/api/v1/memory"
            : `/api/v1/memory/${encodeURIComponent(operation.fact.id)}`;
        const result = await api<Fact>(endpoint, {
          method: operation.kind === "add" ? "POST" : "PATCH",
          signal: request.signal,
          body: JSON.stringify(
            operation.kind === "add"
              ? { content: operation.content, scope: "user" }
              : { content: operation.content },
          ),
        });
        if (request.signal.aborted) return;
        if (
          !validFact(result) ||
          result.content !== storedText(operation.content) ||
          (operation.kind === "add"
            ? result.scope !== "user"
            : result.id !== operation.fact.id ||
              result.scope !== operation.fact.scope ||
              result.agent?.id !== operation.fact.agent?.id)
        )
          throw new Error(t("saveUnconfirmed"));
        if (operation.kind === "add")
          setContent((current) => (current === operation.content ? "" : current));
        else
          setEditor((current) =>
            current?.fact.id === operation.fact.id && current.content === operation.content
              ? null
              : current,
          );
      }
      accepted = true;
      setNotice(
        t(
          operation.kind === "toggle"
            ? "preferenceSaved"
            : operation.kind === "delete"
              ? "deleted"
              : "saved",
        ),
      );
      const selected = currentFilters.current;
      const next = await read(request.signal, selected);
      if (request.signal.aborted) return;
      if (filterKey(selected) !== filterKey(currentFilters.current))
        throw new Error(t("filtersChanged"));
      setPage(next);
      setLoadedFilters(selected);
    } catch (caught) {
      if (!request.signal.aborted)
        setIssue({ accepted, error: caught instanceof Error ? caught : t("error") });
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setPhase(null);
      }
    }
  }
  function counter(value: string) {
    return t("contentCount", {
      count: formatCount(count(value)),
      limit: formatCount(CONTENT_LIMIT),
    });
  }

  return (
    <AppShell>
      <fieldset disabled={busy} className="min-w-0">
        <PageHeader
          title={t("title")}
          body={t("body")}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <fieldset disabled={issue !== null} className="min-w-0">
                <SettingsMode advanced={advanced} onChange={choose} />
              </fieldset>
              <Button
                type="button"
                variant="outline"
                disabled={loading || busy}
                aria-label={t("refresh")}
                onClick={() => void load()}
              >
                <RefreshCw size={16} aria-hidden="true" />
              </Button>
            </div>
          }
        />
        <DetailState
          loading={loading && page === null}
          error={loadError}
          onRetry={loading || busy ? undefined : () => void load()}
        />
        {allowed === false ? <p className="mb-5 text-sm">{t("readDenied")}</p> : null}
        {issue ? (
          <div
            ref={feedback}
            tabIndex={-1}
            className="mb-5 space-y-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-sm"
            role="alert"
          >
            <p>{t(issue.accepted ? "acceptedRecovery" : "recovery")}</p>
            <ErrorMessage error={issue.error} />
          </div>
        ) : null}
        <ActionStatus
          busy={busy || loading}
          busyLabel={t(busy ? `progress.${phase?.kind}` : "loading")}
          notice={notice}
        />
        {page && allowed ? (
          <ManagementLayout
            title={t("listTitle")}
            formTitle={t("createTitle")}
            form={
              <>
                <label className="mb-4 flex items-start gap-2 text-sm">
                  <input
                    checked={page.memoryEnabled}
                    disabled={held}
                    className="mt-1"
                    onChange={(event) =>
                      void change({ kind: "toggle", enabled: event.target.checked })
                    }
                    type="checkbox"
                  />
                  <span>
                    <span className="block font-medium">{t("enabled")}</span>
                    <span className="mt-1 block text-xs leading-relaxed text-[var(--muted-foreground)]">
                      {t("personalHelp")}
                    </span>
                  </span>
                </label>
                <form
                  className="grid gap-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void change({ kind: "add", content });
                  }}
                >
                  <label className="text-sm" htmlFor="memory-content">
                    {t("content")}
                  </label>
                  <textarea
                    className="min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                    required
                    maxLength={CONTENT_LIMIT * 2}
                    disabled={held}
                    id="memory-content"
                    aria-describedby={`memory-create-help memory-create-count${count(content) > CONTENT_LIMIT ? " memory-create-error" : ""}`}
                    aria-invalid={count(content) > CONTENT_LIMIT}
                    onChange={(event) => {
                      setContent(event.target.value);
                      setNotice("");
                    }}
                    value={content}
                  />
                  <p
                    id="memory-create-help"
                    className="text-xs leading-relaxed text-[var(--muted-foreground)]"
                  >
                    {t("createHelp")}
                  </p>
                  <p id="memory-create-count" className="text-xs text-[var(--muted-foreground)]">
                    {counter(content)}
                  </p>
                  {count(content) > CONTENT_LIMIT ? (
                    <p id="memory-create-error" className="text-sm text-[var(--destructive)]">
                      {t("contentTooLong")}
                    </p>
                  ) : null}
                  <Button
                    className="justify-self-start"
                    disabled={
                      held || !nonempty(storedText(content)) || count(content) > CONTENT_LIMIT
                    }
                    type="submit"
                  >
                    {t(phase?.kind === "add" ? "progress.add" : "save")}
                  </Button>
                </form>
              </>
            }
          >
            <form
              className="mb-4 grid gap-2 sm:flex sm:flex-wrap sm:items-end"
              onSubmit={(event) => {
                event.preventDefault();
                setSearch(query.trim());
              }}
            >
              <label className="min-w-0 sm:flex-1 text-sm" htmlFor="memory-search">
                <span className="sr-only">{t("search")}</span>
                <Input
                  id="memory-search"
                  type="search"
                  disabled={busy || issue !== null}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={t("search")}
                  value={query}
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <Button type="submit" variant="outline" disabled={busy || issue !== null}>
                  {t("searchAction")}
                </Button>
                {filtered || query ? (
                  <Button
                    type="button"
                    variant="outline"
                    disabled={busy || issue !== null}
                    onClick={() => {
                      setQuery("");
                      setSearch("");
                      setScope("");
                      setCategory("");
                    }}
                  >
                    {t("clearFilters")}
                  </Button>
                ) : null}
              </div>
            </form>
            {advanced ? (
              <div className="mb-4 flex flex-wrap gap-3">
                <label className="text-sm" htmlFor="memory-scope">
                  {t("scope")}
                  <select
                    id="memory-scope"
                    className="ml-2 h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
                    disabled={issue !== null}
                    value={scope}
                    onChange={(event) => setScope(event.target.value)}
                  >
                    <option value="">{t("all")}</option>
                    {["user", "workspace", "agent_user"].map((value) => (
                      <option key={value} value={value}>
                        {scopeLabel(value)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm" htmlFor="memory-category">
                  {t("category")}
                  <select
                    id="memory-category"
                    className="ml-2 h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
                    disabled={issue !== null}
                    value={category}
                    onChange={(event) => setCategory(event.target.value)}
                  >
                    <option value="">{t("all")}</option>
                    {["preference", "fact", "instruction", "lesson"].map((value) => (
                      <option key={value} value={value}>
                        {categoryLabel(value)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            ) : null}
            {loadedFilters?.query ? (
              <p className="mb-3 break-words text-xs text-[var(--muted-foreground)]">
                {t("submittedSearch", { query: loadedFilters.query })}
              </p>
            ) : null}
            {loading || !loadedFilters || filterKey(loadedFilters) !== filterKey(filters) ? (
              <p className="mb-3 text-sm text-[var(--muted-foreground)]">
                {t("refreshingResults")}
              </p>
            ) : null}
            {editor ? (
              <section
                aria-label={t("editTitle")}
                className="mb-5 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
              >
                <h3 className="mb-3 text-sm font-medium">{t("editTitle")}</h3>
                <form
                  className="grid gap-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void change({ kind: "edit", fact: editor.fact, content: editor.content });
                  }}
                >
                  <label className="text-sm" htmlFor="memory-edit-content">
                    {t("editContent")}
                  </label>
                  <textarea
                    id="memory-edit-content"
                    ref={editField}
                    className="min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                    maxLength={CONTENT_LIMIT * 2}
                    required
                    disabled={held}
                    aria-describedby={`memory-edit-count${count(editor.content) > CONTENT_LIMIT ? " memory-edit-error" : ""}`}
                    aria-invalid={count(editor.content) > CONTENT_LIMIT}
                    value={editor.content}
                    onChange={(event) => {
                      const value = event.target.value;
                      setEditor((current) => (current ? { ...current, content: value } : null));
                      setNotice("");
                    }}
                  />
                  <p id="memory-edit-count" className="text-xs text-[var(--muted-foreground)]">
                    {counter(editor.content)}
                  </p>
                  {count(editor.content) > CONTENT_LIMIT ? (
                    <p id="memory-edit-error" className="text-sm text-[var(--destructive)]">
                      {t("contentTooLong")}
                    </p>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <Button
                      disabled={
                        held ||
                        !nonempty(storedText(editor.content)) ||
                        count(editor.content) > CONTENT_LIMIT
                      }
                      type="submit"
                    >
                      {t(phase?.kind === "edit" ? "progress.edit" : "saveChanges")}
                    </Button>
                    <Button
                      variant="outline"
                      disabled={busy}
                      type="button"
                      onClick={() => setEditor(null)}
                    >
                      {t("cancel")}
                    </Button>
                  </div>
                </form>
              </section>
            ) : null}
            {!loading && !loadError && page.items.length === 0 ? (
              <EmptyState title={filtered ? t("noMatches") : t("empty")} />
            ) : null}
            <ul className="row-list max-w-3xl">
              {pagination.rows.map((row) => (
                <li className="p-4" key={row.id}>
                  <p className="whitespace-pre-wrap break-words text-sm">{row.content}</p>
                  <p className="mt-1 break-words text-xs text-[var(--muted-foreground)]">
                    {[
                      categoryLabel(row.category),
                      scopeLabel(row.scope),
                      row.agent?.name || row.agent?.id,
                      row.status === "pending_review" ? t("pending") : "",
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  {editable(row) ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        disabled={held}
                        id={`edit-memory-${row.id}`}
                        aria-label={t("editNamed", { reference: row.id })}
                        onClick={() => {
                          setEditor({ fact: row, content: row.content });
                          setNotice("");
                        }}
                      >
                        {t("edit")}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        disabled={held}
                        aria-label={t("deleteNamed", { reference: row.id })}
                        onClick={() => void change({ kind: "delete", fact: row })}
                      >
                        {t(
                          phase?.kind === "delete" && phase.id === row.id
                            ? "progress.delete"
                            : "delete",
                        )}
                      </Button>
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                      {t("readOnlyFact")}
                    </p>
                  )}
                </li>
              ))}
            </ul>
            {page.items.length ? <ListPagination {...pagination} label={t("listTitle")} /> : null}
            <p className="mt-5 text-xs leading-relaxed text-[var(--muted-foreground)]">
              {t("individualHelp")}
            </p>
            {page.teams.length ? (
              <SharedMemories teams={page.teams} categoryLabel={categoryLabel} />
            ) : null}
          </ManagementLayout>
        ) : null}
      </fieldset>
      {advancedOpened && canManageTenant ? (
        <div hidden={!advanced}>
          <OrganisationMemorySettings />
        </div>
      ) : null}
    </AppShell>
  );
}

function SharedMemories({
  teams,
  categoryLabel,
}: {
  teams: Team[];
  categoryLabel: (value: string) => string;
}) {
  const t = useTranslations("memory");
  const [query, setQuery] = useState("");
  const facts = useMemo(
    () =>
      teams.flatMap((team) =>
        team.items.map((fact) => ({ ...fact, teamId: team.id, teamName: team.name })),
      ),
    [teams],
  );
  const filtered = useMemo(
    () =>
      facts.filter((row) =>
        [row.content, row.category, row.teamName].some((value) =>
          value.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
        ),
      ),
    [facts, query],
  );
  const pagination = usePagedRows(filtered, query);
  return (
    <section className="mt-8" aria-label={t("shared")}>
      <h2 className="mb-3 text-base font-semibold">{t("shared")}</h2>
      {facts.length > 0 ? (
        <Input
          type="search"
          aria-label={t("searchShared")}
          placeholder={t("searchShared")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="mb-4 max-w-xl"
        />
      ) : null}
      {filtered.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">
          {query ? t("noMatches") : t("teamEmpty")}
        </p>
      ) : null}
      <ul className="row-list max-w-3xl">
        {pagination.rows.map((row) => (
          <li className="p-4" key={`${row.teamId}:${row.id}`}>
            <p className="whitespace-pre-wrap break-words text-sm">{row.content}</p>
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">
              {row.teamName} · {categoryLabel(row.category)}
            </p>
          </li>
        ))}
      </ul>
      {facts.length > 0 ? <ListPagination {...pagination} label={t("shared")} /> : null}
    </section>
  );
}
