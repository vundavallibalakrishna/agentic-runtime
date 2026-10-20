"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { createParser } from "eventsource-parser";
import mermaid from "mermaid";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { createHighlighter } from "shiki";
import { create } from "zustand";

import { Button } from "@/components/ui/button";
import { sanitizeHtml } from "@/lib/markdown";
import { emptyStream, reduceStream, type StreamState } from "@/lib/stream/reducer";

import "katex/dist/katex.min.css";

type Item = Record<string, unknown>;

const useComposer = create<{ draft: string; setDraft: (value: string) => void }>((set) => ({
  draft: "",
  setDraft: (draft) => set({ draft }),
}));

type Session = {
  user?: { email?: string; displayName?: string };
  tenant?: { name?: string; id?: string };
  permissions?: string[];
};

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|; )ar_csrf=([^;]*)/);
  return match?.[1] ? decodeURIComponent(match[1]) : "";
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  headers.set("x-csrf-token", csrfToken());
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const problem = (await response.json()) as { detail?: string };
      detail = problem.detail ?? detail;
    } catch {
      detail = response.statusText;
    }
    throw new Error(detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function textOf(message: Item): string {
  if (typeof message.text === "string") {
    return message.text;
  }
  const content = message.content;
  if (Array.isArray(content) && content[0] && typeof content[0] === "object") {
    const part = content[0] as { text?: string };
    return part.text ?? "";
  }
  return "";
}

export function ChatScreen() {
  const t = useTranslations("chat");
  const [session, setSession] = useState<Session | null>(null);
  const [loadError, setLoadError] = useState("");
  const [loading, setLoading] = useState(true);
  const [conversations, setConversations] = useState<Item[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [messages, setMessages] = useState<Item[]>([]);
  const [agents, setAgents] = useState<Item[]>([]);
  const draft = useComposer((state) => state.draft);
  const setDraft = useComposer((state) => state.setDraft);
  const [stream, setStream] = useState<StreamState>(emptyStream);
  const [runId, setRunId] = useState("");
  const [banner, setBanner] = useState("");
  const [attachmentName, setAttachmentName] = useState("");
  const [attachmentId, setAttachmentId] = useState("");
  const parentRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const runRef = useRef("");

  useEffect(() => {
    void createHighlighter({ themes: ["github-light"], langs: ["text"] }).catch(() => undefined);
    mermaid.initialize({ startOnLoad: false });
  }, []);

  const greeting = useMemo(() => {
    const agent = agents[0];
    return typeof agent?.greeting === "string" ? agent.greeting : t("greeting");
  }, [agents, t]);

  const reload = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const me = await api<Session>("/api/v1/auth/session");
      setSession(me);
      const listed = await api<{ items: Item[] }>("/api/v1/conversations");
      const agentPage = await api<{ items: Item[] }>("/api/v1/agents");
      setConversations(listed.items ?? []);
      setAgents(agentPage.items ?? []);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function openConversation(id: string) {
    setActiveId(id);
    setBanner("");
    const body = await api<Item & { messages?: Item[] }>(`/api/v1/conversations/${id}`);
    setMessages(body.messages ?? []);
    setStream(emptyStream);
  }

  async function startChat() {
    const created = await api<Item>("/api/v1/conversations", {
      method: "POST",
      body: JSON.stringify({}),
    });
    const id = String(created.id);
    setConversations((current) => [created, ...current]);
    await openConversation(id);
  }

  async function readStream(id: string) {
    const response = await fetch(`/api/v1/runs/${id}/events`, { credentials: "include" });
    if (!response.ok || !response.body) {
      throw new Error(t("error"));
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let state = emptyStream;
    const parser = createParser({
      onEvent(event) {
        const payload = JSON.parse(event.data) as {
          type: string;
          seq: number;
          data?: { text?: string };
        };
        state = reduceStream(state, payload);
        setStream(state);
        if (payload.type === "message.completed" || payload.type === "run.cancelled") {
          setMessages((current) => {
            const next = [...current];
            const last = next[next.length - 1];
            if (last && last.role === "assistant") {
              next[next.length - 1] = { ...last, text: state.text, status: state.status };
            }
            return next;
          });
        }
      },
    });
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) {
        break;
      }
      parser.feed(decoder.decode(chunk.value, { stream: true }));
    }
  }

  async function send(text: string) {
    let conversationId = activeId;
    if (!conversationId) {
      const created = await api<Item>("/api/v1/conversations", {
        method: "POST",
        body: JSON.stringify({}),
      });
      conversationId = String(created.id);
      setActiveId(conversationId);
      setConversations((current) => [created, ...current]);
    }
    setBanner("");
    setMessages((current) => [
      ...current,
      { id: `local-${Date.now()}`, role: "user", text, isActiveBranch: true },
      {
        id: `local-a-${Date.now()}`,
        role: "assistant",
        text: "",
        status: "streaming",
        isActiveBranch: true,
      },
    ]);
    setStream({ ...emptyStream, status: "streaming" });
    try {
      const posted = await api<{ run: { id: string } }>(
        `/api/v1/conversations/${conversationId}/messages`,
        {
          method: "POST",
          body: JSON.stringify({
            text,
            attachmentIds: attachmentId ? [attachmentId] : [],
          }),
        },
      );
      runRef.current = posted.run.id;
      setRunId(posted.run.id);
      await readStream(posted.run.id);
      await openConversation(conversationId);
      const fresh = await api<{ items: Item[] }>("/api/v1/conversations");
      setConversations(fresh.items ?? []);
      runRef.current = "";
      setRunId("");
    } catch (error) {
      setBanner(error instanceof Error ? error.message : t("error"));
      setStream((current) => ({ ...current, status: "failed" }));
    }
  }

  async function stop() {
    const id = runRef.current || runId;
    if (!id) {
      return;
    }
    await api(`/api/v1/runs/${id}:cancel`, { method: "POST", body: "{}" });
  }

  async function regenerate(messageId: string) {
    if (!activeId || messageId.startsWith("local-")) {
      return;
    }
    const posted = await api<{ run: { id: string } }>(
      `/api/v1/conversations/${activeId}/messages/${messageId}:regenerate`,
      { method: "POST", body: "{}" },
    );
    setRunId(posted.run.id);
    await readStream(posted.run.id);
    await openConversation(activeId);
  }

  async function onUpload(file: File) {
    const body = new FormData();
    body.set("upload", file);
    body.set("mime_type", file.type || "application/pdf");
    const headers = new Headers();
    headers.set("x-csrf-token", csrfToken());
    const response = await fetch("/api/v1/files:upload", {
      method: "POST",
      body,
      headers,
      credentials: "include",
    });
    if (!response.ok) {
      setBanner(t("uploadError"));
      return;
    }
    const saved = (await response.json()) as { id: string; name: string; status: string };
    if (saved.status !== "ready") {
      setBanner(t("uploadError"));
      return;
    }
    setAttachmentId(saved.id);
    setAttachmentName(saved.name);
  }

  const visible = messages.filter((message) => message.isActiveBranch !== false);
  const virtualizer = useVirtualizer({
    count: visible.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 96,
  });

  return (
    <div className="grid h-screen grid-cols-[280px_1fr]">
      <aside className="flex flex-col border-r border-[var(--border)] bg-[var(--card)] p-4">
        <p className="text-sm font-semibold">{t("product")}</p>
        <p className="mt-1 text-xs text-[var(--muted)]">{session?.user?.email ?? t("signedOut")}</p>
        <Button className="mt-4" onClick={() => void startChat()} type="button">
          {t("newChat")}
        </Button>
        <nav
          aria-label={t("conversations")}
          className="mt-4 flex flex-1 flex-col gap-1 overflow-auto"
        >
          {conversations.length === 0 && !loading ? (
            <p className="text-sm text-[var(--muted)]">{t("noConversations")}</p>
          ) : null}
          {conversations.map((conversation) => (
            <button
              className="rounded-md px-2 py-2 text-left text-sm hover:bg-[var(--background)]"
              key={String(conversation.id)}
              onClick={() => void openConversation(String(conversation.id))}
              type="button"
            >
              {String(conversation.title || t("untitled"))}
            </button>
          ))}
        </nav>
        <a className="mt-3 text-sm underline" href="/admin/models">
          {t("models")}
        </a>
      </aside>
      <section className="flex min-h-0 flex-col">
        <header className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold">{t("title")}</h1>
            <p className="text-sm text-[var(--muted)]">{session?.tenant?.name ?? t("tenant")}</p>
          </div>
          <a className="text-sm underline" href="/platform/health">
            {t("health")}
          </a>
        </header>
        {loading ? <p className="p-6 text-sm">{t("loading")}</p> : null}
        {loadError ? (
          <div className="m-6 rounded-md border border-[var(--border)] p-4" role="alert">
            <p>{loadError}</p>
            <Button className="mt-3" onClick={() => void reload()} type="button" variant="outline">
              {t("retry")}
            </Button>
          </div>
        ) : null}
        {!loading && !loadError && visible.length === 0 ? (
          <div className="mx-auto max-w-xl p-10 text-center">
            <h2 className="text-2xl font-semibold">{greeting}</h2>
            <p className="mt-2 text-[var(--muted)]">{t("empty")}</p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {[t("starter1"), t("starter2"), t("starter3")].map((prompt) => (
                <Button
                  key={prompt}
                  onClick={() => void send(prompt)}
                  type="button"
                  variant="outline"
                >
                  {prompt}
                </Button>
              ))}
            </div>
          </div>
        ) : null}
        <div className="min-h-0 flex-1 overflow-auto px-6" ref={parentRef}>
          <div
            className="relative mx-auto max-w-3xl"
            style={{ height: virtualizer.getTotalSize() }}
          >
            {virtualizer.getVirtualItems().map((row) => {
              const message = visible[row.index];
              if (!message) {
                return null;
              }
              const streamingHere =
                row.index === visible.length - 1 &&
                message.role === "assistant" &&
                stream.status === "streaming";
              const body = streamingHere ? stream.text || textOf(message) : textOf(message);
              return (
                <article
                  className="absolute left-0 top-0 w-full py-3"
                  data-index={row.index}
                  key={String(message.id)}
                  ref={virtualizer.measureElement}
                  style={{ transform: `translateY(${row.start}px)` }}
                >
                  <p className="text-xs uppercase tracking-wide text-[var(--muted)]">
                    {String(message.role)}
                  </p>
                  <div className="prose mt-1 max-w-none text-sm">
                    <ReactMarkdown
                      rehypePlugins={[rehypeKatex, rehypeSanitize]}
                      remarkPlugins={[remarkGfm]}
                    >
                      {sanitizeHtml(body)}
                    </ReactMarkdown>
                  </div>
                  {message.role === "assistant" &&
                  message.id &&
                  !String(message.id).startsWith("local-") ? (
                    <Button
                      className="mt-2"
                      onClick={() => void regenerate(String(message.id))}
                      type="button"
                      variant="outline"
                    >
                      {t("regenerate")}
                    </Button>
                  ) : null}
                </article>
              );
            })}
          </div>
        </div>
        {banner ? (
          <p className="px-6 text-sm" role="alert">
            {banner}
          </p>
        ) : null}
        <form
          className="border-t border-[var(--border)] p-4"
          onSubmit={(event) => {
            event.preventDefault();
            const text = draft.trim();
            if (!text) {
              return;
            }
            setDraft("");
            void send(text);
          }}
        >
          <div className="mx-auto flex max-w-3xl flex-col gap-2">
            {attachmentName ? (
              <p className="text-xs text-[var(--muted)]">
                {t("attached")}: {attachmentName}
              </p>
            ) : null}
            <label className="sr-only" htmlFor="composer">
              {t("composer")}
            </label>
            <textarea
              className="min-h-20 rounded-md border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
              id="composer"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder={t("placeholder")}
              value={draft}
            />
            <div className="flex items-center justify-between gap-2">
              <div className="flex gap-2">
                <input
                  accept="application/pdf,text/plain,image/png"
                  className="sr-only"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) {
                      void onUpload(file);
                    }
                  }}
                  ref={fileRef}
                  type="file"
                />
                <Button onClick={() => fileRef.current?.click()} type="button" variant="outline">
                  {t("attach")}
                </Button>
              </div>
              {stream.status === "streaming" ? (
                <Button onClick={() => void stop()} type="button" variant="outline">
                  {t("stop")}
                </Button>
              ) : (
                <Button type="submit">{t("send")}</Button>
              )}
            </div>
          </div>
        </form>
      </section>
    </div>
  );
}
