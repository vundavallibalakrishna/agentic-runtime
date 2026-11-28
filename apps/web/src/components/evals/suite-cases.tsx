"use client";

import { useTranslations } from "next-intl";
import { type ComponentProps, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DetailState, ErrorMessage } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError, api, type DisplayError, type Session } from "@/lib/api";
import { formatDataValue } from "@/lib/format";
import { casesFrom, caseValid, type SavedCase, sameCase } from "./case-data";
import { CaseReceipt } from "./case-details";

type Attempt = { state: "refused" | "unknown" | "acknowledged" | "confirmed"; saved?: SavedCase };
type Props = {
  suiteId: string;
  initialName?: string;
  initialTab: "cases" | "add";
  onClose: () => void;
  onSaved: () => void;
  onAccessLost: (error: DisplayError) => void;
  onCloseAutoFocus?: ComponentProps<typeof DialogContent>["onCloseAutoFocus"];
};
const scopeOf = (session: Session) =>
  JSON.stringify([
    session.tenant?.id ?? session.tenant?.slug ?? null,
    session.user?.id ?? session.user?.email ?? null,
  ]);
const denied = (error: unknown) =>
  error instanceof ApiError &&
  (error.status === 401 || (error.status === 403 && error.code !== "csrf_failed"));
export function SuiteCases(props: Props) {
  const t = useTranslations("evals");
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) props.onClose();
      }}
    >
      <DialogContent
        title={t("viewCasesFor", { name: props.initialName || props.suiteId })}
        onCloseAutoFocus={props.onCloseAutoFocus}
        footer={
          <div className="flex justify-end">
            <Button type="button" variant="outline" onClick={props.onClose}>
              {t("close")}
            </Button>
          </div>
        }
      >
        <CaseWorkspace key={props.suiteId} {...props} />
      </DialogContent>
    </Dialog>
  );
}
function CaseWorkspace({
  suiteId,
  initialName,
  initialTab,
  onClose,
  onSaved,
  onAccessLost,
}: Props) {
  const t = useTranslations("evals");
  const callbacks = useRef({ onClose, onSaved, onAccessLost });
  callbacks.current = { onClose, onSaved, onAccessLost };
  const [tab, setTab] = useState<string>(initialTab),
    [suiteName, setSuiteName] = useState("");
  const [rows, setRows] = useState<SavedCase[]>([]),
    [loaded, setLoaded] = useState(false),
    [loading, setLoading] = useState(true),
    [allowed, setAllowed] = useState(false);
  const [error, setError] = useState<DisplayError>(""),
    [saveError, setSaveError] = useState<DisplayError>(""),
    [notice, setNotice] = useState("");
  const [name, setName] = useState(""),
    [prompt, setPrompt] = useState(""),
    [expected, setExpected] = useState(""),
    [matchCase, setMatchCase] = useState(false);
  const [query, setQuery] = useState(""),
    [kind, setKind] = useState("");
  const [attempt, setAttempt] = useState<Attempt | null>(null),
    [saving, setSaving] = useState(false);
  const attemptRef = useRef(attempt);
  attemptRef.current = attempt;
  const operation = useRef<AbortController | null>(null),
    owner = useRef<string | null>(null),
    notified = useRef<string | null>(null);
  const search = useRef<HTMLInputElement>(null),
    nameInput = useRef<HTMLInputElement>(null),
    alert = useRef<HTMLDivElement>(null);
  const focusForm = useRef(initialTab === "add"),
    focusSearch = useRef(initialTab === "cases");
  const formInputRef = useCallback((element: HTMLInputElement | null) => {
    nameInput.current = element;
    if (element && focusForm.current) {
      focusForm.current = false;
      element.focus();
    }
  }, []);
  const searchInputRef = useCallback((element: HTMLInputElement | null) => {
    search.current = element;
    if (element && focusSearch.current) {
      focusSearch.current = false;
      element.focus();
    }
  }, []);
  const clearProtected = useCallback((message: DisplayError) => {
    setRows([]);
    setLoaded(false);
    setAllowed(false);
    setName("");
    setPrompt("");
    setExpected("");
    setAttempt(null);
    setNotice("");
    callbacks.current.onAccessLost(message);
  }, []);
  const sessionFor = useCallback(
    async function sessionFor(controller: AbortController) {
      const session = await api<Session>("/api/v1/auth/session", { signal: controller.signal });
      if (controller.signal.aborted) return false;
      const scope = scopeOf(session);
      if (owner.current && owner.current !== scope) {
        clearProtected(t("sessionChanged"));
        return false;
      }
      owner.current = scope;
      if (!session.permissions?.includes("evals:manage")) {
        clearProtected(t("denied"));
        return false;
      }
      return true;
    },
    [clearProtected, t],
  );
  const verified = useCallback(
    function verified(saved: SavedCase) {
      setAttempt({ state: "confirmed", saved });
      setNotice(t("saved"));
      setSaveError("");
      if (notified.current !== saved.id) {
        notified.current = saved.id;
        callbacks.current.onSaved();
      }
    },
    [t],
  );
  const load = useCallback(async () => {
    if (operation.current) return;
    const controller = new AbortController();
    operation.current = controller;
    const active = () => operation.current === controller && !controller.signal.aborted;
    setLoading(true);
    setSaving(false);
    try {
      if (!(await sessionFor(controller)) || !active()) return;
      const [suiteRead, caseRead] = await Promise.allSettled([
        api<{ id?: string; name?: string }>(`/api/v1/eval-suites/${encodeURIComponent(suiteId)}`, {
          signal: controller.signal,
        }),
        api<{ items?: unknown }>(`/api/v1/eval-suites/${encodeURIComponent(suiteId)}/cases`, {
          signal: controller.signal,
        }),
      ]);
      if (!active()) return;
      if (suiteRead.status === "rejected") throw suiteRead.reason;
      if (caseRead.status === "rejected") throw caseRead.reason;
      const suite = suiteRead.value,
        page = caseRead.value;
      if (suite?.id !== suiteId || typeof suite.name !== "string" || !suite.name.trim())
        throw new Error(t("caseSuiteMetadata"));
      const next = casesFrom(page, suiteId, t("copyCaseMetadata"));
      setSuiteName(suite.name);
      setRows(next);
      setLoaded(true);
      setAllowed(true);
      setError("");
      const previous = attemptRef.current;
      if (previous?.saved) {
        const found = next.find((value) => value.id === previous.saved?.id);
        if (found && sameCase(found, previous.saved)) verified(found);
        else setSaveError(t("copyNotVerified"));
      } else if (previous?.state === "refused") {
        setAttempt(null);
        setSaveError("");
        setNotice(t("caseChecked"));
      } else if (previous?.state === "unknown") setNotice(t("caseUnknownChecked"));
    } catch (caught) {
      if (!active()) return;
      if (denied(caught)) {
        clearProtected(caught instanceof Error ? caught : t("denied"));
        return;
      }
      setError(caught instanceof Error ? caught : t("error"));
    } finally {
      if (active()) {
        operation.current = null;
        setLoading(false);
      }
    }
  }, [clearProtected, sessionFor, verified, suiteId, t]);
  useEffect(() => {
    void load();
    return () => {
      operation.current?.abort();
      operation.current = null;
    };
  }, [load]);
  useEffect(() => {
    if (saveError) alert.current?.focus();
  }, [saveError]);
  const indexed = useMemo(
    () =>
      rows.map((row) => ({
        row,
        search: [row.name, row.id, formatDataValue(row.input), formatDataValue(row.assertions)]
          .join(" ")
          .toLocaleLowerCase(),
      })),
    [rows],
  );
  const matching = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return indexed
      .filter(
        (item) =>
          (!kind || item.row.assertions.some((value) => value.type === kind)) &&
          (!term || item.search.includes(term)),
      )
      .map((item) => item.row);
  }, [indexed, query, kind]);
  const kinds = useMemo(
    () =>
      [
        ...new Set([
          kind,
          ...rows.flatMap((row) => row.assertions.map((value) => String(value.type))),
        ]),
      ]
        .filter(Boolean)
        .sort(),
    [rows, kind],
  );
  const pagination = usePagedRows(matching, JSON.stringify([query, kind]));
  async function save() {
    if (
      operation.current ||
      !allowed ||
      !loaded ||
      attempt ||
      !name.trim() ||
      !prompt.trim() ||
      !expected.trim()
    )
      return;
    const snapshot = { name: name.trim(), prompt, expected, matchCase },
      controller = new AbortController();
    operation.current = controller;
    setSaving(true);
    setSaveError("");
    setNotice("");
    const active = () => operation.current === controller && !controller.signal.aborted;
    let sent = false;
    try {
      if (!(await sessionFor(controller)) || !active()) return;
      sent = true;
      setAttempt({ state: "unknown" });
      const saved = await api<unknown>(`/api/v1/eval-suites/${encodeURIComponent(suiteId)}/cases`, {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          name: snapshot.name,
          input: { messages: [snapshot.prompt] },
          assertions: [
            { type: "contains", value: snapshot.expected, caseSensitive: snapshot.matchCase },
          ],
        }),
      });
      if (!active()) return;
      if (
        !caseValid(saved, suiteId) ||
        saved.name !== snapshot.name ||
        saved.input.messages.length !== 1 ||
        saved.input.messages[0] !== snapshot.prompt ||
        saved.assertions.length !== 1 ||
        saved.assertions[0]?.type !== "contains" ||
        saved.assertions[0]?.value !== snapshot.expected ||
        saved.assertions[0]?.caseSensitive !== snapshot.matchCase
      )
        throw new Error(t("copyCaseMetadata"));
      setAttempt({ state: "acknowledged", saved });
      const page = await api<{ items?: unknown }>(
        `/api/v1/eval-suites/${encodeURIComponent(suiteId)}/cases`,
        { signal: controller.signal },
      );
      if (!active()) return;
      const next = casesFrom(page, suiteId, t("copyCaseMetadata"));
      setRows(next);
      const found = next.find((value) => value.id === saved.id);
      if (!found || !sameCase(found, saved)) throw new Error(t("copyNotVerified"));
      verified(found);
    } catch (caught) {
      if (!active()) return;
      if (denied(caught)) {
        clearProtected(caught instanceof Error ? caught : t("denied"));
        return;
      }
      if (sent)
        setAttempt((previous) =>
          previous?.saved
            ? previous
            : {
                state:
                  caught instanceof ApiError &&
                  caught.status === 403 &&
                  caught.code === "csrf_failed"
                    ? "refused"
                    : "unknown",
              },
        );
      setSaveError(caught instanceof Error ? caught : t("error"));
    } finally {
      if (active()) {
        operation.current = null;
        setSaving(false);
      }
    }
  }
  return (
    <div className="mt-4 space-y-4">
      {loaded && suiteName !== initialName ? (
        <p className="break-words text-sm font-medium">{suiteName}</p>
      ) : null}
      <p className="break-all text-xs text-[var(--muted-foreground)]">
        {t("suiteReference", { id: suiteId })}
      </p>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-[var(--muted-foreground)]">{t("caseWorkspaceHelp")}</p>
        <Button
          type="button"
          variant="outline"
          disabled={loading || saving}
          onClick={() => void load()}
        >
          {t("copyRefresh")}
        </Button>
      </div>
      {loaded && (loading || error) ? (
        <p role="status" className="text-sm text-[var(--muted-foreground)]">
          {t(loading ? "refreshing" : "casesRetained")}
        </p>
      ) : null}
      <DetailState loading={loading && !loaded} error={error} onRetry={() => void load()} />
      {loaded && allowed ? (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="cases" disabled={saving}>
              {t("cases")}
            </TabsTrigger>
            <TabsTrigger value="add" disabled={saving}>
              {t("addCase")}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="cases">
            <fieldset
              aria-label={t("caseFilters")}
              className="mb-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem]"
            >
              <Input
                ref={searchInputRef}
                type="search"
                aria-label={t("caseSearch")}
                placeholder={t("caseSearch")}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <label className="text-sm">
                <span className="sr-only">{t("assertionType")}</span>
                <select
                  aria-label={t("assertionType")}
                  className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
                  value={kind}
                  onChange={(event) => setKind(event.target.value)}
                >
                  <option value="">{t("allAssertions")}</option>
                  {kinds.map((value) => (
                    <option key={value} value={value}>
                      {t.has(`assertionTypes.${value}`) ? t(`assertionTypes.${value}`) : value}
                    </option>
                  ))}
                </select>
              </label>
            </fieldset>
            {query || kind ? (
              <Button
                type="button"
                variant="outline"
                className="mb-4"
                onClick={() => {
                  setQuery("");
                  setKind("");
                  search.current?.focus();
                }}
              >
                {t("clearFilters")}
              </Button>
            ) : null}
            {matching.length === 0 ? (
              <EmptyState compact title={t(rows.length ? "noCaseMatches" : "noSavedCases")}>
                {rows.length === 0 ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      focusForm.current = true;
                      setTab("add");
                    }}
                  >
                    {t("addCase")}
                  </Button>
                ) : null}
              </EmptyState>
            ) : null}
            <ul className="space-y-3">
              {pagination.rows.map((row) => (
                <li key={row.id}>
                  <CaseReceipt value={row} compact />
                </li>
              ))}
            </ul>
            {rows.length > 0 ? <ListPagination {...pagination} label={t("cases")} /> : null}
          </TabsContent>
          <TabsContent value="add">
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                void save();
              }}
            >
              <p className="text-sm text-[var(--muted-foreground)]">{t("caseHelp")}</p>
              <label className="text-sm" htmlFor="eval-case-name">
                {t("caseName")}
                <Input
                  ref={formInputRef}
                  disabled={saving}
                  className="mt-1"
                  id="eval-case-name"
                  required
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
              <label className="text-sm" htmlFor="eval-case-prompt">
                {t("message")}
                <textarea
                  className="mt-1 min-h-28 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                  id="eval-case-prompt"
                  disabled={saving}
                  required
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                />
              </label>
              <label className="text-sm" htmlFor="eval-case-expect">
                {t("expect")}
                <Input
                  className="mt-1"
                  id="eval-case-expect"
                  disabled={saving}
                  required
                  value={expected}
                  onChange={(event) => setExpected(event.target.value)}
                />
              </label>
              <label className="flex items-start gap-2 text-sm">
                <input
                  className="mt-1"
                  type="checkbox"
                  disabled={saving}
                  checked={matchCase}
                  onChange={(event) => setMatchCase(event.target.checked)}
                />
                {t("matchLetterCase")}
              </label>
              {saving ? (
                <p role="status" className="text-sm">
                  {t("caseSaving")}
                </p>
              ) : null}
              {saving ? (
                <p className="text-sm text-[var(--muted-foreground)]">{t("copyCancelHelp")}</p>
              ) : null}
              {saveError ? (
                <div
                  ref={alert}
                  role="alert"
                  tabIndex={-1}
                  className="rounded-lg border border-[var(--border)] p-3 text-sm"
                >
                  <ErrorMessage error={saveError} />
                </div>
              ) : null}
              {notice ? (
                <p role="status" className="text-sm">
                  {notice}
                </p>
              ) : null}
              {attempt ? (
                <p className="text-sm text-[var(--muted-foreground)]">
                  {t(
                    attempt.state === "confirmed"
                      ? "caseConfirmed"
                      : attempt.state === "acknowledged"
                        ? "copyAcknowledged"
                        : attempt.state === "refused"
                          ? "caseRefused"
                          : "caseUnconfirmed",
                  )}
                </p>
              ) : null}
              {attempt?.saved ? <CaseReceipt value={attempt.saved} /> : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  type="submit"
                  disabled={
                    saving ||
                    loading ||
                    Boolean(attempt) ||
                    !name.trim() ||
                    !prompt.trim() ||
                    !expected.trim()
                  }
                >
                  {t("saveCase")}
                </Button>
                {attempt?.state === "confirmed" ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setAttempt(null);
                      setName("");
                      setPrompt("");
                      setExpected("");
                      setMatchCase(false);
                      setNotice("");
                      setSaveError("");
                      nameInput.current?.focus();
                    }}
                  >
                    {t("anotherCase")}
                  </Button>
                ) : null}
              </div>
            </form>
          </TabsContent>
        </Tabs>
      ) : null}
    </div>
  );
}
