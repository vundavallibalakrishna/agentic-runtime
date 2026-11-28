"use client";

import { useTranslations } from "next-intl";
import { type ComponentProps, useCallback, useEffect, useRef, useState } from "react";
import type { AgentDetail } from "@/components/agents/types";
import { ErrorMessage } from "@/components/common/detail-state";
import { ReferencePicker } from "@/components/common/reference-picker";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { ApiError, api, type DisplayError, type Session } from "@/lib/api";
import { type Suite, suiteValid } from "./suite-data";

type Version = { id: string; version: number; etag: string; mode: "published" | "draft" };
type Agent = { id: string; name: string; versions: Version[] };
type Receipt = {
  id: string;
  suiteId: string;
  agentId: string;
  agentVersionId: string;
  status: string;
};
type Attempt = { state: "unknown" | "refused" | "acknowledged"; saved?: Receipt };
type Props = {
  suite: Suite;
  agentId?: string;
  session: Session;
  onClose: () => void;
  onStarted: (id: string) => void;
  onHistory: () => void;
  onAccessLost: (error: DisplayError) => void;
  onCloseAutoFocus?: ComponentProps<typeof DialogContent>["onCloseAutoFocus"];
};
const scopeOf = (session: Session) =>
  JSON.stringify([
    session.tenant?.id ?? session.tenant?.slug ?? null,
    session.user?.id ?? session.user?.email ?? null,
  ]);
const text = (value: unknown): value is string =>
  typeof value === "string" && Boolean(value.trim());
function agentFrom(value: AgentDetail, id: string, message: string): Agent {
  if (!value || value.id !== id || !text(value.name)) throw new Error(message);
  const versions: Version[] = [];
  for (const mode of ["published", "draft"] as const) {
    const version = value[mode];
    if (version == null) continue;
    const etag = (version as { etag?: unknown }).etag;
    if (
      !text(etag) ||
      !text(version.id) ||
      !Number.isSafeInteger(version.version) ||
      (version.version ?? 0) < 1
    )
      throw new Error(message);
    if (versions.some((item) => item.version === version.version || item.id === version.id))
      throw new Error(message);
    versions.push({
      id: version.id,
      version: version.version as number,
      etag: etag as string,
      mode,
    });
  }
  return { id, name: value.name, versions };
}
function matches(
  value: unknown,
  expected: Omit<Receipt, "id" | "status">,
  id?: string,
): value is Receipt {
  if (!value || typeof value !== "object") return false;
  const row = value as Receipt;
  return (
    text(row.id) &&
    (!id || row.id === id) &&
    text(row.status) &&
    row.suiteId === expected.suiteId &&
    row.agentId === expected.agentId &&
    row.agentVersionId === expected.agentVersionId
  );
}
export function RunSetup(props: Props) {
  const t = useTranslations("evals");
  const callbacks = useRef(props);
  callbacks.current = props;
  const [agentId, setAgentId] = useState(props.agentId || props.suite.agent?.id || ""),
    [agent, setAgent] = useState<Agent | null>(null),
    [suite, setSuite] = useState<Suite | null>(null),
    [versionId, setVersionId] = useState(""),
    [busy, setBusy] = useState<"read" | "write" | "">("read"),
    [allowed, setAllowed] = useState(false),
    [error, setError] = useState<DisplayError>(""),
    [notice, setNotice] = useState(""),
    [attempt, setAttempt] = useState<Attempt | null>(null),
    [model, setModel] = useState(""),
    [aliases, setAliases] = useState<string[]>([]);
  const operation = useRef<AbortController | null>(null),
    attemptRef = useRef(attempt),
    owner = useRef(scopeOf(props.session)),
    notified = useRef(false),
    alert = useRef<HTMLDivElement>(null);
  attemptRef.current = attempt;
  const suiteId = props.suite.id;
  useEffect(() => {
    // Comparing models is optional: without permission to read them, it is not offered.
    const controller = new AbortController();
    api<{ items?: { alias?: string; kind?: string }[] }>("/api/v1/model-aliases", {
      signal: controller.signal,
    })
      .then((listed) => {
        if (controller.signal.aborted) return;
        setAliases(
          [
            ...new Set(
              (listed.items ?? [])
                .filter((row) => (row.kind ?? "chat") === "chat" && row.alias)
                .map((row) => row.alias as string),
            ),
          ].sort(),
        );
      })
      .catch(() => {
        if (!controller.signal.aborted) setAliases([]);
      });
    return () => controller.abort();
  }, []);
  const session = useCallback(
    async (controller: AbortController) => {
      const current = await api<Session>("/api/v1/auth/session", { signal: controller.signal });
      if (controller.signal.aborted) return false;
      if (scopeOf(current) !== owner.current) {
        callbacks.current.onAccessLost(t("sessionChanged"));
        return false;
      }
      if (
        !current.permissions?.includes("evals:manage") ||
        !current.permissions.includes("evals:run")
      ) {
        callbacks.current.onAccessLost(t("runDenied"));
        return false;
      }
      if (!current.permissions.includes("agents:read")) {
        setAllowed(false);
        throw new Error(t("agentAccess"));
      }
      setAllowed(true);
      return true;
    },
    [t],
  );
  const fail = useCallback(
    (caught: unknown) => {
      if (
        caught instanceof ApiError &&
        (caught.status === 401 || (caught.status === 403 && caught.code !== "csrf_failed"))
      ) {
        callbacks.current.onAccessLost(caught);
      } else setError(caught instanceof Error ? caught : t("error"));
    },
    [t],
  );
  const opened = useCallback((id: string) => {
    if (!notified.current) {
      notified.current = true;
      callbacks.current.onStarted(id);
    }
  }, []);
  const read = useCallback(async () => {
    if (operation.current) return;
    const controller = new AbortController();
    operation.current = controller;
    const active = () => operation.current === controller && !controller.signal.aborted;
    setBusy("read");
    setNotice("");
    try {
      if (!(await session(controller)) || !active()) return;
      const [savedSuite, savedAgent] = await Promise.all([
        api<unknown>(`/api/v1/eval-suites/${encodeURIComponent(suiteId)}`, {
          signal: controller.signal,
        }),
        agentId
          ? api<AgentDetail>(`/api/v1/agents/${encodeURIComponent(agentId)}`, {
              signal: controller.signal,
            })
          : Promise.resolve(null),
      ]);
      if (!active()) return;
      if (!suiteValid(savedSuite) || savedSuite.id !== suiteId) throw new Error(t("suiteMetadata"));
      const next = savedAgent ? agentFrom(savedAgent, agentId, t("runAgentMetadata")) : null;
      setSuite(savedSuite);
      setAgent(next);
      setError("");
      const previous = attemptRef.current;
      if (previous?.saved) {
        const checked = await api<unknown>(
          `/api/v1/eval-runs/${encodeURIComponent(previous.saved.id)}`,
          { signal: controller.signal },
        );
        if (!active()) return;
        if (!matches(checked, previous.saved, previous.saved.id)) throw new Error(t("runMetadata"));
        opened(checked.id);
      } else if (previous?.state === "refused") {
        setAttempt(null);
        setNotice(t("runChecked"));
      } else if (previous?.state === "unknown") setNotice(t("runUnknownChecked"));
    } catch (caught) {
      if (active()) fail(caught);
    } finally {
      if (active()) {
        operation.current = null;
        setBusy("");
      }
    }
  }, [agentId, suiteId, session, fail, opened, t]);
  useEffect(() => {
    void read();
    return () => {
      operation.current?.abort();
      operation.current = null;
    };
  }, [read]);
  useEffect(() => {
    if (error) alert.current?.focus();
  }, [error]);
  const selected = agent?.versions.find((value) => value.id === versionId),
    ready = Boolean(
      allowed && suite?.caseCount && agent && selected && !error && !attempt && !busy,
    );
  async function start() {
    if (operation.current || !ready || !selected || !agent || !suite) return;
    const controller = new AbortController(),
      expected = { suiteId, agentId: agent.id, agentVersionId: selected.id };
    operation.current = controller;
    const active = () => operation.current === controller && !controller.signal.aborted;
    setBusy("write");
    setError("");
    setNotice("");
    let sent = false;
    try {
      if (!(await session(controller)) || !active()) return;
      const [currentSuite, currentVersion] = await Promise.all([
        api<unknown>(`/api/v1/eval-suites/${encodeURIComponent(suiteId)}`, {
          signal: controller.signal,
        }),
        api<{ id?: string; version?: number; agentId?: string; etag?: string }>(
          `/api/v1/agents/${encodeURIComponent(agent.id)}/versions/${selected.version}`,
          { signal: controller.signal },
        ),
      ]);
      if (!active()) return;
      if (!suiteValid(currentSuite) || currentSuite.id !== suiteId || currentSuite.caseCount === 0)
        throw new Error(t("runSuiteUnavailable"));
      if (
        currentVersion?.id !== selected.id ||
        currentVersion.version !== selected.version ||
        currentVersion.etag !== selected.etag ||
        currentVersion.agentId !== agent.id
      )
        throw new Error(t("runVersionChanged"));
      sent = true;
      setAttempt({ state: "unknown" });
      const saved = await api<unknown>(`/api/v1/eval-suites/${encodeURIComponent(suiteId)}:run`, {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          agentId: agent.id,
          agentVersionRef: String(selected.version),
          ...(model ? { modelAliasOverride: model } : {}),
        }),
      });
      if (!active()) return;
      if (!matches(saved, expected)) throw new Error(t("runMetadata"));
      setAttempt({ state: "acknowledged", saved });
      const checked = await api<unknown>(`/api/v1/eval-runs/${encodeURIComponent(saved.id)}`, {
        signal: controller.signal,
      });
      if (!active()) return;
      if (!matches(checked, expected, saved.id)) throw new Error(t("runMetadata"));
      opened(checked.id);
    } catch (caught) {
      if (!active()) return;
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
      fail(caught);
    } finally {
      if (active()) {
        operation.current = null;
        setBusy("");
      }
    }
  }
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) props.onClose();
      }}
    >
      <DialogContent
        title={t("runSetup")}
        onCloseAutoFocus={props.onCloseAutoFocus}
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="outline" onClick={props.onClose}>
              {t("close")}
            </Button>
            <Button type="submit" form="eval-run-setup" disabled={!ready}>
              {t("startRun")}
            </Button>
          </div>
        }
      >
        <form
          id="eval-run-setup"
          className="mt-4 grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            void start();
          }}
        >
          <p className="break-words text-sm font-medium">{suite?.name || props.suite.name}</p>
          <p className="text-sm text-[var(--muted-foreground)]">{t("runHelp")}</p>
          <fieldset disabled={Boolean(busy || attempt)} className="grid min-w-0 gap-4">
            <ReferencePicker
              label={t("targetAgent")}
              endpoint="/api/v1/agents"
              value={agentId}
              selection={agent || props.suite.agent}
              onChange={(value) => {
                setAgentId(value);
                setAgent(null);
                setVersionId("");
                setError("");
                setNotice("");
              }}
              required
              disabled={Boolean(props.agentId) || !allowed || Boolean(busy || attempt)}
            />
            <label htmlFor="eval-run-version" className="text-sm">
              {t("version")}
            </label>
            <select
              id="eval-run-version"
              className="h-10 w-full min-w-0 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
              value={versionId}
              onChange={(event) => setVersionId(event.target.value)}
              disabled={!agent || Boolean(busy || attempt)}
            >
              <option value="">{t("chooseRunVersion")}</option>
              {versionId && !selected ? (
                <option value={versionId} disabled>
                  {t("runVersionUnavailable")}
                </option>
              ) : null}
              {agent?.versions.map((version) => (
                <option key={version.id} value={version.id}>
                  {t("runVersionOption", { mode: t(version.mode), version: version.version })}
                </option>
              ))}
            </select>
          </fieldset>
          {agent && agent.versions.length === 0 ? (
            <p className="text-sm">{t("runNoVersions")}</p>
          ) : null}
          {aliases.length > 0 ? (
            <label className="block text-sm" htmlFor="eval-run-model">
              {t("model")}
              <select
                className="mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
                disabled={Boolean(busy || attempt)}
                id="eval-run-model"
                onChange={(event) => setModel(event.target.value)}
                value={model}
              >
                <option value="">{t("agentModel")}</option>
                {aliases.map((alias) => (
                  <option key={alias} value={alias}>
                    {alias}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {selected ? (
            <p className="break-all text-xs text-[var(--muted-foreground)]">
              {t("runVersionReference", { id: selected.id })}
            </p>
          ) : null}
          {suite?.caseCount === 0 ? <p className="text-sm">{t("suiteNeedsCases")}</p> : null}
          {busy ? (
            <p role="status" className="text-sm">
              {t(busy === "write" ? "runStarting" : "runLoading")}
            </p>
          ) : null}
          {error ? (
            <div
              role="alert"
              ref={alert}
              tabIndex={-1}
              className="rounded-lg border border-[var(--border)] p-3 text-sm"
            >
              <ErrorMessage error={error} />
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
                  ? "runRefused"
                  : attempt.state === "acknowledged"
                    ? "runAcknowledged"
                    : "runUnconfirmed",
              )}
            </p>
          ) : null}
          {attempt?.saved ? (
            <p className="break-all text-xs">{t("runSavedReference", { id: attempt.saved.id })}</p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={Boolean(busy)}
              onClick={() => void read()}
            >
              {t("copyRefresh")}
            </Button>
            {attempt ? (
              <Button
                type="button"
                variant="outline"
                disabled={Boolean(busy)}
                onClick={props.onHistory}
              >
                {t("runReviewHistory")}
              </Button>
            ) : null}
          </div>
          <p className="text-xs text-[var(--muted-foreground)]">{t("runCloseHelp")}</p>
        </form>
      </DialogContent>
    </Dialog>
  );
}
