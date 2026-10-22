"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { createParser } from "eventsource-parser";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { create } from "zustand";

import { AppShell } from "@/components/app-shell";
import { CitationList, citationsOf } from "@/components/chat/citations";
import { MarkdownView } from "@/components/chat/markdown-view";
import { MemoryIndicator } from "@/components/chat/memory-indicator";
import { ToolCallCard } from "@/components/chat/tool-call-card";
import { WorkspacePanel } from "@/components/computer/workspace-panel";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { emptyStream, reduceStream, type StreamState } from "@/lib/stream/reducer";

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
  const [agentId, setAgentId] = useState("");
  const [plan, setPlan] = useState<string[]>([]);
  const draft = useComposer((state) => state.draft);
  const setDraft = useComposer((state) => state.setDraft);
  const [stream, setStream] = useState<StreamState>(emptyStream);
  const [runId, setRunId] = useState("");
  const [banner, setBanner] = useState("");
  const [attachmentName, setAttachmentName] = useState("");
  const [attachmentId, setAttachmentId] = useState("");
  const [offline, setOffline] = useState(false);
  const [live, setLive] = useState("");
  const [stuck, setStuck] = useState(false);
  const [copiedId, setCopiedId] = useState("");
  const parentRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const runRef = useRef("");
  const stickRef = useRef(true);
  const openedFromQuery = useRef(false);

  const greeting = useMemo(() => {
    const agent = agents.find((row) => row.slug === "assistant") ?? agents[0];
    return typeof agent?.greeting === "string" && agent.greeting ? agent.greeting : t("greeting");
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
      const requested = new URLSearchParams(window.location.search).get("agent");
      if (requested) {
        const match = (agentPage.items ?? []).find((row) => row.slug === requested);
        if (match?.id) {
          setAgentId(String(match.id));
        }
      }
      if (!openedFromQuery.current) {
        const conversationId = new URLSearchParams(window.location.search).get("conversation");
        if (conversationId) {
          openedFromQuery.current = true;
          const body = await api<Item & { messages?: Item[] }>(
            `/api/v1/conversations/${conversationId}`,
          );
          setActiveId(conversationId);
          setMessages(body.messages ?? []);
          setStream(emptyStream);
        }
      }
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    function onNew() {
      setActiveId("");
      setMessages([]);
      setStream(emptyStream);
      setBanner("");
      setRunId("");
    }
    window.addEventListener("ar-new-chat", onNew);
    return () => window.removeEventListener("ar-new-chat", onNew);
  }, []);

  useEffect(() => {
    function sync() {
      setOffline(!navigator.onLine);
    }
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);

  useEffect(() => {
    if (stream.status !== "streaming") {
      setLive("");
      return;
    }
    const timer = window.setTimeout(() => setLive(stream.text), 400);
    return () => window.clearTimeout(timer);
  }, [stream.status, stream.text]);

  const pin = `${messages.length}:${stream.text.length}`;
  useEffect(() => {
    const node = parentRef.current;
    if (!node || !stickRef.current || pin.length < 0) {
      return;
    }
    node.scrollTop = node.scrollHeight;
  }, [pin]);

  async function openConversation(id: string, keep?: StreamState) {
    setActiveId(id);
    const params = new URLSearchParams(window.location.search);
    params.set("conversation", id);
    window.history.replaceState(null, "", `/chat?${params.toString()}`);
    setBanner("");
    const body = await api<Item & { messages?: Item[] }>(`/api/v1/conversations/${id}`);
    setMessages(body.messages ?? []);
    setPlan(Array.isArray(body.plan) ? body.plan.map((item) => String(item)) : []);
    setStream(
      keep
        ? {
            ...emptyStream,
            memories: keep.memories,
            recalled: keep.recalled,
            compacted: keep.compacted,
          }
        : emptyStream,
    );
    stickRef.current = true;
    setStuck(false);
  }

  async function startChat() {
    const created = await api<Item>("/api/v1/conversations", {
      method: "POST",
      body: JSON.stringify(agentId ? { agentId } : {}),
    });
    const id = String(created.id);
    setConversations((current) => [created, ...current]);
    await openConversation(id);
  }

  async function readStream(id: string): Promise<StreamState> {
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
    return state;
  }

  async function undoMemory(factId: string) {
    await api(`/api/v1/memory/${factId}`, { method: "DELETE" });
    setStream((current) => ({
      ...current,
      memories: current.memories.filter((item) => item.factId !== factId),
    }));
  }

  async function send(text: string) {
    let conversationId = activeId;
    if (!conversationId) {
      const created = await api<Item>("/api/v1/conversations", {
        method: "POST",
        body: JSON.stringify(agentId ? { agentId } : {}),
      });
      conversationId = String(created.id);
      setActiveId(conversationId);
      setConversations((current) => [created, ...current]);
    }
    setBanner("");
    stickRef.current = true;
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
      const streamed = await readStream(posted.run.id);
      await openConversation(conversationId, streamed);
      const fresh = await api<{ items: Item[] }>("/api/v1/conversations");
      setConversations(fresh.items ?? []);
      runRef.current = "";
      setAttachmentId("");
      setAttachmentName("");
    } catch (error) {
      const message = error instanceof Error ? error.message : t("error");
      setBanner(message);
      if (message.toLowerCase().includes("quota")) {
        setMessages((current) => current.filter((item) => !item.id.startsWith("local-")));
      }
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
    setStream({ ...emptyStream, status: "streaming" });
    const posted = await api<{ run: { id: string } }>(
      `/api/v1/conversations/${activeId}/messages/${messageId}:regenerate`,
      { method: "POST", body: "{}" },
    );
    runRef.current = posted.run.id;
    setRunId(posted.run.id);
    const streamed = await readStream(posted.run.id);
    runRef.current = "";
    await openConversation(activeId, streamed);
  }

  async function onUpload(file: File) {
    const body = new FormData();
    body.set("upload", file);
    body.set("mime_type", file.type || "application/pdf");
    try {
      const saved = await api<{ id: string; name: string; status: string }>(
        "/api/v1/files:upload",
        {
          method: "POST",
          body,
        },
      );
      if (saved.status !== "ready") {
        setBanner(t("uploadError"));
        return;
      }
      setAttachmentId(saved.id);
      setAttachmentName(saved.name);
    } catch {
      setBanner(t("uploadError"));
    }
  }

  async function copyMessage(id: string, text: string) {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    window.setTimeout(() => setCopiedId(""), 1200);
  }

  function onScroll() {
    const node = parentRef.current;
    if (!node) {
      return;
    }
    const nearBottom = node.scrollHeight - node.scrollTop - node.clientHeight < 80;
    stickRef.current = nearBottom;
    setStuck(!nearBottom);
  }

  function grow(node: HTMLTextAreaElement) {
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 180)}px`;
  }

  const visible = messages.filter((message) => message.isActiveBranch !== false);
  const virtualizer = useVirtualizer({
    count: visible.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 120,
  });

  return (
    <AppShell flush>
      <div className="grid h-full min-h-0 min-w-0 grid-cols-1 md:grid-cols-[16rem_1fr]">
        <aside
          aria-label={t("conversations")}
          className="flex max-h-40 min-h-0 min-w-0 flex-col overflow-hidden border-b border-[var(--border)] md:max-h-none md:border-b-0 md:border-r"
        >
          <div className="px-2 pt-3">
            <Button
              className="h-8 w-full justify-start px-2 text-[13px] font-normal"
              onClick={() => void startChat()}
              type="button"
              variant="ghost"
            >
              {t("newChat")}
            </Button>
          </div>
          <nav
            aria-label={t("conversations")}
            className="mt-1 flex min-h-0 flex-1 flex-col gap-px overflow-y-auto px-2 pb-3"
          >
            {conversations.length === 0 && !loading ? (
              <p className="text-sm text-[var(--muted-foreground)]">{t("noConversations")}</p>
            ) : null}
            {conversations.map((conversation) => {
              const id = String(conversation.id);
              const selected = id === activeId;
              return (
                <button
                  aria-current={selected ? "true" : undefined}
                  className={`truncate rounded-md px-2 py-1.5 text-left text-[13px] ${selected ? "bg-[var(--muted)]" : "hover:bg-[var(--muted)]"}`}
                  key={id}
                  onClick={() => {
                    setRunId("");
                    void openConversation(id);
                  }}
                  type="button"
                >
                  {String(conversation.title || t("untitled"))}
                </button>
              );
            })}
          </nav>
        </aside>
        <section className="flex min-h-0 min-w-0 flex-col">
          <h1 className="sr-only">{t("title")}</h1>
          <p className="sr-only">{session?.tenant?.name ?? t("tenant")}</p>
          <div className="sr-only" aria-atomic="false" aria-live="polite">
            {live ? `${t("streaming")}. ${live}` : ""}
          </div>
          {loading ? (
            <div aria-busy="true" className="mx-auto w-full max-w-2xl space-y-3 px-6 py-8">
              <p className="sr-only">{t("loading")}</p>
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-5/6" />
            </div>
          ) : null}
          {loadError ? (
            <div
              className="m-6 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
              role="alert"
            >
              <p>{loadError}</p>
              <Button
                className="mt-3"
                onClick={() => void reload()}
                type="button"
                variant="outline"
              >
                {t("retry")}
              </Button>
            </div>
          ) : null}
          {!loading && !loadError && visible.length === 0 ? (
            <div className="mx-auto flex w-full max-w-xl flex-1 flex-col justify-center px-6 pb-8">
              <h2 className="font-serif text-[2rem] leading-tight tracking-tight">{greeting}</h2>
              <p className="mt-3 max-w-md text-[15px] leading-relaxed text-[var(--muted-foreground)]">
                {t("empty")}
              </p>
              <div className="mt-8 flex flex-col items-start gap-1">
                {[t("starter1"), t("starter2"), t("starter3")].map((prompt) => (
                  <Button
                    className="h-9 px-2 font-normal text-[var(--muted-foreground)]"
                    key={prompt}
                    onClick={() => void send(prompt)}
                    type="button"
                    variant="ghost"
                  >
                    {prompt}
                  </Button>
                ))}
              </div>
            </div>
          ) : null}
          <div
            className="min-h-0 flex-1 overflow-auto px-4 md:px-8"
            onScroll={onScroll}
            ref={parentRef}
          >
            <div
              className="relative mx-auto max-w-2xl"
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
                const id = String(message.id ?? row.index);
                const mine = message.role === "user";
                return (
                  <article
                    className="absolute left-0 top-0 w-full py-3"
                    data-index={row.index}
                    key={id}
                    ref={virtualizer.measureElement}
                    style={{ transform: `translateY(${row.start}px)` }}
                  >
                    <div className={mine ? "flex justify-end" : ""}>
                      <div
                        className={
                          mine
                            ? "max-w-[85%] rounded-2xl bg-[var(--muted)] px-4 py-2.5"
                            : "max-w-none"
                        }
                      >
                        <p className="sr-only">{String(message.role)}</p>
                        <MarkdownView text={body} />
                        {Array.isArray(message.toolCalls)
                          ? message.toolCalls.map((call) => {
                              const row =
                                call && typeof call === "object"
                                  ? (call as Record<string, unknown>)
                                  : {};
                              const toolKey = `${id}-${String(row.qualifiedName ?? "tool")}-${String(row.resultPreview ?? row.status ?? "")}`;
                              return (
                                <ToolCallCard call={row} key={toolKey} label={t("toolCall")} />
                              );
                            })
                          : null}
                        <CitationList
                          citations={
                            streamingHere && stream.citations.length
                              ? stream.citations
                              : citationsOf(message)
                          }
                          conversationId={activeId}
                          messageId={id}
                        />
                        {streamingHere ? <span aria-hidden="true" className="caret" /> : null}
                      </div>
                    </div>
                    <div className={`mt-1 flex gap-1 ${mine ? "justify-end" : ""}`}>
                      <Button
                        className="h-7 px-2 text-xs font-normal text-[var(--muted-foreground)]"
                        onClick={() => void copyMessage(id, body)}
                        type="button"
                        variant="ghost"
                      >
                        {copiedId === id ? t("copied") : t("copy")}
                      </Button>
                      {message.role === "assistant" && id && !id.startsWith("local-") ? (
                        <Button
                          className="h-7 px-2 text-xs font-normal text-[var(--muted-foreground)]"
                          onClick={() => void regenerate(id)}
                          type="button"
                          variant="ghost"
                        >
                          {t("regenerate")}
                        </Button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
          {stuck ? (
            <div className="flex justify-center">
              <Button
                onClick={() => {
                  stickRef.current = true;
                  setStuck(false);
                  if (parentRef.current) {
                    parentRef.current.scrollTop = parentRef.current.scrollHeight;
                  }
                }}
                type="button"
                variant="outline"
              >
                {t("jump")}
              </Button>
            </div>
          ) : null}
          {offline ? (
            <p className="px-6 text-sm" role="status">
              {t("offline")}
            </p>
          ) : null}
          {banner ? (
            <p className="px-6 text-sm" role="alert">
              {banner}
            </p>
          ) : null}
          <div className="mx-auto w-full max-w-2xl px-4 md:px-8">
            <MemoryIndicator
              compacted={stream.compacted}
              memories={stream.memories}
              onUndo={(factId) => void undoMemory(factId)}
              recalled={stream.recalled}
            />
          </div>
          {activeId ? (
            <WorkspacePanel conversationId={activeId} revision={messages.length} />
          ) : null}
          <form
            className="px-4 pb-4 md:px-8"
            onSubmit={(event) => {
              event.preventDefault();
              const text = draft.trim();
              if (!text || stream.status === "streaming") {
                return;
              }
              setDraft("");
              if (composerRef.current) {
                composerRef.current.style.height = "auto";
              }
              void send(text);
            }}
          >
            {plan.length > 0 ? (
              <section className="mx-auto mb-3 max-w-2xl rounded-xl border border-[var(--border)] px-3 py-2 text-sm">
                <h2 className="font-medium">{t("plan")}</h2>
                <ul>
                  {plan.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ul>
              </section>
            ) : null}
            {runId ? (
              <p className="mx-auto mb-2 max-w-2xl text-sm">
                <a className="underline" href={`/runs/${runId}`}>
                  {t("viewTrace")}
                </a>
              </p>
            ) : null}
            <div className="mx-auto flex max-w-2xl flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] px-3 py-2">
              <label className="sr-only" htmlFor="agent-picker">
                {t("agent")}
              </label>
              <select
                className="mb-1 max-w-xs bg-transparent text-sm text-[var(--muted-foreground)]"
                id="agent-picker"
                onChange={(event) => setAgentId(event.target.value)}
                value={agentId}
              >
                <option value="">{t("agent")}</option>
                {agents.map((agent) => (
                  <option key={String(agent.id)} value={String(agent.id)}>
                    {String(agent.name ?? agent.slug)}
                  </option>
                ))}
              </select>
              {attachmentName ? (
                <p className="px-1 pb-1 text-xs text-[var(--muted-foreground)]">
                  {t("attached")}: {attachmentName}
                </p>
              ) : null}
              <label className="sr-only" htmlFor="composer">
                {t("composer")}
              </label>
              <textarea
                className="max-h-44 min-h-12 w-full resize-none border-0 bg-transparent px-1 py-1 text-[15px]"
                id="composer"
                onChange={(event) => {
                  setDraft(event.target.value);
                  grow(event.currentTarget);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                placeholder={t("placeholder")}
                ref={composerRef}
                rows={2}
                value={draft}
              />
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <input
                    accept="application/pdf,text/plain,text/csv,.csv,image/png"
                    aria-label={t("attach")}
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
                  <Button
                    className="h-8 px-2 text-xs font-normal text-[var(--muted-foreground)]"
                    onClick={() => fileRef.current?.click()}
                    type="button"
                    variant="ghost"
                  >
                    {t("attach")}
                  </Button>
                  <p className="hidden text-xs text-[var(--muted-foreground)] sm:block">
                    {t("hint")}
                  </p>
                </div>
                {stream.status === "streaming" ? (
                  <Button
                    className="h-8 px-3 text-xs"
                    onClick={() => void stop()}
                    type="button"
                    variant="outline"
                  >
                    {t("stop")}
                  </Button>
                ) : (
                  <Button className="h-8 px-3 text-xs" type="submit">
                    {t("send")}
                  </Button>
                )}
              </div>
            </div>
          </form>
        </section>
      </div>
    </AppShell>
  );
}
