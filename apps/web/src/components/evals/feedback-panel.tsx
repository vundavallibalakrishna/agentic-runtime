"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DetailState, ErrorMessage } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { ReferencePicker } from "@/components/common/reference-picker";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { TableScroll } from "@/components/ui/table";
import { ApiError, api, type DisplayError, type Session } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { loadSession } from "@/lib/session";
import { casesFrom, caseValid, type SavedCase, sameCase } from "./case-data";
import { CaseReceipt } from "./case-details";

type Feedback = {
  messageId?: string | null;
  conversationId?: string | null;
  rating: string;
  comment?: string | null;
  agent?: { name?: string } | null;
  createdAt?: string | null;
};
type Copy = { state: "refused" | "unknown" | "acknowledged" | "confirmed"; saved?: SavedCase };
const text = (value: unknown): value is string =>
  typeof value === "string" && Boolean(value.trim());
const scopeOf = (session: Session) =>
  JSON.stringify([
    session.tenant?.id ?? session.tenant?.slug ?? null,
    session.user?.id ?? session.user?.email ?? null,
  ]);
const accessLost = (error: unknown) =>
  error instanceof ApiError &&
  (error.status === 401 || (error.status === 403 && error.code !== "csrf_failed"));
const targetKey = (item: Feedback, suiteId: string) =>
  JSON.stringify([item.conversationId, item.messageId, suiteId]);
function feedbackValid(value: unknown): value is Feedback {
  if (!value || typeof value !== "object") return false;
  const row = value as Feedback;
  return (
    text(row.rating) &&
    (row.messageId == null || text(row.messageId)) &&
    (row.conversationId == null || text(row.conversationId)) &&
    (row.comment == null || typeof row.comment === "string") &&
    (row.agent == null ||
      (typeof row.agent === "object" &&
        (row.agent.name == null || typeof row.agent.name === "string"))) &&
    (row.createdAt == null ||
      (text(row.createdAt) &&
        /(?:Z|[+-]\d{2}:\d{2})$/i.test(row.createdAt) &&
        Number.isFinite(new Date(row.createdAt).getTime())))
  );
}

export function EvalFeedbackPanel() {
  const t = useTranslations("evals"),
    locale = useLocale();
  const [rows, setRows] = useState<Feedback[]>([]),
    [loaded, setLoaded] = useState(false),
    [loading, setLoading] = useState(true);
  const [allowed, setAllowed] = useState(false),
    [canReadSource, setCanReadSource] = useState(false);
  const [error, setError] = useState<DisplayError>("");
  const [query, setQuery] = useState(""),
    [rating, setRating] = useState("");
  const [item, setItem] = useState<Feedback | null>(null),
    [suiteId, setSuiteId] = useState("");
  const [sourceReady, setSourceReady] = useState(false),
    [pending, setPending] = useState("");
  const [saveError, setSaveError] = useState<DisplayError>("");
  const [notice, setNotice] = useState("");
  const [copies, setCopies] = useState<Record<string, Copy>>({});
  const copiesRef = useRef(copies);
  copiesRef.current = copies;
  const read = useRef<AbortController | null>(null),
    action = useRef<AbortController | null>(null),
    owner = useRef<string | null>(null);
  const search = useRef<HTMLInputElement>(null),
    opener = useRef<HTMLButtonElement>(null),
    actionAlert = useRef<HTMLDivElement>(null);
  const deny = useCallback((message: DisplayError) => {
    read.current?.abort();
    read.current = null;
    action.current?.abort();
    action.current = null;
    setLoading(false);
    setPending("");
    setAllowed(false);
    setCanReadSource(false);
    setRows([]);
    setLoaded(false);
    setItem(null);
    setSourceReady(false);
    setCopies({});
    setError(message);
  }, []);
  const load = useCallback(async () => {
    if (read.current || action.current) return;
    const controller = new AbortController();
    read.current = controller;
    const active = () => read.current === controller && !controller.signal.aborted;
    setLoading(true);
    try {
      const session = await loadSession();
      if (!active()) return;
      const scope = scopeOf(session);
      if (owner.current && owner.current !== scope) {
        setRows([]);
        setLoaded(false);
        setItem(null);
        setCopies({});
        setSourceReady(false);
      }
      owner.current = scope;
      if (!session.permissions?.includes("evals:manage")) {
        deny(t("denied"));
        return;
      }
      setAllowed(true);
      setCanReadSource(Boolean(session.user?.id && session.permissions?.includes("chat:use")));
      const page = await api<{ items?: unknown }>("/api/v1/feedback", {
        signal: controller.signal,
      });
      if (!active()) return;
      if (!Array.isArray(page?.items) || !page.items.every(feedbackValid))
        throw new Error(t("feedbackMetadata"));
      setRows(page.items);
      setLoaded(true);
      setError("");
    } catch (caught) {
      if (!active()) return;
      if (accessLost(caught)) {
        deny(caught instanceof Error ? caught : t("denied"));
        return;
      }
      setError(caught instanceof Error ? caught : t("feedbackError"));
    } finally {
      if (active()) {
        read.current = null;
        setLoading(false);
      }
    }
  }, [deny, t]);
  useEffect(() => {
    void load();
    return () => {
      read.current?.abort();
      read.current = null;
      action.current?.abort();
      action.current = null;
    };
  }, [load]);
  const indexed = useMemo(
    () =>
      rows.map((row, index) => ({
        row,
        key: JSON.stringify([row.messageId, row.conversationId, row.createdAt, index]),
        search: [row.agent?.name, row.comment, row.messageId, row.conversationId]
          .filter(Boolean)
          .join(" ")
          .toLocaleLowerCase(),
      })),
    [rows],
  );
  const matching = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return indexed.filter(
      (value) => (!rating || value.row.rating === rating) && (!term || value.search.includes(term)),
    );
  }, [indexed, query, rating]);
  const ratings = useMemo(
    () => [...new Set([rating, ...rows.map((row) => row.rating)])].filter(Boolean).sort(),
    [rows, rating],
  );
  const pagination = usePagedRows(matching, JSON.stringify([query, rating]));
  const key = item ? targetKey(item, suiteId) : "";
  const currentCopy = copies[key];
  const busy = Boolean(pending);
  function close() {
    action.current?.abort();
    action.current = null;
    setPending("");
    setItem(null);
    setSaveError("");
    setNotice("");
    setSourceReady(false);
  }
  async function sourceCheck(controller: AbortController, target: Feedback) {
    const session = await api<Session>("/api/v1/auth/session", { signal: controller.signal });
    if (controller.signal.aborted) return false;
    if (owner.current !== scopeOf(session)) {
      deny(t("sessionChanged"));
      return false;
    }
    if (!session.permissions?.includes("evals:manage")) {
      deny(t("denied"));
      return false;
    }
    if (!session.user?.id || !session.permissions?.includes("chat:use"))
      throw new Error(t("feedbackSourceAccess"));
    const source = await api<{ id?: string; userId?: string; messages?: { id?: string }[] }>(
      `/api/v1/conversations/${encodeURIComponent(target.conversationId ?? "")}`,
      { signal: controller.signal },
    );
    if (controller.signal.aborted) return false;
    if (
      source?.id !== target.conversationId ||
      !text(source.userId) ||
      !Array.isArray(source.messages) ||
      !source.messages.every((message) => message && text(message.id)) ||
      !source.messages.some((message) => message.id === target.messageId)
    )
      throw new Error(t("feedbackSourceMetadata"));
    if (source.userId !== session.user.id && !session.permissions.includes("agents:manage_all"))
      throw new Error(t("feedbackSourceAccess"));
    return true;
  }
  async function inspect(target: Feedback, destination: string, recovery = false) {
    if (action.current || read.current) return;
    const controller = new AbortController();
    action.current = controller;
    setPending("check");
    setSaveError("");
    setNotice("");
    setSourceReady(false);
    const active = () => action.current === controller && !controller.signal.aborted;
    try {
      if (!(await sourceCheck(controller, target)) || !active()) return;
      setSourceReady(true);
      if (recovery && destination) {
        const page = await api<{ items?: unknown }>(
          `/api/v1/eval-suites/${encodeURIComponent(destination)}/cases`,
          { signal: controller.signal },
        );
        if (!active()) return;
        const cases = casesFrom(page, destination, t("copyCaseMetadata"));
        const previous = copiesRef.current[targetKey(target, destination)];
        if (previous?.saved) {
          const found = cases.find((value) => value.id === previous.saved?.id);
          if (!found || !sameCase(found, previous.saved)) throw new Error(t("copyNotVerified"));
          setCopies((values) => ({
            ...values,
            [targetKey(target, destination)]: { state: "confirmed", saved: found },
          }));
          setNotice(t("added"));
        } else if (previous?.state === "refused") {
          setCopies((values) => {
            const next = { ...values };
            delete next[targetKey(target, destination)];
            return next;
          });
          setNotice(t("copyChecked"));
        } else setNotice(t("copyCasesChecked", { count: cases.length }));
      }
    } catch (caught) {
      if (!active()) return;
      if (accessLost(caught) && caught instanceof ApiError && caught.status === 401) {
        deny(caught);
        return;
      }
      setSaveError(caught instanceof Error ? caught : t("error"));
    } finally {
      if (active()) {
        action.current = null;
        setPending("");
      }
    }
  }
  async function add() {
    if (
      action.current ||
      read.current ||
      !allowed ||
      !item ||
      !suiteId ||
      !sourceReady ||
      currentCopy
    )
      return;
    const target = item,
      destination = suiteId,
      targetId = targetKey(target, destination),
      controller = new AbortController();
    action.current = controller;
    setPending("copy");
    setSaveError("");
    setNotice("");
    const active = () => action.current === controller && !controller.signal.aborted;
    let sent = false;
    try {
      if (!(await sourceCheck(controller, target)) || !active()) return;
      sent = true;
      setCopies((values) => ({ ...values, [targetId]: { state: "unknown" } }));
      const saved = await api<unknown>(
        `/api/v1/eval-suites/${encodeURIComponent(destination)}/cases:from-conversation`,
        {
          method: "POST",
          signal: controller.signal,
          body: JSON.stringify({
            conversationId: target.conversationId,
            messageId: target.messageId,
          }),
        },
      );
      if (!active()) return;
      if (!caseValid(saved, destination) || saved.input.messages.length === 0)
        throw new Error(t("copyCaseMetadata"));
      setCopies((values) => ({ ...values, [targetId]: { state: "acknowledged", saved } }));
      const page = await api<{ items?: unknown }>(
        `/api/v1/eval-suites/${encodeURIComponent(destination)}/cases`,
        { signal: controller.signal },
      );
      if (!active()) return;
      const cases = casesFrom(page, destination, t("copyCaseMetadata"));
      const found = cases.find((value) => value.id === saved.id);
      if (!found || !sameCase(found, saved)) throw new Error(t("copyNotVerified"));
      setCopies((values) => ({ ...values, [targetId]: { state: "confirmed", saved: found } }));
      setNotice(t("added"));
    } catch (caught) {
      if (!active()) return;
      if (accessLost(caught)) {
        deny(caught instanceof Error ? caught : t("denied"));
        return;
      }
      if (sent)
        setCopies((values) =>
          values[targetId]?.saved
            ? values
            : {
                ...values,
                [targetId]: {
                  state:
                    caught instanceof ApiError && caught.code === "csrf_failed"
                      ? "refused"
                      : "unknown",
                },
              },
        );
      setSaveError(caught instanceof Error ? caught : t("error"));
    } finally {
      if (active()) {
        action.current = null;
        setPending("");
      }
    }
  }
  useEffect(() => {
    if (saveError) actionAlert.current?.focus();
  }, [saveError]);
  return (
    <section aria-label={t("feedback")}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-[var(--muted-foreground)]">{t("feedbackHelp")}</p>
        <Button
          type="button"
          variant="outline"
          disabled={loading || busy}
          onClick={() => void load()}
        >
          {t("refresh")}
        </Button>
      </div>
      {loaded && !canReadSource ? (
        <p className="mb-4 text-sm text-[var(--muted-foreground)]">{t("feedbackSourceAccess")}</p>
      ) : null}
      <fieldset
        aria-label={t("feedbackFilters")}
        className="mb-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem]"
      >
        <Input
          ref={search}
          type="search"
          aria-label={t("feedbackSearch")}
          placeholder={t("feedbackSearch")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <label className="text-sm">
          <span className="sr-only">{t("rating")}</span>
          <select
            aria-label={t("rating")}
            className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
            value={rating}
            onChange={(event) => setRating(event.target.value)}
          >
            <option value="">{t("allRatings")}</option>
            {ratings.map((value) => (
              <option key={value} value={value}>
                {t.has(`ratings.${value}`) ? t(`ratings.${value}`) : value}
              </option>
            ))}
          </select>
        </label>
      </fieldset>
      {query || rating ? (
        <Button
          type="button"
          className="mb-4"
          variant="outline"
          onClick={() => {
            setQuery("");
            setRating("");
            search.current?.focus();
          }}
        >
          {t("clearFilters")}
        </Button>
      ) : null}
      {loaded && (loading || error) ? (
        <p role="status" className="mb-3 text-sm text-[var(--muted-foreground)]">
          {t(loading ? "refreshing" : "feedbackRetained")}
        </p>
      ) : null}
      <DetailState loading={loading && !loaded} error={error} onRetry={() => void load()} />
      {loaded && matching.length === 0 ? (
        <EmptyState compact title={t(rows.length ? "noFeedbackMatches" : "noFeedback")}>
          {rows.length === 0 ? (
            <>
              <p className="mb-3 text-sm text-[var(--muted-foreground)]">
                {t("feedbackEmptyHelp")}
              </p>
              {canReadSource ? (
                <Button asChild variant="outline">
                  <Link href="/chat">{t("openChat")}</Link>
                </Button>
              ) : null}
            </>
          ) : null}
        </EmptyState>
      ) : null}
      <ul className="row-list">
        {loaded
          ? pagination.rows.map(({ row, key }) => (
              <li key={key} className="space-y-3 p-4 text-sm">
                <p className="break-words font-medium">
                  {row.agent?.name || t("unnamedAgent")} ·{" "}
                  {t.has(`ratings.${row.rating}`) ? t(`ratings.${row.rating}`) : row.rating}
                </p>
                {row.comment ? (
                  <TableScroll label={t("feedbackComment")} className="max-h-40">
                    <p className="whitespace-pre-wrap break-words text-[var(--muted-foreground)]">
                      {row.comment}
                    </p>
                  </TableScroll>
                ) : null}
                {row.createdAt ? (
                  <time
                    className="block text-xs text-[var(--muted-foreground)]"
                    dateTime={row.createdAt}
                  >
                    {formatDateTime(row.createdAt, locale)}
                  </time>
                ) : null}
                {row.messageId ? (
                  <p
                    title={row.messageId}
                    className="break-all text-xs text-[var(--muted-foreground)]"
                  >
                    {t("feedbackReference", { id: row.messageId.slice(-8) })}
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  {row.conversationId ? (
                    <Button asChild variant="outline">
                      <Link href={`/chat?conversation=${encodeURIComponent(row.conversationId)}`}>
                        {t("openConversation")}
                      </Link>
                    </Button>
                  ) : null}
                  <Button
                    variant="outline"
                    type="button"
                    aria-label={t("copyFeedbackNamed", { id: row.messageId ?? "" })}
                    disabled={
                      !row.messageId || !row.conversationId || !canReadSource || loading || busy
                    }
                    onClick={(event) => {
                      opener.current = event.currentTarget;
                      setItem(row);
                      setSuiteId("");
                      setSourceReady(false);
                      setSaveError("");
                      setNotice("");
                      void inspect(row, "");
                    }}
                  >
                    {t("addFeedback")}
                  </Button>
                </div>
              </li>
            ))
          : null}
      </ul>
      {loaded && rows.length > 0 ? <ListPagination {...pagination} label={t("feedback")} /> : null}
      <Dialog
        open={Boolean(item) && allowed}
        onOpenChange={(open) => {
          if (!open) close();
        }}
      >
        <DialogContent
          title={t("addFeedback")}
          footer={
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="outline" type="button" onClick={close}>
                {t(currentCopy?.state === "confirmed" ? "close" : "cancel")}
              </Button>
              <Button
                variant="outline"
                type="button"
                disabled={busy}
                onClick={() => item && void inspect(item, suiteId, Boolean(currentCopy))}
              >
                {t("copyRefresh")}
              </Button>
              <Button
                type="button"
                disabled={busy || loading || !suiteId || !sourceReady || Boolean(currentCopy)}
                onClick={() => void add()}
              >
                {t("addFeedback")}
              </Button>
            </div>
          }
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (opener.current?.isConnected && !opener.current.disabled) opener.current.focus();
            else search.current?.focus();
          }}
        >
          <p className="my-4 text-sm text-[var(--muted-foreground)]">
            {t("feedbackDestinationHelp")}
          </p>
          {item ? (
            <p className="mb-4 break-all text-xs text-[var(--muted-foreground)]">
              {t("feedbackReference", { id: item.messageId ?? "" })}
            </p>
          ) : null}
          <ReferencePicker
            key={item ? targetKey(item, "") : "none"}
            label={t("destinationSuite")}
            endpoint="/api/v1/eval-suites"
            value={suiteId}
            onChange={(value) => {
              setSuiteId(value);
              setSaveError("");
              setNotice("");
            }}
            required
            disabled={busy || !sourceReady}
          />
          {busy ? (
            <p role="status" className="mt-3 text-sm">
              {t(pending === "copy" ? "copyWorking" : "copyChecking")}
            </p>
          ) : null}
          {pending === "copy" ? (
            <p className="mt-3 text-sm text-[var(--muted-foreground)]">{t("copyCancelHelp")}</p>
          ) : null}
          {saveError ? (
            <div
              ref={actionAlert}
              role="alert"
              tabIndex={-1}
              className="mt-3 rounded-lg border border-[var(--border)] p-3 text-sm"
            >
              <ErrorMessage error={saveError} />
            </div>
          ) : null}
          {notice ? (
            <p role="status" className="mt-3 text-sm">
              {notice}
            </p>
          ) : null}
          {currentCopy ? (
            <p className="mt-3 text-sm text-[var(--muted-foreground)]">
              {t(
                currentCopy.state === "confirmed"
                  ? "copyConfirmed"
                  : currentCopy.state === "refused"
                    ? "copyRefused"
                    : currentCopy.state === "acknowledged"
                      ? "copyAcknowledged"
                      : "copyUnconfirmed",
              )}
            </p>
          ) : null}
          {currentCopy?.saved ? (
            <div className="mt-4">
              <CaseReceipt key={currentCopy.saved.id} value={currentCopy.saved} />
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </section>
  );
}
