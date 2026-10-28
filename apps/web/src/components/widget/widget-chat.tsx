"use client";

import { createParser } from "eventsource-parser";
import { ArrowUp, MessageSquare, RotateCcw, Square } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { MarkdownView } from "@/components/chat/markdown-view";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  shouldResumeStatus,
  shouldResumeStream,
  streamHeaders,
  waitForResume,
} from "@/lib/stream/reconnect";
import {
  emptyStream,
  reduceStream,
  type StreamEvent,
  type StreamState,
} from "@/lib/stream/reducer";
import { exactOrigins } from "@/lib/widget-origins";

type Message = { id: string; role: string; text: string };
type Session = {
  integrationId: string;
  name: string;
  csrfToken: string;
  conversationId: string | null;
  agents: { id: string; name: string }[];
};

export function WidgetChat({ integrationId }: { integrationId: string }) {
  const t = useTranslations("widget");
  const [phase, setPhase] = useState<"loading" | "waiting" | "ready" | "error">("loading");
  const [session, setSession] = useState<Session | null>(null);
  const [agentId, setAgentId] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [stream, setStream] = useState<StreamState>(emptyStream);
  const [attempt, setAttempt] = useState(0);
  const run = useRef("");
  const active = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const busy = stream.status === "streaming";

  const csrfToken = useRef("");
  const parentOrigin = useRef("");
  const [expired, setExpired] = useState(false);
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
        await request("/sessions", {
          method: "POST",
          signal: controller.signal,
          body: JSON.stringify({ integrationId, token: event.data.token }),
        });
        const context = await request<Session>("/session", { signal: controller.signal });
        if (context.integrationId !== integrationId) throw new Error(t("requestFailed"));
        if (controller.signal.aborted) return;
        csrfToken.current = context.csrfToken;
        setSession(context);
        setAgentId(context.agents[0]?.id ?? "");
        setConversationId("");
        setMessages([]);
        setStream(emptyStream);
        setExpired(false);
        setPhase("ready");
      } catch (failure) {
        if (controller.signal.aborted) return;
        setError(
          failure instanceof ApiError && failure.status === 401 ? t("expired") : t("connectFailed"),
        );
        setPhase("error");
      }
    }
    window.addEventListener("message", authenticate);
    void (async () => {
      try {
        const policy = await request<{ allowedOrigins: string[] }>(
          `/integrations/${integrationId}`,
          { signal: controller.signal },
        );
        origins = exactOrigins(policy.allowedOrigins);
        if (controller.signal.aborted) return;
        if (window.parent === window || !origins.length) throw new Error(t("embedOnly"));
        setPhase("waiting");
        // The ready message contains no credentials; only an allowed parent may answer.
        window.parent.postMessage({ type: "ar-widget:ready", integrationId, nonce }, "*");
        timer = setTimeout(() => {
          setError(t("hostWaiting"));
          setPhase("error");
        }, 15000);
      } catch (failure) {
        if (controller.signal.aborted) return;
        setError(failure instanceof Error ? failure.message : t("connectFailed"));
        setPhase("error");
      }
    })();
    return () => {
      controller.abort();
      active.current?.abort();
      clearTimeout(timer);
      window.removeEventListener("message", authenticate);
    };
  }, [integrationId, attempt, t, request]);

  useEffect(() => {
    if (messages.length || stream.text) bottom.current?.scrollIntoView({ block: "end" });
  }, [messages.length, stream.text]);

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
    setStream({ ...emptyStream, status: "streaming" });
    let latest: StreamState = { ...emptyStream, status: "streaming" };
    let attempt = 0;
    while (attempt < 4) {
      const response = await fetch(`/api/v1/widget/runs/${runId}/events`, {
        credentials: "include",
        signal: controller.signal,
        cache: "no-store",
        headers: streamHeaders(latest.lastSeq),
      });
      if (!response.ok || !response.body) {
        attempt += 1;
        if (
          !shouldResumeStatus(response.status, attempt) ||
          !shouldResumeStream(latest.status, attempt)
        ) {
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
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      try {
        while (true) {
          const chunk = await reader.read();
          if (chunk.done) break;
          parser.feed(decoder.decode(chunk.value, { stream: true }));
        }
      } finally {
        reader.releaseLock();
      }
      if (!shouldResumeStream(latest.status, attempt + 1)) break;
      attempt += 1;
      if (!shouldResumeStream(latest.status, attempt)) break;
      await waitForResume(250 * attempt, controller.signal);
    }
    if (latest.status === "streaming") throw new Error(t("streamFailed"));
    const saved = await request<{ messages: Message[] }>(`/conversations/${id}`, {
      signal: controller.signal,
    });
    setMessages(saved.messages);
    setStream(emptyStream);
    if (latest.status === "failed") setError(t("runFailed"));
  }

  async function recover() {
    if (expired || !conversationId) {
      setAttempt((current) => current + 1);
      return;
    }
    const controller = new AbortController();
    active.current?.abort();
    active.current = controller;
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
    }
  }

  async function send() {
    const text = draft.trim();
    if (!text || busy || !agentId) return;
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
          body: JSON.stringify({ text }),
          signal: controller.signal,
        },
      );
      accepted = true;
      setDraft("");
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
      className="flex h-dvh min-h-0 flex-col bg-background text-foreground"
    >
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{t("eyebrow")}</p>
          <h1 className="truncate text-lg font-semibold">{session?.name || t("title")}</h1>
        </div>
        {phase === "ready" && (
          <Button
            variant="ghost"
            aria-label={t("newChat")}
            title={t("newChat")}
            disabled={busy}
            onClick={() => {
              setConversationId("");
              setMessages([]);
              setStream(emptyStream);
              setError("");
            }}
          >
            <RotateCcw size={16} />
          </Button>
        )}
      </header>
      {phase !== "ready" ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 px-7 text-center">
          <MessageSquare size={28} className="text-muted-foreground" aria-hidden="true" />
          <h2 className="text-lg font-medium">
            {phase === "error" ? t("cannotConnect") : t("connecting")}
          </h2>
          <p
            role={phase === "error" ? "alert" : "status"}
            className="text-sm text-muted-foreground"
          >
            {error || t("signingIn")}
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
            className="min-h-0 flex-1 overflow-y-auto px-5 py-5"
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
            {messages.map((message) => (
              <article key={message.id} className="mb-6 break-words">
                <p className="mb-1 text-xs font-medium text-muted-foreground">
                  {message.role === "user" ? t("you") : t("assistant")}
                </p>
                <MarkdownView text={message.text || ""} />
              </article>
            ))}
            {stream.text && (
              <article className="mb-6 break-words">
                <p className="mb-1 text-xs font-medium text-muted-foreground">{t("assistant")}</p>
                <MarkdownView text={stream.text} />
              </article>
            )}
            {busy && !stream.text && (
              <p role="status" className="text-sm text-muted-foreground">
                {t("thinking")}
              </p>
            )}
            <div ref={bottom} />
          </div>
          {error && (
            <div className="mx-5 mb-3 rounded-lg border border-border bg-muted p-3 text-sm">
              <p role="alert">{error}</p>
              <button type="button" className="mt-2 underline" onClick={() => void recover()}>
                {expired ? t("reconnect") : t("recover")}
              </button>
            </div>
          )}
          <form
            className="shrink-0 border-t border-border bg-card p-4"
            onSubmit={(event) => {
              event.preventDefault();
              void send();
            }}
          >
            {(session?.agents.length ?? 0) > 1 && (
              <label className="mb-3 block text-xs text-muted-foreground">
                {t("agent")}
                <select
                  className="ml-2 max-w-full rounded border border-border bg-background p-1 text-foreground"
                  value={agentId}
                  disabled={busy || !!conversationId}
                  onChange={(event) => setAgentId(event.target.value)}
                >
                  {session?.agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label htmlFor="widget-message" className="sr-only">
              {t("message")}
            </label>
            <textarea
              id="widget-message"
              rows={2}
              className="w-full resize-none bg-transparent text-sm outline-none"
              placeholder={t("placeholder")}
              value={draft}
              disabled={!agentId || busy}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  void send();
                }
              }}
            />
            <div className="mt-2 flex items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">{t("hint")}</p>
              {busy ? (
                <Button type="button" onClick={() => void stop()} aria-label={t("stop")}>
                  <Square size={15} />
                </Button>
              ) : (
                <Button type="submit" disabled={!draft.trim() || !agentId} aria-label={t("send")}>
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
