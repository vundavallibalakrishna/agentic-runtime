"use client";

import { createParser } from "eventsource-parser";
import { ArrowUp, MessageSquare, Paperclip, RotateCcw, Square } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { type Attached, AttachmentList } from "@/components/chat/attachment-list";
import { MessageBody } from "@/components/chat/message-body";
import { PlanChecklist } from "@/components/chat/plan-checklist";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { ReferencePicker } from "@/components/common/reference-picker";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { shouldResumeStatus, streamHeaders, waitForResume } from "@/lib/stream/reconnect";
import {
  emptyStream,
  reduceStream,
  type StreamEvent,
  type StreamState,
} from "@/lib/stream/reducer";
import { exactOrigins } from "@/lib/widget-origins";

import { WidgetSources } from "./widget-sources";

type Message = Record<string, unknown> & { id: string; role: string; text: string };
type Session = {
  integrationId: string;
  name: string;
  csrfToken: string;
  conversationId: string | null;
  agents: { id: string; name: string }[];
  public?: boolean;
};

export function WidgetChat({ integrationId }: { integrationId: string }) {
  return <WidgetConversation key={integrationId} integrationId={integrationId} />;
}

function WidgetConversation({ integrationId }: { integrationId: string }) {
  const t = useTranslations("widget");
  const [phase, setPhase] = useState<"loading" | "waiting" | "notice" | "ready" | "error">(
    "loading",
  );
  // What a public widget tells a visitor before the chat starts, and the visitor's yes.
  const [notice, setNotice] = useState("");
  const [longest, setLongest] = useState(0);
  const [visitor, setVisitor] = useState(false);
  const accept = useRef<(() => void) | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [agentId, setAgentId] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<Attached[]>([]);
  const uploadRequest = useRef<AbortController | null>(null);
  const [uploading, setUploading] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState("");
  const [stream, setStream] = useState<StreamState>(emptyStream);
  const [attempt, setAttempt] = useState(0);
  const run = useRef("");
  const active = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const busy = stream.status === "streaming";

  const newestFirst = useMemo(() => [...messages].reverse(), [messages]);
  const history = usePagedRows(newestFirst, conversationId);

  const csrfToken = useRef("");
  const parentOrigin = useRef("");
  const [expired, setExpired] = useState(false);
  const blocked = busy || uploading || recovering || expired || !agentId;
  const request = useCallback(
    async function request<T>(
      path: string,
      init: RequestInit = {},
      csrf = csrfToken.current,
    ): Promise<T> {
      const response = await fetch(`/api/v1/widget${path}`, {
        ...init,
        credentials: "include",
        cache: "no-store",
        headers: { "content-type": "application/json", ...(csrf ? { "x-csrf-token": csrf } : {}) },
      });
      if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        throw new ApiError(problem.detail || t("requestFailed"), response.status);
      }
      return response.status === 204 ? (undefined as T) : response.json();
    },
    [t],
  );

  useEffect(() => {
    const controller = new AbortController();
    const nonce = `${attempt}-${crypto.randomUUID()}`;
    let origins: string[] = [];
    let authenticating = false;
    let timer: ReturnType<typeof setTimeout>;
    setPhase("loading");
    setSession(null);
    setAgentId("");
    csrfToken.current = "";
    parentOrigin.current = "";
    setError("");

    async function authenticate(event: MessageEvent) {
      if (
        event.source !== window.parent ||
        !origins.includes(event.origin) ||
        event.data?.type !== "ar-widget:authenticate" ||
        event.data?.nonce !== nonce ||
        event.data?.integrationId !== integrationId ||
        typeof event.data?.token !== "string" ||
        authenticating
      )
        return;
      authenticating = true;
      parentOrigin.current = event.origin;
      clearTimeout(timer);
      try {
        await enter({ integrationId, token: event.data.token });
      } catch (failure) {
        if (controller.signal.aborted) return;
        setError(
          failure instanceof ApiError && failure.status === 401 ? t("expired") : t("connectFailed"),
        );
        setPhase("error");
      }
    }

    // Start a session and open the chat in it. A public widget sends no token.
    async function enter(body: { integrationId: string; token?: string }) {
      await request("/sessions", {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify(body),
      });
      const context = await request<Session>("/session", { signal: controller.signal });
      if (context.integrationId !== integrationId) throw new Error(t("requestFailed"));
      if (controller.signal.aborted) return;
      csrfToken.current = context.csrfToken;
      setSession(context);
      setAgentId(context.agents[0]?.id ?? "");
      setConversationId("");
      setMessages([]);
      setDraft("");
      setAttachments([]);
      setStream(emptyStream);
      setExpired(false);
      setPhase("ready");
    }

    async function visit() {
      setPhase("loading");
      try {
        await enter({ integrationId });
      } catch (failure) {
        if (controller.signal.aborted) return;
        setError(failure instanceof ApiError ? failure.message : t("startFailed"));
        setPhase("error");
      }
    }
    window.addEventListener("message", authenticate);
    void (async () => {
      try {
        const policy = await request<{
          allowedOrigins: string[];
          maxMessageChars?: number | null;
          access?: string;
          notice?: string;
        }>(`/integrations/${encodeURIComponent(integrationId)}`, { signal: controller.signal });
        origins = exactOrigins(policy.allowedOrigins);
        setLongest(policy.maxMessageChars ?? 0);
        if (controller.signal.aborted) return;
        if (window.parent === window || !origins.length) throw new Error(t("embedOnly"));
        setVisitor(policy.access === "public");
        if (policy.access === "public") {
          // Nobody signs a visitor in. The page that framed this one is where Escape
          // sends its close, when it is one the widget allows.
          const from = document.referrer ? new URL(document.referrer).origin : "";
          parentOrigin.current = origins.includes(from) ? from : "";
          if (policy.notice) {
            setNotice(policy.notice);
            accept.current = () => void visit();
            setPhase("notice");
          } else await visit();
          return;
        }
        setPhase("waiting");
        // The ready message contains no credentials; only an allowed parent may answer.
        window.parent.postMessage({ type: "ar-widget:ready", integrationId, nonce }, "*");
        timer = setTimeout(() => {
          setError(t("hostWaiting"));
          setPhase("error");
        }, 15000);
      } catch (failure) {
        if (controller.signal.aborted) return;
        setError(
          failure instanceof ApiError && failure.status === 404
            ? t("unavailable")
            : failure instanceof Error
              ? failure.message
              : t("connectFailed"),
        );
        setPhase("error");
      }
    })();
    return () => {
      controller.abort();
      active.current?.abort();
      uploadRequest.current?.abort();
      clearTimeout(timer);
      window.removeEventListener("message", authenticate);
    };
  }, [integrationId, attempt, t, request]);

  useEffect(() => {
    if (history.page === 1 && (messages.length || stream.text))
      bottom.current?.scrollIntoView({ block: "end" });
  }, [history.page, messages.length, stream.text]);

  useEffect(() => {
    function close(event: KeyboardEvent) {
      if (event.key === "Escape" && parentOrigin.current)
        window.parent.postMessage({ type: "ar-widget:close", integrationId }, parentOrigin.current);
    }
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [integrationId]);

  async function followRun(runId: string, id: string, controller: AbortController) {
    run.current = runId;
    history.setPage(1);
    setStream({ ...emptyStream, status: "streaming" });
    let latest: StreamState = { ...emptyStream, status: "streaming" };
    let attempt = 0;
    while (attempt < 3) {
      let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
      try {
        const response = await fetch(`/api/v1/widget/runs/${runId}/events`, {
          credentials: "include",
          signal: controller.signal,
          cache: "no-store",
          headers: streamHeaders(latest.lastSeq),
        });
        if (!response.ok || !response.body) {
          attempt += 1;
          if (!shouldResumeStatus(response.status, attempt)) {
            throw new ApiError(t("streamFailed"), response.status);
          }
          await waitForResume(250 * attempt, controller.signal);
          continue;
        }
        const parser = createParser({
          onEvent(event) {
            latest = reduceStream(latest, JSON.parse(event.data) as StreamEvent);
            setStream(latest);
          },
        });
        reader = response.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
          const chunk = await reader.read();
          if (chunk.done) break;
          parser.feed(decoder.decode(chunk.value, { stream: true }));
        }
        break;
      } catch (error) {
        if (controller.signal.aborted) throw error;
        attempt += 1;
        if (latest.status !== "streaming" || attempt >= 3) break;
        await waitForResume(250 * attempt, controller.signal);
      } finally {
        reader?.releaseLock();
      }
    }
    const saved = await request<{ messages: Message[] }>(`/conversations/${id}`, {
      signal: controller.signal,
    });
    setMessages(saved.messages);
    setStream(emptyStream);
    if (latest.status === "failed") setError(t("runFailed"));
    else if (
      latest.status === "streaming" &&
      !saved.messages.some((message) => message.role === "assistant" && message.text)
    ) {
      setError(t("streamFailed"));
    }
  }

  async function recover() {
    if (recovering || busy || uploading) return;
    if (expired || !conversationId) {
      setAttempt((current) => current + 1);
      return;
    }
    const controller = new AbortController();
    active.current?.abort();
    active.current = controller;
    setRecovering(true);
    setError("");
    try {
      const saved = await request<{ messages: Message[]; activeRunId: string | null }>(
        `/conversations/${conversationId}`,
        { signal: controller.signal },
      );
      // A running assistant message is replayed by the stream, so show it only once.
      setMessages(
        saved.activeRunId
          ? saved.messages.filter(
              (message) => message.role !== "assistant" || message.id !== saved.messages.at(-1)?.id,
            )
          : saved.messages,
      );
      setStream(emptyStream);
      if (saved.activeRunId) await followRun(saved.activeRunId, conversationId, controller);
    } catch (failure) {
      if (controller.signal.aborted) return;
      setExpired(failure instanceof ApiError && failure.status === 401);
      setError(
        failure instanceof ApiError && failure.status === 401 ? t("expired") : t("streamFailed"),
      );
      setStream((current) => ({ ...current, status: "failed" }));
    } finally {
      if (active.current === controller) run.current = "";
      if (!controller.signal.aborted) setRecovering(false);
    }
  }

  async function onUpload(files: FileList) {
    if (phase !== "ready" || blocked || uploadRequest.current) return;
    const controller = new AbortController();
    uploadRequest.current = controller;
    setUploading(true);
    setError("");
    try {
      for (const file of Array.from(files)) {
        const body = new FormData();
        body.set("upload", file);
        body.set("mime_type", file.type);
        const response = await fetch("/api/v1/widget/files", {
          method: "POST",
          credentials: "include",
          signal: controller.signal,
          headers: csrfToken.current ? { "x-csrf-token": csrfToken.current } : {},
          body,
        });
        if (!response.ok) throw new ApiError(t("requestFailed"), response.status);
        const saved = (await response.json()) as {
          id?: string;
          name?: string;
          mimeType?: string;
          mime_type?: string;
          status?: string;
        };
        if (controller.signal.aborted) return;
        if (!saved.id) throw new Error(t("requestFailed"));
        if (saved.status && saved.status !== "ready")
          throw new Error(t("fileNotReady", { name: file.name }));
        const attached: Attached = {
          id: saved.id,
          name: saved.name || file.name,
          mimeType: saved.mimeType || saved.mime_type || file.type,
        };
        setAttachments((current) => [
          ...current.filter((item) => item.id !== attached.id),
          attached,
        ]);
      }
    } catch (failure) {
      if (controller.signal.aborted) return;
      const isExpired = failure instanceof ApiError && failure.status === 401;
      setExpired(isExpired);
      setError(
        isExpired ? t("expired") : failure instanceof Error ? failure.message : t("requestFailed"),
      );
    } finally {
      if (uploadRequest.current === controller) {
        uploadRequest.current = null;
        if (!controller.signal.aborted) setUploading(false);
      }
    }
  }

  async function send() {
    const text = draft.trim();
    if (!text || phase !== "ready" || blocked || uploadRequest.current) return;
    const controller = new AbortController();
    active.current?.abort();
    active.current = controller;
    setError("");
    setStream({ ...emptyStream, status: "streaming" });
    let accepted = false;
    let id = conversationId;
    try {
      if (!id) {
        const created = await request<{ id: string }>("/conversations", {
          method: "POST",
          body: JSON.stringify({ agentId }),
          signal: controller.signal,
        });
        id = created.id;
        setConversationId(id);
      }
      const posted = await request<{ message: Message; run: { id: string } }>(
        `/conversations/${id}/messages`,
        {
          method: "POST",
          body: JSON.stringify({
            text,
            attachmentIds: attachments.map((file) => file.id),
            suggestFollowups: true,
          }),
          signal: controller.signal,
        },
      );
      accepted = true;
      setDraft("");
      setAttachments([]);
      setMessages((current) => [...current, posted.message]);
      await followRun(posted.run.id, id, controller);
    } catch (failure) {
      if (controller.signal.aborted) return;
      if (!accepted) setDraft(text);
      setExpired(failure instanceof ApiError && failure.status === 401);
      setError(
        failure instanceof ApiError && failure.status === 401
          ? t("expired")
          : failure instanceof Error
            ? failure.message
            : t("requestFailed"),
      );
      setStream((current) => ({ ...current, status: "failed" }));
    } finally {
      if (active.current === controller) run.current = "";
    }
  }

  async function stop() {
    if (!run.current) return;
    try {
      await request(`/runs/${run.current}:cancel`, { method: "POST", body: "{}" });
    } catch {
      setError(t("stopFailed"));
    }
  }

  return (
    <main
      aria-label={t("title")}
      className="flex h-dvh min-h-0 min-w-0 flex-col bg-background text-foreground"
    >
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div className="min-w-0">
          {visitor ? null : <p className="text-xs text-muted-foreground">{t("eyebrow")}</p>}
          <h1 className="truncate text-lg font-semibold">{session?.name || t("title")}</h1>
        </div>
        {phase === "ready" && (
          <Button
            variant="ghost"
            aria-label={t("newChat")}
            title={t("newChat")}
            disabled={busy || uploading || recovering || expired}
            onClick={() => {
              setConversationId("");
              setMessages([]);
              setDraft("");
              setAttachments([]);
              setStream(emptyStream);
              setError("");
            }}
          >
            <RotateCcw size={16} />
          </Button>
        )}
      </header>
      {phase === "notice" ? (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 overflow-y-auto px-7 py-8 text-center">
          <MessageSquare size={28} className="text-muted-foreground" aria-hidden="true" />
          <h2 className="text-lg font-medium">{t("beforeYouStart")}</h2>
          <p className="max-w-sm whitespace-pre-wrap break-words text-sm leading-relaxed text-muted-foreground">
            {notice}
          </p>
          <Button onClick={() => accept.current?.()}>{t("startChat")}</Button>
        </div>
      ) : phase !== "ready" ? (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 overflow-y-auto px-7 py-8 text-center">
          <MessageSquare size={28} className="text-muted-foreground" aria-hidden="true" />
          <h2 className="text-lg font-medium">
            {phase === "error" ? t("cannotConnect") : t("connecting")}
          </h2>
          <p
            role={phase === "error" ? "alert" : "status"}
            className="max-w-sm break-words text-sm leading-relaxed text-muted-foreground"
          >
            {error || t(visitor ? "starting" : "signingIn")}
          </p>
          {phase === "error" && (
            <Button variant="outline" onClick={() => setAttempt((current) => current + 1)}>
              {t("retry")}
            </Button>
          )}
        </div>
      ) : (
        <>
          <div
            className="min-h-0 min-w-0 flex-1 overflow-y-auto px-5 py-5"
            role="log"
            aria-label={t("conversation")}
            aria-live="polite"
          >
            {!messages.length && (
              <div className="py-8">
                <MessageSquare
                  size={24}
                  className="mb-4 text-muted-foreground"
                  aria-hidden="true"
                />
                <h2 className="mb-2 text-xl font-medium">{t("welcome")}</h2>
                <p className="text-sm text-muted-foreground">
                  {session?.agents.length ? t("welcomeHint") : t("noAgents")}
                </p>
              </div>
            )}
            {messages.length > history.pageSize ? (
              <div className="mb-5 rounded-lg border border-border p-3">
                <ListPagination
                  {...history}
                  compact
                  label={t("history")}
                  previousLabel={t("newer")}
                  nextLabel={t("older")}
                />
                {history.page > 1 ? (
                  <Button
                    className="mt-3 w-full"
                    variant="ghost"
                    onClick={() => history.setPage(1)}
                  >
                    {t("latest")}
                  </Button>
                ) : null}
              </div>
            ) : null}
            {[...history.rows].reverse().map((message) => (
              <article key={message.id} className="mb-6 break-words">
                <p className="mb-1 text-xs font-medium text-muted-foreground">
                  {message.role === "user" ? t("you") : t("assistant")}
                </p>
                {message.role === "assistant" ? (
                  <>
                    <MessageBody
                      message={message}
                      onFollowup={setDraft}
                      text={message.text || ""}
                    />
                    <WidgetSources message={message} />
                  </>
                ) : (
                  <MessageBody message={message} text={message.text || ""} />
                )}
              </article>
            ))}
            {history.page === 1 && (stream.text || stream.reasoning || stream.plan.length) ? (
              <article className="mb-6 break-words">
                <p className="mb-1 text-xs font-medium text-muted-foreground">{t("assistant")}</p>
                <PlanChecklist items={stream.plan} />
                <MessageBody
                  message={{}}
                  onFollowup={setDraft}
                  prompts={stream.followups}
                  reasoning={stream.reasoning}
                  reasoningMs={stream.reasoningMs}
                  text={stream.text}
                />
              </article>
            ) : null}
            {history.page === 1 && busy && !stream.text && (
              <p role="status" className="text-sm text-muted-foreground">
                {run.current ? t("thinking") : t("sending")}
              </p>
            )}
            <div ref={bottom} />
          </div>
          {error && (
            <div className="mx-5 mb-3 rounded-lg border border-border bg-muted p-3 text-sm">
              <p role="alert">{error}</p>
              <Button
                type="button"
                variant="outline"
                className="mt-3"
                disabled={busy || uploading || recovering}
                onClick={() => void recover()}
              >
                {recovering ? t("recovering") : expired ? t("reconnect") : t("recover")}
              </Button>
            </div>
          )}
          <form
            className="shrink-0 border-t border-border bg-card p-4"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              if (event.dataTransfer.files?.length) void onUpload(event.dataTransfer.files);
            }}
            onSubmit={(event) => {
              event.preventDefault();
              void send();
            }}
          >
            {(session?.agents.length ?? 0) > 1 && (
              <div className="mb-3">
                <ReferencePicker
                  label={t("agent")}
                  items={session?.agents ?? []}
                  required
                  clearable={false}
                  value={agentId}
                  disabled={blocked || !!conversationId}
                  onChange={setAgentId}
                />
              </div>
            )}
            <AttachmentList
              busy={busy || uploading || recovering || expired}
              files={attachments}
              onRemove={(id) =>
                setAttachments((current) => current.filter((item) => item.id !== id))
              }
            />
            <input
              aria-label={t("attach")}
              className="sr-only"
              multiple
              disabled={blocked}
              onChange={(event) => {
                if (event.target.files?.length) void onUpload(event.target.files);
                event.target.value = "";
              }}
              ref={fileRef}
              type="file"
            />
            <label htmlFor="widget-message" className="sr-only">
              {t("message")}
            </label>
            <textarea
              id="widget-message"
              rows={2}
              className="w-full resize-none rounded-lg border border-border bg-background p-3 text-sm focus-visible:ring-2 focus-visible:ring-ring"
              aria-describedby="widget-composer-hint"
              maxLength={longest || undefined}
              placeholder={t("placeholder")}
              value={draft}
              disabled={busy || recovering || expired || !agentId}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  void send();
                }
              }}
            />
            <p
              role="status"
              className={uploading || recovering ? "mt-2 text-xs text-muted-foreground" : "sr-only"}
            >
              {uploading ? t("uploading") : recovering ? t("recovering") : ""}
            </p>
            <div className="mt-2 flex items-center justify-between gap-3">
              <div className="flex min-w-0 flex-1 items-center gap-2">
                {visitor ? null : (
                  <Button
                    aria-label={t("attach")}
                    className="size-9 shrink-0 p-0"
                    disabled={blocked}
                    onClick={() => fileRef.current?.click()}
                    type="button"
                    variant="ghost"
                  >
                    <Paperclip size={15} />
                  </Button>
                )}
                <p
                  id="widget-composer-hint"
                  className="min-w-0 text-[11px] leading-relaxed text-muted-foreground"
                >
                  {t("hint")}
                </p>
              </div>
              {busy ? (
                <Button
                  className="size-9 shrink-0 p-0"
                  type="button"
                  onClick={() => void stop()}
                  disabled={!run.current}
                  aria-label={run.current ? t("stop") : t("sending")}
                >
                  <Square size={15} />
                </Button>
              ) : (
                <Button
                  className="size-9 shrink-0 p-0"
                  type="submit"
                  disabled={!draft.trim() || blocked}
                  aria-label={t("send")}
                >
                  <ArrowUp size={17} />
                </Button>
              )}
            </div>
          </form>
        </>
      )}
    </main>
  );
}
