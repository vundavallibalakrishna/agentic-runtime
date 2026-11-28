"use client";

import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { ActionStatus, DetailState, ErrorMessage } from "@/components/common/detail-state";
import { ReferencePicker } from "@/components/common/reference-picker";
import { Button } from "@/components/ui/button";
import { ApiError, api, type DisplayError } from "@/lib/api";
import { loadSession } from "@/lib/session";

type Queue = { id: string; name?: string; subjectType: string };
type Tenant = { settings?: { approvals?: { replyReviewQueueId?: string | null } } };

/** The existing tenant setting selects a real message queue; Off is an explicit choice. */
export function ReplyAcceptanceSettings() {
  const t = useTranslations("reviews");
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [readDenied, setReadDenied] = useState(false);
  const [queues, setQueues] = useState<Queue[] | null>(null);
  const [saved, setSaved] = useState<{ queueId: string } | null>(null);
  const [chosen, setChosen] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<DisplayError>("");
  const [loadError, setLoadError] = useState<DisplayError>("");
  const [notice, setNotice] = useState("");
  const [recovery, setRecovery] = useState(false);
  const readRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const savedRef = useRef<{ queueId: string } | null>(null);
  const feedback = useRef<HTMLDivElement>(null);
  const busy = loading || saving;

  const load = useCallback(
    async (apply = false) => {
      if (actionRequest.current || readRequest.current) return;
      const request = new AbortController();
      readRequest.current = request;
      setLoading(true);
      setLoadError("");
      setNotice("");
      try {
        const session = await loadSession();
        if (request.signal.aborted) return;
        const held = session.permissions ?? [];
        const canManage = held.includes("tenant:manage") && held.includes("reviews:read");
        setAllowed(canManage);
        setReadDenied(canManage && !held.includes("tenant:read"));
        if (!canManage || !held.includes("tenant:read")) {
          setQueues(null);
          setSaved(null);
          savedRef.current = null;
          return;
        }
        const [tenant, listed] = await Promise.all([
          api<Tenant>("/api/v1/tenant", { signal: request.signal }),
          api<{ items?: Queue[] }>("/api/v1/review-queues", { signal: request.signal }),
        ]);
        if (request.signal.aborted) return;
        const id = tenant?.settings?.approvals?.replyReviewQueueId;
        if (
          (id !== null && (typeof id !== "string" || !id.trim())) ||
          !Array.isArray(listed?.items) ||
          listed.items.some(
            (queue) =>
              !queue ||
              typeof queue.id !== "string" ||
              !queue.id.trim() ||
              typeof queue.subjectType !== "string" ||
              (queue.name !== undefined && typeof queue.name !== "string"),
          )
        ) {
          throw new Error(t("replyMetadataError"));
        }
        const next = { queueId: id ?? "" };
        if (apply || !savedRef.current) setChosen(next.queueId);
        savedRef.current = next;
        setSaved(next);
        setQueues(listed.items.filter((queue) => queue.subjectType === "message"));
        setError("");
        setRecovery(false);
      } catch (caught) {
        if (!request.signal.aborted) {
          setLoadError(caught instanceof Error ? caught : t("error"));
          if (caught instanceof ApiError && [401, 403, 404].includes(caught.status)) {
            setQueues(null);
            setSaved(null);
            savedRef.current = null;
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

  const dirty = saved !== null && chosen !== saved.queueId;
  const unavailable = Boolean(chosen && !queues?.some((queue) => queue.id === chosen));
  async function save(event: FormEvent) {
    event.preventDefault();
    if (
      actionRequest.current ||
      readRequest.current ||
      !allowed ||
      !saved ||
      queues === null ||
      loadError ||
      recovery ||
      !dirty ||
      unavailable
    )
      return;
    const request = new AbortController();
    actionRequest.current = request;
    setSaving(true);
    setError("");
    setNotice("");
    const submitted = chosen;
    try {
      const result = await api<Tenant>("/api/v1/tenant", {
        method: "PATCH",
        signal: request.signal,
        body: JSON.stringify({
          settings: { approvals: { replyReviewQueueId: submitted || null } },
        }),
      });
      if (request.signal.aborted) return;
      if (result?.settings?.approvals?.replyReviewQueueId !== (submitted || null))
        throw new Error(t("replyUnconfirmed"));
      const next = { queueId: submitted };
      savedRef.current = next;
      setSaved(next);
      setNotice(t("replySaved"));
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
    <section aria-labelledby="reply-acceptance" className="mt-10">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold" id="reply-acceptance">
            {t("replyTitle")}
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-[var(--muted-foreground)]">
            {t("replyBody")}
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          disabled={busy}
          aria-label={t("replyRefresh")}
          onClick={() => void load()}
        >
          <RefreshCw size={16} aria-hidden="true" />
        </Button>
      </div>
      <DetailState
        loading={loading}
        error={loadError}
        onRetry={busy ? undefined : () => void load()}
      />
      {readDenied ? <p className="text-sm">{t("replyReadDenied")}</p> : null}
      {allowed && queues !== null && saved ? (
        <form
          className="grid gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
          onSubmit={(event) => void save(event)}
        >
          <p className="text-sm text-[var(--muted-foreground)]">
            {t("replySavedChoice", {
              queue: saved.queueId
                ? queues.find((queue) => queue.id === saved.queueId)?.name || saved.queueId
                : t("replyOff"),
            })}
          </p>
          <div className="grid gap-1">
            <p className="text-sm">{t("replyQueue")}</p>
            <ReferencePicker<Queue>
              hideLabel
              items={queues}
              selection={
                unavailable
                  ? {
                      id: chosen,
                      name: t("replyUnavailable", { id: chosen }),
                      subjectType: "message",
                    }
                  : null
              }
              label={t("replyQueue")}
              value={chosen}
              onChange={(value) => {
                setChosen(value);
                setNotice("");
              }}
              disabled={busy || Boolean(loadError) || recovery}
              emptyLabel={t("replyOff")}
              resetLabel={t("replyOff")}
              emptyMessage={t("replyNoQueues")}
              help={t("replyChoiceHelp")}
            />
          </div>
          {unavailable ? <p className="break-words text-sm">{t("replyUnavailableHelp")}</p> : null}
          {queues.length === 0 ? (
            <p className="text-xs leading-relaxed text-[var(--muted-foreground)]">
              {t("replyNoQueues")}
            </p>
          ) : null}
          {dirty ? (
            <p className="text-sm text-[var(--muted-foreground)]">{t("replyUnsaved")}</p>
          ) : null}
          {recovery ? <p className="text-sm">{t("replyRecovery")}</p> : null}
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
          <ActionStatus busy={saving} busyLabel={t("replySaving")} notice={notice} />
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={busy || Boolean(loadError) || recovery || !dirty || unavailable}
              type="submit"
            >
              {t("replySave")}
            </Button>
            {dirty ? (
              <Button
                variant="outline"
                type="button"
                disabled={busy}
                onClick={() => {
                  setChosen(saved.queueId);
                  setNotice("");
                }}
              >
                {t("replyUseSaved")}
              </Button>
            ) : null}
          </div>
        </form>
      ) : null}
    </section>
  );
}
