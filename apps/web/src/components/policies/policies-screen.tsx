"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ActionStatus, DetailState, ErrorMessage } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { WebAccess } from "@/components/policies/web-access";
import { MaskingSettings } from "@/components/privacy/masking-settings";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { DisplayError } from "@/lib/api";
import { api } from "@/lib/api";
import { loadSession } from "@/lib/session";
import { confirmStepUp } from "@/lib/step-up";

type Row = Record<string, unknown>;

const MODE_KEY = "ar-settings-mode";

export function PoliciesScreen() {
  const t = useTranslations("policies");
  const confirmation = useTranslations("detail");
  const shell = useTranslations("shell");
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<DisplayError>("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const [name, setName] = useState("");
  const [tool, setTool] = useState("");
  const [effect, setEffect] = useState("requireApproval");
  const [message, setMessage] = useState("");
  const [documentText, setDocumentText] = useState("");
  const [decision, setDecision] = useState("");
  const [checkTool, setCheckTool] = useState("");
  const readRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const [phase, setPhase] = useState<
    "saving" | "checking" | "confirming" | "activating" | "refreshing" | null
  >(null);
  const busy = phase !== null;
  const [actionError, setActionError] = useState<DisplayError>("");
  const [checkError, setCheckError] = useState<DisplayError>("");
  const [checkedTool, setCheckedTool] = useState("");
  const [target, setTarget] = useState("");
  const [recovery, setRecovery] = useState<{
    accepted: boolean;
    id?: string;
    detail?: DisplayError;
  } | null>(null);
  const [canManage, setCanManage] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const filtered = rows.filter(
    (row) =>
      (!status || row.status === status) &&
      [row.name, row.description, row.id].some((value) =>
        String(value ?? "")
          .toLocaleLowerCase()
          .includes(query.trim().toLocaleLowerCase()),
      ),
  );
  const pagination = usePagedRows(filtered, `${query}::${status}`);
  const statuses = [...new Set(rows.map((row) => String(row.status ?? "")).filter(Boolean))].sort();

  useEffect(() => {
    try {
      setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
    } catch {
      setAdvanced(false);
    }
  }, []);

  const load = useCallback(
    async (expectedId?: string) => {
      readRequest.current?.abort();
      const request = new AbortController();
      readRequest.current = request;
      setLoading(true);
      setError("");
      try {
        const [page, session] = await Promise.all([
          api<{ items: Row[] }>("/api/v1/policies", { signal: request.signal }),
          loadSession(),
        ]);
        if (request.signal.aborted) return false;
        if (!Array.isArray(page?.items)) throw new Error(t("listUnconfirmed"));
        setRows(page.items);
        setCanManage(session.permissions?.includes("policies:manage") ?? false);
        if (expectedId && !page.items.some((row) => row.id === expectedId))
          throw new Error(t("targetUnavailable"));
        return true;
      } catch (caught) {
        if (!request.signal.aborted) setError(caught instanceof Error ? caught : t("error"));
        return false;
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
    void load();
    return () => {
      readRequest.current?.abort();
      actionRequest.current?.abort();
    };
  }, [load]);

  const documentMode = advanced && Boolean(documentText.trim());
  const complete =
    name.trim() !== "" && (documentMode || (tool.trim() !== "" && message.trim() !== ""));
  const locked = busy || loading || Boolean(error) || Boolean(recovery);
  function documentBody(): Record<string, unknown> {
    if (documentMode) {
      const parsed: unknown = JSON.parse(documentText);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
        throw new Error(t("documentObject"));
      return parsed as Record<string, unknown>;
    }
    return { rules: [{ id: "rule-1", effect, message, match: { tools: [tool] } }] };
  }

  async function refresh() {
    if (actionRequest.current) return;
    if (await load(recovery?.id)) {
      setRecovery(null);
      setActionError("");
    }
  }

  async function save() {
    if (actionRequest.current || locked || !canManage || !complete) return;
    setActionError("");
    setNotice("");
    let document: Record<string, unknown>;
    try {
      document = documentBody();
    } catch (caught) {
      setActionError(caught instanceof Error ? caught : t("documentObject"));
      return;
    }
    const submitted = { name, message, tool, documentText };
    const request = new AbortController();
    actionRequest.current = request;
    setPhase("saving");
    setTarget(name);
    let accepted = false;
    let id: string | undefined;
    try {
      const result = await api<Row>("/api/v1/policies", {
        method: "POST",
        signal: request.signal,
        body: JSON.stringify({ name, description: message, document }),
      });
      if (request.signal.aborted) return;
      if (typeof result?.id !== "string" || !result.id || result.status !== "draft")
        throw new Error(t("saveUnconfirmed"));
      accepted = true;
      id = result.id;
      setNotice(t("saved"));
      setName((current) => (current === submitted.name ? "" : current));
      setMessage((current) => (current === submitted.message ? "" : current));
      setTool((current) => (current === submitted.tool ? "" : current));
      setDocumentText((current) => (current === submitted.documentText ? "" : current));
      setPhase("refreshing");
      if (!(await load(id)) && !request.signal.aborted) setRecovery({ accepted, id });
    } catch (caught) {
      if (!request.signal.aborted)
        setRecovery({
          accepted,
          id,
          detail: caught instanceof Error ? caught : t("error"),
        });
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setPhase(null);
      }
    }
  }

  async function simulate() {
    if (actionRequest.current || locked || !checkTool.trim()) return;
    const request = new AbortController();
    actionRequest.current = request;
    const submitted = checkTool.trim();
    setPhase("checking");
    setCheckedTool(submitted);
    setDecision("");
    setCheckError("");
    try {
      const result = await api<Row>("/api/v1/policies:simulate", {
        method: "POST",
        signal: request.signal,
        body: JSON.stringify({ toolQualifiedName: submitted, args: {} }),
      });
      if (request.signal.aborted) return;
      if (typeof result?.decision !== "string" || !result.decision)
        throw new Error(t("checkUnconfirmed"));
      setDecision(result.decision);
    } catch (caught) {
      if (!request.signal.aborted) setCheckError(caught instanceof Error ? caught : t("error"));
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setPhase(null);
      }
    }
  }

  async function activate(row: Row) {
    const version = row.latestVersion;
    if (
      actionRequest.current ||
      locked ||
      !canManage ||
      typeof row.id !== "string" ||
      !row.id ||
      !Number.isSafeInteger(version) ||
      Number(version) < 1 ||
      row.status === "active"
    )
      return;
    const request = new AbortController();
    actionRequest.current = request;
    setPhase("confirming");
    setTarget(String(row.name ?? row.id));
    setActionError("");
    setNotice("");
    let posted = false;
    let accepted = false;
    try {
      await confirmStepUp(confirmation("stepUpUnconfirmed"), request.signal);
      if (request.signal.aborted) return;
      setPhase("activating");
      posted = true;
      const result = await api<Row>(`/api/v1/policies/${encodeURIComponent(row.id)}:activate`, {
        method: "POST",
        signal: request.signal,
        body: JSON.stringify({ version }),
      });
      if (request.signal.aborted) return;
      if (result?.id !== row.id || result.status !== "active" || result.activeVersion !== version)
        throw new Error(t("activationUnconfirmed"));
      accepted = true;
      setNotice(
        t("activatedNamed", { name: String(row.name ?? row.id), version: Number(version) }),
      );
      setPhase("refreshing");
      if (!(await load(row.id)) && !request.signal.aborted) setRecovery({ accepted, id: row.id });
    } catch (caught) {
      if (!request.signal.aborted) {
        const detail = caught instanceof Error ? caught : t("error");
        if (posted) setRecovery({ accepted, id: row.id, detail });
        else setActionError(detail);
      }
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setPhase(null);
      }
    }
  }

  return (
    <AppShell>
      <PageHeader
        title={t("title")}
        body={t("body")}
        actions={
          <>
            <Button asChild variant="ghost">
              <a href="/approvals">{shell("navApprovals")}</a>
            </Button>
            <SettingsMode
              advanced={advanced}
              onChange={(value) => {
                setAdvanced(value);
                try {
                  window.localStorage.setItem(MODE_KEY, value ? "advanced" : "simple");
                } catch {
                  /* Keep the chosen mode for this view. */
                }
              }}
            />
          </>
        }
      />

      <Tabs defaultValue="rules">
        <TabsList>
          <TabsTrigger value="rules">{t("tabs.rules")}</TabsTrigger>
          <TabsTrigger value="web">{t("tabs.web")}</TabsTrigger>
          <TabsTrigger value="masking">{t("tabs.masking")}</TabsTrigger>
        </TabsList>
        <TabsContent value="rules" forceMount>
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <ActionStatus
              busy={busy || loading}
              busyLabel={
                phase
                  ? t(`progress.${phase}`, { name: phase === "checking" ? checkedTool : target })
                  : t("progress.refreshing")
              }
              notice={notice}
            />
            <Button
              type="button"
              variant="outline"
              disabled={busy || loading}
              onClick={() => void refresh()}
            >
              {t("refresh")}
            </Button>
          </div>
          <DetailState
            loading={loading && rows.length === 0}
            error={error}
            onRetry={busy ? undefined : () => void refresh()}
          />
          {actionError ? (
            <div role="alert" className="mb-4 break-words text-sm text-[var(--destructive)]">
              <ErrorMessage error={actionError} />
            </div>
          ) : null}
          {recovery ? (
            <div role="alert" className="mb-5 rounded-lg border border-[var(--border)] p-4 text-sm">
              <p>{t(recovery.accepted ? "acceptedRecovery" : "recovery", { name: target })}</p>
              {recovery.detail ? (
                <div className="mt-2 break-words text-[var(--muted-foreground)]">
                  <ErrorMessage error={recovery.detail} />
                </div>
              ) : null}
            </div>
          ) : null}
          <ManagementLayout
            title={t("listTitle")}
            formTitle={t("createTitle")}
            form={
              <form
                className="grid gap-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void save();
                }}
              >
                <p className="text-sm text-[var(--muted-foreground)]">
                  {loading ? t("loading") : canManage ? t("createHelp") : t("readOnly")}
                </p>
                <fieldset disabled={locked || !canManage} className="grid min-w-0 gap-4">
                  <label htmlFor="policy-name">
                    {t("name")}
                    <Input
                      id="policy-name"
                      required
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                    />
                  </label>
                  <fieldset className="grid min-w-0 gap-4" disabled={documentMode}>
                    <div>
                      <label htmlFor="policy-tool">{t("tool")}</label>
                      <Input
                        id="policy-tool"
                        value={tool}
                        onChange={(event) => setTool(event.target.value)}
                        aria-describedby="policy-tool-help"
                      />
                      <span
                        id="policy-tool-help"
                        className="mt-1 block text-xs text-[var(--muted-foreground)]"
                      >
                        {t("toolHelp")}
                      </span>
                    </div>
                    <label htmlFor="policy-effect">
                      {t("effect")}
                      <select
                        id="policy-effect"
                        className="mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
                        value={effect}
                        onChange={(event) => setEffect(event.target.value)}
                      >
                        <option value="requireApproval">{t("requireApproval")}</option>
                        <option value="deny">{t("deny")}</option>
                        <option value="allow">{t("allow")}</option>
                      </select>
                    </label>
                    <label htmlFor="policy-message">
                      {t("message")}
                      <Input
                        id="policy-message"
                        value={message}
                        onChange={(event) => setMessage(event.target.value)}
                      />
                    </label>
                  </fieldset>
                  {advanced ? (
                    <div>
                      <label htmlFor="policy-document">{t("yaml")}</label>
                      <span
                        id="policy-document-help"
                        className="my-1 block text-xs text-[var(--muted-foreground)]"
                      >
                        {t("documentHelp")}
                      </span>
                      <textarea
                        id="policy-document"
                        aria-describedby="policy-document-help"
                        className="mt-1 h-40 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 font-mono text-xs"
                        value={documentText}
                        onChange={(event) => setDocumentText(event.target.value)}
                      />
                    </div>
                  ) : null}
                  <div className="flex gap-2">
                    <Button disabled={!complete} type="submit">
                      {t("save")}
                    </Button>
                  </div>
                </fieldset>
              </form>
            }
          >
            {!loading && !error && rows.length === 0 ? <EmptyState title={t("empty")} /> : null}
            {!loading && rows.length > 0 ? (
              <div className="mb-4 flex flex-wrap gap-3">
                <Input
                  type="search"
                  aria-label={t("search")}
                  placeholder={t("search")}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  className="min-w-0 flex-1"
                />
                <select
                  aria-label={t("status")}
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                  className="h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
                >
                  <option value="">{t("allStatuses")}</option>
                  {statuses.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
                {query || status ? (
                  <Button
                    variant="outline"
                    type="button"
                    onClick={() => {
                      setQuery("");
                      setStatus("");
                    }}
                  >
                    {t("clearFilters")}
                  </Button>
                ) : null}
              </div>
            ) : null}
            {!loading && rows.length > 0 && filtered.length === 0 ? (
              <EmptyState title={t("noMatches")} />
            ) : null}
            <ul className="row-list">
              {pagination.rows.map((row) => (
                <li key={String(row.id)} className="p-4">
                  <h3 className="break-words font-medium">{String(row.name)}</h3>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    <Badge tone={statusTone(String(row.status ?? ""))}>
                      {String(row.status ?? "")}
                    </Badge>{" "}
                    {t("versions")} {String(row.latestVersion ?? "")}
                  </p>
                  {canManage && row.status !== "active" ? (
                    <Button
                      disabled={
                        locked ||
                        !Number.isSafeInteger(row.latestVersion) ||
                        Number(row.latestVersion) < 1
                      }
                      className="mt-3"
                      type="button"
                      onClick={() => void activate(row)}
                    >
                      {t("activate")}
                    </Button>
                  ) : null}
                  {canManage &&
                  row.status !== "active" &&
                  (!Number.isSafeInteger(row.latestVersion) || Number(row.latestVersion) < 1) ? (
                    <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                      {t("versionUnavailable")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
            {!loading && rows.length > 0 ? <ListPagination {...pagination} /> : null}
          </ManagementLayout>
          <section
            className="mt-8 max-w-2xl rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
            aria-label={t("checkTitle")}
          >
            <h2 className="text-sm font-semibold">{t("checkTitle")}</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("checkHelp")}</p>
            <form
              className="mt-4"
              onSubmit={(event) => {
                event.preventDefault();
                void simulate();
              }}
            >
              <label className="block text-sm" htmlFor="check-policy-tool">
                {t("tool")}
              </label>
              <div className="mt-1 flex flex-wrap gap-2">
                <Input
                  className="min-w-0 flex-1"
                  id="check-policy-tool"
                  disabled={locked}
                  value={checkTool}
                  onChange={(event) => {
                    setCheckTool(event.target.value);
                    setDecision("");
                    setCheckError("");
                  }}
                  required
                />
                <Button type="submit" variant="outline" disabled={locked || !checkTool.trim()}>
                  {t("simulate")}
                </Button>
              </div>
            </form>
            {checkError ? (
              <div className="mt-3 break-words text-sm text-[var(--destructive)]" role="alert">
                <ErrorMessage error={checkError} />
              </div>
            ) : null}
            {decision ? (
              <p className="mt-3 text-sm" role="status">
                <span className="mb-1 block text-xs text-[var(--muted-foreground)]">
                  {t("checkedTool", { tool: checkedTool })}
                </span>
                {t("decision")}:{" "}
                {decision === "require_approval" || decision === "requireApproval"
                  ? t("requireApproval")
                  : decision === "allow"
                    ? t("allow")
                    : decision === "deny"
                      ? t("deny")
                      : decision}
              </p>
            ) : null}
          </section>
        </TabsContent>
        <TabsContent value="web" forceMount>
          <WebAccess />
        </TabsContent>
        <TabsContent value="masking" forceMount>
          <MaskingSettings advanced={advanced} />
        </TabsContent>
      </Tabs>
    </AppShell>
  );
}
