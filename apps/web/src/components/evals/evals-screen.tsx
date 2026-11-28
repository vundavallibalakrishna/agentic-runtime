"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { BackButton, DetailState, ErrorMessage } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TableScroll } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError, api, type DisplayError, type Session } from "@/lib/api";
import { formatDataValue } from "@/lib/format";
import { EvalFeedbackPanel } from "./feedback-panel";
import { EvalRunHistory } from "./run-history";
import { RunSetup } from "./run-setup";
import { SuiteCases } from "./suite-cases";
import {
  decimalNumber,
  fromRate,
  type Gate,
  gateFields,
  matchesSuite,
  type Suite,
  sameSuite,
  suitesFrom,
  suiteValid,
  toRate,
} from "./suite-data";

type Operation = { controller: AbortController; kind: "read" | "suite" | "import" };
type ImportReply = { imported?: number; errors?: { line?: number; msg?: string }[] };
type Attempt = { state: "refused" | "unknown" | "acknowledged" | "confirmed"; saved?: Suite };
const kinds = ["functional", "retrieval", "safety", "red_team"];
const selectClass =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm";
const scopeOf = (session: Session) =>
  JSON.stringify([
    session.tenant?.id ?? session.tenant?.slug ?? null,
    session.user?.id ?? session.user?.email ?? null,
  ]);
const accessLost = (error: unknown) =>
  error instanceof ApiError &&
  (error.status === 401 || (error.status === 403 && error.code !== "csrf_failed"));
export function EvalsScreen(props: { agentId?: string; admin?: boolean }) {
  return (
    <EvalsWorkspace key={`${props.admin === true}:${props.agentId ?? "workspace"}`} {...props} />
  );
}
function EvalsWorkspace({ agentId, admin = false }: { agentId?: string; admin?: boolean }) {
  const t = useTranslations("evals"),
    locale = useLocale();
  const [session, setSession] = useState<Session | null>(null),
    [suites, setSuites] = useState<Suite[]>([]),
    [loaded, setLoaded] = useState(false),
    [loading, setLoading] = useState(true),
    [pending, setPending] = useState("");
  const [error, setError] = useState<DisplayError>(""),
    [formError, setFormError] = useState<DisplayError>(""),
    [notice, setNotice] = useState(""),
    [importNotice, setImportNotice] = useState(""),
    [importError, setImportError] = useState<DisplayError>("");
  const [name, setName] = useState(""),
    [description, setDescription] = useState(""),
    [suiteKind, setSuiteKind] = useState(""),
    [gatePercent, setGatePercent] = useState(""),
    [gateRequired, setGateRequired] = useState("");
  const [regression, setRegression] = useState(""),
    [tags, setTags] = useState(""),
    [editing, setEditing] = useState<Suite | null>(null),
    [advanced, setAdvanced] = useState(false),
    [attempt, setAttempt] = useState<Attempt | null>(null);
  const [query, setQuery] = useState(""),
    [kindFilter, setKindFilter] = useState(""),
    [runStatus, setRunStatus] = useState(""),
    [tab, setTab] = useState("suites");
  const [caseSuite, setCaseSuite] = useState<Suite | null>(null),
    [caseTab, setCaseTab] = useState<"cases" | "add">("cases");
  const [selectedRun, setSelectedRun] = useState(""),
    [runSuite, setRunSuite] = useState<Suite | null>(null);
  const operation = useRef<Operation | null>(null),
    owner = useRef<string | null>(null),
    attemptRef = useRef(attempt);
  attemptRef.current = attempt;
  const nameInput = useRef<HTMLInputElement>(null),
    searchInput = useRef<HTMLInputElement>(null),
    dialogOpener = useRef<HTMLButtonElement>(null),
    editOpener = useRef<HTMLButtonElement>(null),
    formAlert = useRef<HTMLDivElement>(null);
  const canManage = session?.permissions?.includes("evals:manage") ?? false,
    canRun = session?.permissions?.includes("evals:run") ?? false,
    busy = Boolean(pending);
  const clearProtected = useCallback((message: DisplayError) => {
    operation.current?.controller.abort();
    operation.current = null;
    setSession(null);
    setSuites([]);
    setLoaded(false);
    setLoading(false);
    setPending("");
    setEditing(null);
    setCaseSuite(null);
    setRunSuite(null);
    setSelectedRun("");
    setName("");
    setDescription("");
    setGatePercent("");
    setGateRequired("");
    setRegression("");
    setTags("");
    setAttempt(null);
    setFormError("");
    setNotice("");
    setImportNotice("");
    setImportError("");
    setError(message);
  }, []);
  const authorize = useCallback(
    async (controller: AbortController) => {
      const current = await api<Session>("/api/v1/auth/session", { signal: controller.signal });
      if (controller.signal.aborted) return false;
      const scope = scopeOf(current);
      if (owner.current && owner.current !== scope) {
        clearProtected(t("sessionChanged"));
        return false;
      }
      owner.current = scope;
      if (!current.permissions?.includes("evals:manage")) {
        clearProtected(t("denied"));
        return false;
      }
      setSession(current);
      return true;
    },
    [clearProtected, t],
  );
  const load = useCallback(async () => {
    if (operation.current) return;
    const op: Operation = { kind: "read", controller: new AbortController() };
    operation.current = op;
    const active = () => operation.current === op && !op.controller.signal.aborted;
    setLoading(true);
    try {
      if (!(await authorize(op.controller)) || !active()) return;
      const params = new URLSearchParams();
      if (agentId) params.set("agent_id", agentId);
      const page = await api<{ items?: unknown }>(`/api/v1/eval-suites?${params}`, {
        signal: op.controller.signal,
      });
      if (!active()) return;
      const next = suitesFrom(page, agentId, t("suiteMetadata"));
      setSuites(next);
      setLoaded(true);
      setError("");
      const previous = attemptRef.current;
      if (previous?.saved) {
        const found = next.find((row) => row.id === previous.saved?.id);
        if (found && sameSuite(found, previous.saved)) {
          setAttempt({ state: "confirmed", saved: found });
          setFormError("");
          setNotice(t("suiteVerified"));
        } else setFormError(t("suiteNotVerified"));
      } else if (previous?.state === "refused") {
        setAttempt(null);
        setFormError("");
        setNotice(t("suiteChecked"));
      } else if (previous?.state === "unknown") setNotice(t("suiteUnknownChecked"));
    } catch (caught) {
      if (!active()) return;
      if (accessLost(caught)) {
        clearProtected(caught instanceof Error ? caught : t("denied"));
        return;
      }
      setError(caught instanceof Error ? caught : t("error"));
      if (attemptRef.current?.state === "confirmed") setNotice(t("suiteSavedListPending"));
    } finally {
      if (active()) {
        operation.current = null;
        setLoading(false);
      }
    }
  }, [agentId, authorize, clearProtected, t]);
  useEffect(() => {
    void load();
    return () => {
      operation.current?.controller.abort();
      operation.current = null;
    };
  }, [load]);
  useEffect(() => {
    setAdvanced(localStorage.getItem("ar-settings-mode") === "advanced");
  }, []);
  useEffect(() => {
    if (editing) nameInput.current?.focus();
  }, [editing]);
  useEffect(() => {
    if (formError) formAlert.current?.focus();
  }, [formError]);
  const suiteNames = useMemo(() => new Map(suites.map((row) => [row.id, row.name])), [suites]);
  const indexed = useMemo(
    () =>
      suites.map((row) => ({
        row,
        text: [row.name, row.description, row.id, row.agent?.name, row.agent?.id]
          .filter(Boolean)
          .join(" ")
          .toLocaleLowerCase(),
      })),
    [suites],
  );
  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return indexed
      .filter(
        (item) =>
          (!kindFilter || item.row.kind === kindFilter) &&
          (!runStatus ||
            runStatus ===
              JSON.stringify(item.row.lastRun ? ["status", item.row.lastRun.status] : ["none"])) &&
          (!term || item.text.includes(term)),
      )
      .map((item) => item.row);
  }, [indexed, query, kindFilter, runStatus]);
  const pagination = usePagedRows(filtered, JSON.stringify([query, kindFilter, runStatus]));
  const kindOptions = useMemo(
    () => [...new Set([kindFilter, ...suites.map((row) => row.kind)])].filter(Boolean).sort(),
    [suites, kindFilter],
  );
  const statuses = useMemo(
    () =>
      [
        ...new Set([
          runStatus,
          ...suites.map((row) =>
            JSON.stringify(row.lastRun ? ["status", row.lastRun.status] : ["none"]),
          ),
        ]),
      ]
        .filter(Boolean)
        .sort(),
    [suites, runStatus],
  );
  const kindLabel = (value: string) => (t.has(`kinds.${value}`) ? t(`kinds.${value}`) : value);
  const statusLabel = (value: string) =>
    t.has(`statuses.${value}`) ? t(`statuses.${value}`) : value;
  const percent = useMemo(
    () => new Intl.NumberFormat(locale, { style: "percent", maximumSignificantDigits: 17 }),
    [locale],
  );
  function resetForm() {
    setEditing(null);
    setName("");
    setDescription("");
    setSuiteKind("");
    setGatePercent("");
    setGateRequired("");
    setRegression("");
    setTags("");
    setFormError("");
    setNotice("");
    setAttempt(null);
  }
  function edit(suite: Suite, button: HTMLButtonElement) {
    editOpener.current = button;
    setEditing(suite);
    setName(suite.name);
    setDescription(suite.description);
    setSuiteKind(suite.kind);
    setGatePercent(fromRate(suite.gate.minPassRate));
    setGateRequired(String(suite.gate.required));
    setRegression(String(suite.gate.maxRegressionPct));
    setTags(JSON.stringify(suite.gate.mustPassTags, null, 2));
    setFormError("");
    setNotice("");
    setAttempt(null);
  }
  const unknownGate = Boolean(
    editing && Object.keys(editing.gate).some((key) => !gateFields.includes(key)),
  );
  const gateChanges = useMemo(() => {
    const change: Partial<Gate> = {};
    let invalid = "";
    if (gateRequired !== (editing ? String(editing.gate.required) : "")) {
      if (gateRequired === "true" || gateRequired === "false")
        change.required = gateRequired === "true";
      else if (editing) invalid = t("gateExplicitEdit");
    }
    if (gatePercent !== (editing ? fromRate(editing.gate.minPassRate) : "")) {
      if (gatePercent.trim()) {
        const rate = toRate(gatePercent);
        if (rate === null) invalid = t("invalidThreshold");
        else change.minPassRate = rate;
      } else if (editing) invalid = t("gateExplicitEdit");
    }
    if (regression !== (editing ? String(editing.gate.maxRegressionPct) : "")) {
      if (regression.trim()) {
        const value = decimalNumber(regression);
        if (value === null) invalid = t("invalidRegression");
        else change.maxRegressionPct = value;
      } else if (editing) invalid = t("gateExplicitEdit");
    }
    if (tags !== (editing ? JSON.stringify(editing.gate.mustPassTags, null, 2) : "")) {
      if (tags.trim()) {
        try {
          const value: unknown = JSON.parse(tags);
          if (!Array.isArray(value) || !value.every((value) => typeof value === "string"))
            invalid = t("invalidGateTags");
          else change.mustPassTags = value;
        } catch {
          invalid = t("invalidGateTags");
        }
      } else if (editing) invalid = t("gateExplicitEdit");
    }
    if (unknownGate && Object.keys(change).length) invalid = t("unknownGateEdit");
    return { change, invalid };
  }, [gateRequired, gatePercent, regression, tags, editing, unknownGate, t]);
  const body = useMemo(() => {
    const value: Record<string, unknown> = editing
      ? {}
      : { name: name.trim(), agentId: agentId ?? null };
    if (editing && name.trim() !== editing.name) value.name = name.trim();
    if (description !== (editing?.description ?? "")) value.description = description;
    if (suiteKind !== (editing?.kind ?? "")) {
      if (suiteKind) value.kind = suiteKind;
    }
    if (Object.keys(gateChanges.change).length)
      value.gate = { ...(editing?.gate ?? {}), ...gateChanges.change };
    return value;
  }, [name, description, suiteKind, editing, agentId, gateChanges]);
  const dirty = editing ? Object.keys(body).length > 0 : true,
    hiddenChanges = !advanced && Object.keys(gateChanges.change).length > 0;
  async function createSuite() {
    if (operation.current || !canManage || !loaded || attempt || !name.trim() || !dirty) return;
    if (gateChanges.invalid) {
      setFormError(gateChanges.invalid);
      return;
    }
    const original = editing,
      snapshot = body,
      op: Operation = { kind: "suite", controller: new AbortController() };
    operation.current = op;
    const active = () => operation.current === op && !op.controller.signal.aborted;
    setPending("suite");
    setFormError("");
    setNotice("");
    let sent = false;
    try {
      if (!(await authorize(op.controller)) || !active()) return;
      if (original) {
        const current = await api<unknown>(
          `/api/v1/eval-suites/${encodeURIComponent(original.id)}`,
          { signal: op.controller.signal },
        );
        if (!active()) return;
        if (!suiteValid(current, agentId) || !sameSuite(current, original))
          throw new Error(t("suiteChanged"));
      }
      sent = true;
      setAttempt({ state: "unknown" });
      const saved = await api<unknown>(
        original ? `/api/v1/eval-suites/${encodeURIComponent(original.id)}` : "/api/v1/eval-suites",
        {
          method: original ? "PATCH" : "POST",
          signal: op.controller.signal,
          body: JSON.stringify(snapshot),
        },
      );
      if (!active()) return;
      if (!suiteValid(saved, agentId) || !matchesSuite(saved, snapshot, original, agentId))
        throw new Error(t("suiteReceipt"));
      setAttempt({ state: "acknowledged", saved });
      const checked = await api<unknown>(`/api/v1/eval-suites/${encodeURIComponent(saved.id)}`, {
        signal: op.controller.signal,
      });
      if (!active()) return;
      if (!suiteValid(checked, agentId) || !sameSuite(checked, saved))
        throw new Error(t("suiteNotVerified"));
      setAttempt({ state: "confirmed", saved: checked });
      setSuites((previous) =>
        previous.some((row) => row.id === checked.id)
          ? previous.map((row) => (row.id === checked.id ? checked : row))
          : [checked, ...previous],
      );
      setNotice(t(original ? "suiteUpdated" : "suiteSaved"));
    } catch (caught) {
      if (!active()) return;
      if (accessLost(caught)) {
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
      setFormError(caught instanceof Error ? caught : t("error"));
    } finally {
      if (active()) {
        operation.current = null;
        setPending("");
      }
    }
  }
  async function importCases(suite: Suite, file: File) {
    if (operation.current || !canManage) return;
    const op: Operation = { kind: "import", controller: new AbortController() };
    operation.current = op;
    const active = () => operation.current === op && !op.controller.signal.aborted;
    setPending("import");
    setImportNotice("");
    setImportError("");
    let imported = false;
    try {
      if (!(await authorize(op.controller)) || !active()) return;
      const reply = await api<ImportReply>(
        `/api/v1/eval-suites/${encodeURIComponent(suite.id)}/cases:import`,
        {
          method: "POST",
          signal: op.controller.signal,
          body: JSON.stringify({ content: await file.text() }),
        },
      );
      if (!active()) return;
      const errors = Array.isArray(reply?.errors) ? reply.errors : [];
      const count = reply?.imported ?? 0;
      setImportNotice(
        errors.length > 0
          ? t("importedWithErrors", {
              count,
              errors: errors.length,
              first: `${errors[0]?.line ?? ""}: ${errors[0]?.msg ?? ""}`,
            })
          : t("imported", { count }),
      );
      imported = true;
    } catch (caught) {
      if (!active()) return;
      if (accessLost(caught)) {
        clearProtected(caught instanceof Error ? caught : t("denied"));
        return;
      }
      setImportError(caught instanceof Error ? caught : t("error"));
    } finally {
      if (active()) {
        operation.current = null;
        setPending("");
      }
    }
    // The case counts changed, so read the list again.
    if (imported) await load();
  }
  return (
    <AppShell>
      <PageHeader
        title={t(admin ? "adminTitle" : "title")}
        body={t(admin ? "adminBody" : "body")}
        actions={
          <>
            <Button
              type="button"
              variant="outline"
              disabled={loading || busy}
              onClick={() => void load()}
            >
              {t("refresh")}
            </Button>
            <BackButton href={agentId ? `/agents/${agentId}` : "/chat"}>{t("back")}</BackButton>
          </>
        }
      />
      {!canManage ? (
        <DetailState loading={loading} error={error} onRetry={() => void load()} />
      ) : (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="suites" disabled={busy}>
              {t("suites")}
            </TabsTrigger>
            <TabsTrigger value="runs" disabled={busy}>
              {t("runHistory")}
            </TabsTrigger>
            {admin ? (
              <TabsTrigger value="feedback" disabled={busy}>
                {t("feedback")}
              </TabsTrigger>
            ) : null}
          </TabsList>
          <TabsContent value="suites">
            <div className="mb-4 flex flex-wrap justify-end gap-3">
              <Button
                type="button"
                className="xl:hidden"
                disabled={!loaded || busy}
                variant="outline"
                onClick={() => {
                  nameInput.current?.focus();
                  nameInput.current?.scrollIntoView?.({ block: "center" });
                }}
              >
                {t("openSuiteForm")}
              </Button>
            </div>
            <ManagementLayout
              title={t("suites")}
              formTitle={t(editing ? "editSuite" : "create")}
              form={
                <form
                  className="grid gap-4"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void createSuite();
                  }}
                >
                  <p className="text-sm text-[var(--muted-foreground)]">
                    {t(editing ? "editSuiteHelp" : "createHelp")}
                  </p>
                  {editing ? (
                    <p className="break-all text-xs text-[var(--muted-foreground)]">
                      {t("suiteReference", { id: editing.id })}
                    </p>
                  ) : null}
                  <fieldset disabled={!loaded || busy} className="grid min-w-0 gap-4">
                    <label className="text-sm" htmlFor="suite-name">
                      {t("name")}
                      <Input
                        ref={nameInput}
                        id="suite-name"
                        className="mt-1"
                        required
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                      />
                    </label>
                    <label className="text-sm" htmlFor="suite-description">
                      {t("suiteDescription")}
                      <textarea
                        id="suite-description"
                        className="mt-1 min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                        value={description}
                        onChange={(event) => setDescription(event.target.value)}
                      />
                    </label>
                    <label className="text-sm" htmlFor="suite-kind">
                      {t("kind")}
                      <select
                        id="suite-kind"
                        className={`mt-1 ${selectClass}`}
                        value={suiteKind}
                        onChange={(event) => setSuiteKind(event.target.value)}
                      >
                        {!editing ? <option value="">{t("inheritDefault")}</option> : null}
                        {[...new Set([...kinds, ...(suiteKind ? [suiteKind] : [])])].map(
                          (value) => (
                            <option key={value} value={value}>
                              {kindLabel(value)}
                            </option>
                          ),
                        )}
                      </select>
                    </label>
                  </fieldset>
                  <SettingsMode
                    advanced={advanced}
                    onChange={(value) => {
                      setAdvanced(value);
                      localStorage.setItem("ar-settings-mode", value ? "advanced" : "simple");
                    }}
                  />
                  {!advanced ? (
                    <p className="text-sm text-[var(--muted-foreground)]">
                      {t(
                        hiddenChanges
                          ? "gateHiddenChanges"
                          : editing
                            ? "gatePreserved"
                            : "gateInherited",
                      )}
                    </p>
                  ) : (
                    <fieldset
                      disabled={!loaded || busy || unknownGate}
                      className="grid min-w-0 gap-4"
                    >
                      <legend className="mb-3 text-sm font-medium">{t("gate")}</legend>
                      <p className="text-sm text-[var(--muted-foreground)]">{t("gateHelp")}</p>
                      <label className="text-sm" htmlFor="suite-required">
                        {t("gateRequirement")}
                        <select
                          id="suite-required"
                          className={`mt-1 ${selectClass}`}
                          value={gateRequired}
                          onChange={(event) => setGateRequired(event.target.value)}
                        >
                          {!editing ? <option value="">{t("inheritDefault")}</option> : null}
                          <option value="true">{t("gateRequired")}</option>
                          <option value="false">{t("gateOptional")}</option>
                        </select>
                      </label>
                      <label className="text-sm" htmlFor="suite-threshold">
                        {t("threshold")}
                        <Input
                          id="suite-threshold"
                          className="mt-1"
                          inputMode="decimal"
                          value={gatePercent}
                          onChange={(event) => setGatePercent(event.target.value)}
                          placeholder={editing ? undefined : t("inheritBlank")}
                        />
                      </label>
                      <label className="text-sm" htmlFor="suite-regression">
                        {t("gateRegression")}
                        <Input
                          id="suite-regression"
                          className="mt-1"
                          inputMode="decimal"
                          value={regression}
                          onChange={(event) => setRegression(event.target.value)}
                          placeholder={editing ? undefined : t("inheritBlank")}
                        />
                      </label>
                      <div className="text-sm">
                        <label htmlFor="suite-tags">{t("gateTags")}</label>
                        <textarea
                          id="suite-tags"
                          aria-describedby="suite-tags-help"
                          className="mt-1 min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 font-mono text-xs"
                          value={tags}
                          onChange={(event) => setTags(event.target.value)}
                          placeholder={editing ? undefined : t("inheritBlank")}
                        />
                        <p
                          id="suite-tags-help"
                          className="mt-1 text-xs text-[var(--muted-foreground)]"
                        >
                          {t("gateTagsHelp")}
                        </p>
                      </div>
                      {!editing ? (
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => {
                            setGateRequired("");
                            setGatePercent("");
                            setRegression("");
                            setTags("");
                          }}
                        >
                          {t("resetGate")}
                        </Button>
                      ) : null}
                    </fieldset>
                  )}
                  {unknownGate ? (
                    <div className="space-y-2 text-sm">
                      <p>{t("unknownGateEdit")}</p>
                      <details>
                        <summary className="cursor-pointer">{t("savedGate")}</summary>
                        <TableScroll label={t("savedGate")} className="mt-2 max-h-48">
                          <pre className="whitespace-pre-wrap break-words text-xs">
                            {formatDataValue(editing?.gate)}
                          </pre>
                        </TableScroll>
                      </details>
                    </div>
                  ) : null}
                  {gateChanges.invalid ? <p className="text-sm">{gateChanges.invalid}</p> : null}
                  {busy && pending === "suite" ? (
                    <p role="status" className="text-sm">
                      {t("suiteSaving")}
                    </p>
                  ) : null}
                  {formError ? (
                    <div
                      ref={formAlert}
                      role="alert"
                      tabIndex={-1}
                      className="rounded-lg border border-[var(--border)] p-3 text-sm"
                    >
                      <ErrorMessage error={formError} />
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
                        attempt.state === "refused"
                          ? "suiteRefused"
                          : attempt.state === "unknown"
                            ? "suiteUnconfirmed"
                            : attempt.state === "acknowledged"
                              ? "suiteAcknowledged"
                              : "suiteConfirmed",
                      )}
                    </p>
                  ) : null}
                  {attempt?.saved ? (
                    <p className="break-all text-xs">
                      {t("suiteReference", { id: attempt.saved.id })}
                    </p>
                  ) : null}
                  {attempt?.saved ? (
                    <details className="text-sm">
                      <summary className="cursor-pointer">{t("returnedSuite")}</summary>
                      <TableScroll label={t("returnedSuite")} className="mt-2 max-h-64">
                        <pre className="whitespace-pre-wrap break-words text-xs">
                          {formatDataValue({
                            name: attempt.saved.name,
                            description: attempt.saved.description,
                            kind: attempt.saved.kind,
                            agent: attempt.saved.agent,
                            gate: attempt.saved.gate,
                          })}
                        </pre>
                      </TableScroll>
                    </details>
                  ) : null}
                  {attempt || formError ? (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={loading || busy}
                      onClick={() => void load()}
                    >
                      {t("copyRefresh")}
                    </Button>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="submit"
                      disabled={
                        !loaded ||
                        loading ||
                        busy ||
                        Boolean(attempt) ||
                        !name.trim() ||
                        !dirty ||
                        Boolean(gateChanges.invalid)
                      }
                    >
                      {t(editing ? "saveChanges" : "create")}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={busy}
                      onClick={() => {
                        const wasEditing = Boolean(editing);
                        resetForm();
                        if (wasEditing && editOpener.current?.isConnected)
                          editOpener.current.focus();
                        else if (wasEditing) searchInput.current?.focus();
                        else nameInput.current?.focus();
                      }}
                    >
                      {t(
                        attempt?.state === "confirmed"
                          ? "finishEdit"
                          : editing
                            ? "cancel"
                            : "clearDraft",
                      )}
                    </Button>
                  </div>
                </form>
              }
            >
              {loaded && (loading || error) ? (
                <p role="status" className="mb-3 text-sm text-[var(--muted-foreground)]">
                  {t(loading ? "refreshing" : "suitesRetained")}
                </p>
              ) : null}
              <DetailState loading={loading && !loaded} error={error} onRetry={() => void load()} />
              {busy && pending === "import" ? (
                <p role="status" className="mb-3 text-sm">
                  {t("importing")}
                </p>
              ) : null}
              {importNotice ? (
                <p role="status" className="mb-3 text-sm">
                  {importNotice}
                </p>
              ) : null}
              {importError ? (
                <div
                  role="alert"
                  className="mb-3 rounded-lg border border-[var(--border)] p-3 text-sm"
                >
                  <ErrorMessage error={importError} />
                </div>
              ) : null}
              <fieldset aria-label={t("suiteFilters")} className="mb-4 grid gap-3">
                <Input
                  ref={searchInput}
                  type="search"
                  aria-label={t("suiteSearch")}
                  placeholder={t("suiteSearch")}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="text-sm">
                    {t("kind")}
                    <select
                      className={`mt-1 ${selectClass}`}
                      value={kindFilter}
                      onChange={(event) => setKindFilter(event.target.value)}
                    >
                      <option value="">{t("allKinds")}</option>
                      {kindOptions.map((value) => (
                        <option key={value} value={value}>
                          {kindLabel(value)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-sm">
                    {t("status")}
                    <select
                      className={`mt-1 ${selectClass}`}
                      value={runStatus}
                      onChange={(event) => setRunStatus(event.target.value)}
                    >
                      <option value="">{t("allStatuses")}</option>
                      {statuses.map((value) => {
                        const parts = JSON.parse(value) as string[];
                        return (
                          <option key={value} value={value}>
                            {parts[0] === "none" ? t("noSavedRun") : statusLabel(parts[1] ?? "")}
                          </option>
                        );
                      })}
                    </select>
                  </label>
                </div>
              </fieldset>
              {query || kindFilter || runStatus ? (
                <Button
                  type="button"
                  variant="outline"
                  className="mb-4"
                  onClick={() => {
                    setQuery("");
                    setKindFilter("");
                    setRunStatus("");
                    searchInput.current?.focus();
                  }}
                >
                  {t("clearFilters")}
                </Button>
              ) : null}
              {loaded && filtered.length === 0 ? (
                <EmptyState compact title={t(suites.length ? "noSuiteMatches" : "empty")} />
              ) : null}
              <ul className="row-list">
                {loaded
                  ? pagination.rows.map((suite) => (
                      <li key={suite.id} className="space-y-3 p-4">
                        <h2 className="break-words text-sm font-medium">{suite.name}</h2>
                        <p className="break-words text-sm text-[var(--muted-foreground)]">
                          {kindLabel(suite.kind)} · {t("cases")} {suite.caseCount}
                          {suite.agent ? ` · ${suite.agent.name || suite.agent.id}` : ""}
                        </p>
                        {suite.description ? (
                          <details>
                            <summary className="cursor-pointer text-sm">
                              {t("suiteDescription")}
                            </summary>
                            <p className="mt-2 whitespace-pre-wrap break-words text-sm text-[var(--muted-foreground)]">
                              {suite.description}
                            </p>
                          </details>
                        ) : null}
                        {suite.lastRun ? (
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge tone={statusTone(suite.lastRun.status)}>
                              {statusLabel(suite.lastRun.status)}
                            </Badge>
                            {suite.lastRun.passRate != null ? (
                              <span className="break-all text-sm">
                                {t("rateSummary", { rate: percent.format(suite.lastRun.passRate) })}
                              </span>
                            ) : null}
                          </div>
                        ) : (
                          <p className="text-sm text-[var(--muted-foreground)]">
                            {t("noSavedRun")}
                          </p>
                        )}
                        {suite.gate.required ? (
                          <p className="break-all text-xs text-[var(--muted-foreground)]">
                            {t("gateSummaryExact", {
                              rate: percent.format(suite.gate.minPassRate),
                            })}
                          </p>
                        ) : null}
                        <p title={suite.id} className="text-xs text-[var(--muted-foreground)]">
                          {t("reference", { id: suite.id.slice(-8) })}
                        </p>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            disabled={busy}
                            aria-label={t("viewCasesFor", { name: suite.name })}
                            onClick={(event) => {
                              dialogOpener.current = event.currentTarget;
                              setCaseSuite(suite);
                              setCaseTab("cases");
                            }}
                          >
                            {t("viewCases")}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            disabled={busy}
                            aria-label={t("addCaseTo", { name: suite.name })}
                            onClick={(event) => {
                              dialogOpener.current = event.currentTarget;
                              setCaseSuite(suite);
                              setCaseTab("add");
                            }}
                          >
                            {t("addCase")}
                          </Button>
                          <label className="sr-only" htmlFor={`import-${suite.id}`}>
                            {t("importCases")}
                          </label>
                          <input
                            accept=".jsonl,.json,.yaml,.yml,application/json,text/plain"
                            className="sr-only"
                            disabled={busy}
                            id={`import-${suite.id}`}
                            tabIndex={-1}
                            type="file"
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              event.target.value = "";
                              if (file) void importCases(suite, file);
                            }}
                          />
                          <Button
                            type="button"
                            variant="outline"
                            disabled={busy}
                            aria-label={t("importCasesFor", { name: suite.name })}
                            onClick={() => document.getElementById(`import-${suite.id}`)?.click()}
                          >
                            {t("importCases")}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            disabled={busy}
                            aria-label={t("editSuiteNamed", { name: suite.name })}
                            onClick={(event) => edit(suite, event.currentTarget)}
                          >
                            {t("editSuite")}
                          </Button>
                          <Button
                            type="button"
                            disabled={busy || !canRun || suite.caseCount === 0}
                            onClick={(event) => {
                              dialogOpener.current = event.currentTarget;
                              setRunSuite(suite);
                            }}
                          >
                            {t("run")}
                          </Button>
                          {suite.lastRun ? (
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => {
                                setSelectedRun(suite.lastRun?.id ?? "");
                                setTab("runs");
                              }}
                            >
                              {t("viewResults")}
                            </Button>
                          ) : null}
                        </div>
                        {suite.caseCount === 0 ? (
                          <p className="text-xs text-[var(--muted-foreground)]">
                            {t("suiteNeedsCases")}
                          </p>
                        ) : null}
                      </li>
                    ))
                  : null}
              </ul>
              {loaded && suites.length > 0 ? (
                <ListPagination {...pagination} label={t("suites")} />
              ) : null}
            </ManagementLayout>
          </TabsContent>
          <TabsContent value="runs">
            <EvalRunHistory
              agentId={agentId}
              selectedId={selectedRun}
              onSelect={setSelectedRun}
              suiteNames={suiteNames}
            />
          </TabsContent>
          {admin ? (
            <TabsContent value="feedback">
              <EvalFeedbackPanel />
            </TabsContent>
          ) : null}
        </Tabs>
      )}
      {caseSuite ? (
        <SuiteCases
          suiteId={caseSuite.id}
          initialName={caseSuite.name}
          initialTab={caseTab}
          onClose={() => setCaseSuite(null)}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (dialogOpener.current?.isConnected) dialogOpener.current.focus();
            else searchInput.current?.focus();
          }}
          onSaved={() => void load()}
          onAccessLost={clearProtected}
        />
      ) : null}
      {runSuite && session ? (
        <RunSetup
          key={runSuite.id}
          suite={runSuite}
          agentId={agentId}
          session={session}
          onClose={() => setRunSuite(null)}
          onStarted={(id) => {
            setRunSuite(null);
            setSelectedRun(id);
            setTab("runs");
          }}
          onHistory={() => {
            setRunSuite(null);
            setTab("runs");
          }}
          onAccessLost={clearProtected}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (dialogOpener.current?.isConnected) dialogOpener.current.focus();
            else searchInput.current?.focus();
          }}
        />
      ) : null}
    </AppShell>
  );
}
