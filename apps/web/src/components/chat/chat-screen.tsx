"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { createParser } from "eventsource-parser";
import {
  ArrowUp,
  ArrowUpRight,
  Check,
  Copy,
  FileText,
  History,
  Lightbulb,
  MessageSquare,
  PanelRight,
  Paperclip,
  PenLine,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { create } from "zustand";
import { AppShell } from "@/components/app-shell";
import { type Attached, AttachmentList, attachedOf } from "@/components/chat/attachment-list";
import {
  CitationList,
  citationsOf,
  ReadingNote,
  ReviewTable,
  readingOf,
  reviewsOf,
} from "@/components/chat/citations";
import { DocumentPicker, mentionStarted } from "@/components/chat/document-picker";
import { FailedReply } from "@/components/chat/failed-reply";
import { FeedbackButtons } from "@/components/chat/feedback-buttons";
import { MarkdownView } from "@/components/chat/markdown-view";
import { MemoryIndicator } from "@/components/chat/memory-indicator";
import { MessageBody } from "@/components/chat/message-body";
import { PlanChecklist, planItems } from "@/components/chat/plan-checklist";
import { AcceptReply, type ReplyReview, ReplyReviewStatus } from "@/components/chat/reply-review";
import { RunDetails } from "@/components/chat/run-details";
import { JobList, ToolCallCard } from "@/components/chat/tool-call-card";
import { ErrorMessage } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { ReferencePicker } from "@/components/common/reference-picker";
import { WorkspacePanel } from "@/components/computer/workspace-panel";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { isAvailableAgent } from "@/lib/agent-availability";
import type { DisplayError } from "@/lib/api";
import { ApiError, api } from "@/lib/api";
import { chatAliases } from "@/lib/model-aliases";
import { loadSession } from "@/lib/session";
import { LATE_MEMORY_WAITS_MS, lateMemoryEvents } from "@/lib/stream/late";
import {
  shouldResumeStatus,
  shouldResumeStream,
  streamHeaders,
  waitForResume,
} from "@/lib/stream/reconnect";
import { emptyStream, type PlanStep, reduceStream, type StreamState } from "@/lib/stream/reducer";
import { cn } from "@/lib/utils";

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

// Whether the run details panel is open, remembered for this browser.
const DETAILS_KEY = "ar-chat-details";

function isTerminalRunStatus(status: string): boolean {
  return ["completed", "failed", "cancelled", "interrupted"].includes(status);
}

function agentReference(agent: Item) {
  return {
    id: String(agent.id),
    name: String(agent.name ?? agent.slug ?? agent.id),
    slug: typeof agent.slug === "string" ? agent.slug : "",
  };
}

/** Resolve saved speakers from the full catalogue, including archived agents. */
function replyName(
  message: Item,
  agents: ReadonlyMap<string, Item>,
  fallback: string,
  conversationAgentId: string,
): string {
  const agent = agents.get(String(message.agentId || conversationAgentId));
  return String(agent?.name ?? agent?.slug ?? fallback);
}

/** The run that wrote a reply, for the link to its trace. */
function traceOf(message: Item, current: string): string {
  return String((message as { runId?: string }).runId || current || "");
}

function planFrom(value: unknown): PlanStep[] {
  return planItems(value);
}

function conversationBody(agentId: string, modelAlias: string): string {
  const body: Record<string, string> = {};
  if (agentId) body.agentId = agentId;
  if (modelAlias) body.modelAlias = modelAlias;
  return JSON.stringify(body);
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
  const availability = useTranslations("agentAvailability");
  const [session, setSession] = useState<Session | null>(null);
  const [loadError, setLoadError] = useState<DisplayError>("");
  const [loading, setLoading] = useState(true);
  const [conversations, setConversations] = useState<Item[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [conversationAgentId, setConversationAgentId] = useState("");
  const [savedRun, setSavedRun] = useState<{ conversationId: string; runId: string } | null>(null);
  const [messages, setMessages] = useState<Item[]>([]);
  const [jobs, setJobs] = useState<Item[]>([]);
  const [agents, setAgents] = useState<Item[]>([]);
  const [aliases, setAliases] = useState<string[]>([]);
  const [agentId, setAgentId] = useState("");
  const [modelAlias, setModelAlias] = useState("");
  const aliasChoices = useMemo(
    () => aliases.map((alias) => ({ id: alias, name: alias })),
    [aliases],
  );
  const agentIndex = useMemo(
    () => new Map(agents.filter((agent) => agent.id).map((agent) => [String(agent.id), agent])),
    [agents],
  );
  const agentChoices = useMemo(
    () => agents.filter((agent) => agent.id && isAvailableAgent(agent)).map(agentReference),
    [agents],
  );
  const availableAgentIds = useMemo(
    () => new Set(agentChoices.map((agent) => agent.id)),
    [agentChoices],
  );
  const defaultAgent = useMemo(
    () => agents.find((agent) => agent.slug === "assistant" && isAvailableAgent(agent)),
    [agents],
  );
  const defaultAgentName =
    typeof defaultAgent?.name === "string" ? defaultAgent.name : t("defaultAgent");
  const selectedAgent = agentIndex.get(agentId);
  const [agentProblem, setAgentProblem] = useState(false);
  const canStartChat =
    !agentProblem && (agentId ? availableAgentIds.has(agentId) : Boolean(defaultAgent));
  const [modelAction, setModelAction] = useState<"saving" | "refreshing" | null>(null);
  const modelSaving = modelAction !== null;
  const [modelNotice, setModelNotice] = useState("");
  const [modelProblem, setModelProblem] = useState<DisplayError>("");
  const [conversationLoading, setConversationLoading] = useState(false);
  const [conversationProblem, setConversationProblem] = useState(false);
  const [runAction, setRunAction] = useState<
    "create" | "send" | "generate" | "regenerate" | "edit" | "resume" | "refresh" | null
  >(null);
  const [runIssue, setRunIssue] = useState<{
    detail: DisplayError;
    accepted: boolean;
    runId?: string;
    status?: string;
    action?: "send";
    cancelRequested?: boolean;
  } | null>(null);
  const submitting = runAction === "send" || runAction === "create";
  const [runNotice, setRunNotice] = useState("");
  const actionRequest = useRef<AbortController | null>(null);
  const modelRequest = useRef<AbortController | null>(null);
  const cancelRequest = useRef<AbortController | null>(null);
  const [cancelState, setCancelState] = useState<"requesting" | "requested" | null>(null);
  const [cancelError, setCancelError] = useState<DisplayError>("");
  const selectedConversation = useRef("");
  const [plan, setPlan] = useState<PlanStep[]>([]);
  const draft = useComposer((state) => state.draft);
  const setDraft = useComposer((state) => state.setDraft);
  const [stream, setStream] = useState<StreamState>(emptyStream);
  const [runId, setRunId] = useState("");
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null);
  const [banner, setBannerState] = useState<{ error: DisplayError; prefix?: string } | null>(null);
  const setBanner = useCallback((error: DisplayError, prefix?: string) => {
    setBannerState(error ? { error, prefix } : null);
  }, []);
  const [attachments, setAttachments] = useState<Attached[]>([]);
  const [picking, setPicking] = useState(false);
  const uploadRequest = useRef<AbortController | null>(null);
  const [uploadState, setUploadState] = useState<{
    name: string;
    index: number;
    total: number;
  } | null>(null);
  const [uploadIssue, setUploadIssue] = useState<{
    name: string;
    detail: DisplayError;
    remaining: number;
  } | null>(null);
  const [uploadNotice, setUploadNotice] = useState("");
  const uploading = uploadState !== null;
  const attachmentBlocked =
    loading ||
    Boolean(loadError) ||
    conversationLoading ||
    conversationProblem ||
    submitting ||
    uploading;
  const [accept, setAccept] = useState("");
  const [offline, setOffline] = useState(false);
  const [live, setLive] = useState("");
  const [stuck, setStuck] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyQuery, setHistoryQuery] = useState("");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [researchOn, setResearchOn] = useState(false);
  const [taskTemplate, setTaskTemplate] = useState("");
  const [checklist, setChecklist] = useState("");
  const [collectionIds, setCollectionIds] = useState("");
  const [copiedId, setCopiedId] = useState("");
  const parentRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const runRef = useRef("");
  // The finished run whose stream is read again for memories saved after the answer.
  const lateRunRef = useRef("");
  const streamRequest = useRef<AbortController | null>(null);
  const conversationRequest = useRef<AbortController | null>(null);
  // The conversation "New chat" is creating, until it is open. A message sent meanwhile
  // waits for it and goes there.
  const opening = useRef<Promise<string> | null>(null);
  const stickRef = useRef(true);
  const openedFromQuery = useRef(false);
  const editFieldRef = useRef<HTMLTextAreaElement>(null);
  const previousEdit = useRef("");
  const generationBlocked =
    loading ||
    Boolean(loadError) ||
    modelSaving ||
    Boolean(modelProblem) ||
    conversationLoading ||
    conversationProblem ||
    Boolean(runAction) ||
    Boolean(savedRun) ||
    uploading ||
    Boolean(uploadIssue) ||
    Boolean(runIssue) ||
    (!activeId && !canStartChat) ||
    stream.status === "streaming";

  const clearUploads = useCallback(() => {
    uploadRequest.current?.abort();
    uploadRequest.current = null;
    setUploadState(null);
    setUploadIssue(null);
    setUploadNotice("");
    // A new context closes the document picker; its ticks follow the attachments.
    setPicking(false);
  }, []);

  const clearCancellation = useCallback(() => {
    cancelRequest.current?.abort();
    cancelRequest.current = null;
    setCancelState(null);
    setCancelError("");
  }, []);

  useEffect(() => {
    if (stream.status !== "streaming") clearCancellation();
  }, [stream.status, clearCancellation]);

  const selectConversation = useCallback(
    (id: string, continuingRequest?: AbortController) => {
      if (selectedConversation.current !== id) {
        clearUploads();
        clearCancellation();
        // A newly created conversation inherits its own pending request; navigation cancels others.
        if (!continuingRequest || actionRequest.current !== continuingRequest) {
          actionRequest.current?.abort();
          actionRequest.current = null;
          setRunAction(null);
        }
        setRunIssue(null);
        setRunNotice("");
        setEditing(null);
        setConversationAgentId("");
        setSavedRun(null);
      }
      modelRequest.current?.abort();
      modelRequest.current = null;
      selectedConversation.current = id;
      setActiveId(id);
      setModelAction(null);
      setModelNotice("");
      setModelProblem("");
      setConversationLoading(false);
      setConversationProblem(false);
    },
    [clearUploads, clearCancellation],
  );

  function chooseAgent(id: string) {
    if (id ? !availableAgentIds.has(id) : !defaultAgent) return;
    setAgentId(id);
    setAgentProblem(false);
    const params = new URLSearchParams(window.location.search);
    params.delete("agent");
    window.history.replaceState(null, "", `/chat${params.size ? `?${params}` : ""}`);
  }

  async function chooseModel(next: string, refreshOnly = false) {
    if (
      modelRequest.current ||
      actionRequest.current ||
      runIssue ||
      conversationLoading ||
      conversationProblem ||
      loading ||
      stream.status === "streaming"
    )
      return;
    const id = selectedConversation.current;
    if (!id) {
      setModelAlias(next);
      setModelNotice("");
      return;
    }
    const request = new AbortController();
    modelRequest.current = request;
    setModelAction(refreshOnly ? "refreshing" : "saving");
    setModelNotice("");
    try {
      const body = await api<Item>(
        `/api/v1/conversations/${id}`,
        refreshOnly
          ? { signal: request.signal }
          : { method: "PATCH", body: JSON.stringify({ modelAlias: next }), signal: request.signal },
      );
      if (request.signal.aborted || selectedConversation.current !== id) return;
      setModelAlias(typeof body.modelAlias === "string" ? body.modelAlias : "");
      setModelProblem("");
      setModelNotice(t(refreshOnly ? "modelLoaded" : "modelSaved"));
    } catch (error) {
      if (request.signal.aborted || selectedConversation.current !== id) return;
      setModelProblem(error instanceof Error ? error : t("error"));
    } finally {
      if (modelRequest.current === request) {
        modelRequest.current = null;
        setModelAction(null);
      }
    }
  }

  const greeting = useMemo(() => {
    const agent = agents.find((row) => row.slug === "assistant") ?? agents[0];
    return typeof agent?.greeting === "string" && agent.greeting ? agent.greeting : t("greeting");
  }, [agents, t]);

  const reload = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const me = await loadSession();
      void api<{ mimeTypes: string[] }>("/api/v1/files:limits")
        .then((limits) => setAccept((limits.mimeTypes ?? []).join(",")))
        .catch(() => setAccept(""));
      setSession(me);
      const listed = await api<{ items: Item[] }>("/api/v1/conversations");
      const agentPage = await api<{ items: Item[] }>("/api/v1/agents");
      const aliasList = await chatAliases();
      setConversations(listed.items ?? []);
      const catalogue = agentPage.items ?? [];
      setAgents(catalogue);
      setAliases(aliasList);
      const requested = new URLSearchParams(window.location.search).get("agent");
      if (requested) {
        const match = catalogue.find(
          (agent) => agent.slug === requested && isAvailableAgent(agent),
        );
        setAgentId(match?.id ? String(match.id) : "");
        setAgentProblem(!match);
      }
      if (!openedFromQuery.current) {
        const conversationId = new URLSearchParams(window.location.search).get("conversation");
        if (conversationId) {
          setConversationLoading(true);
          openedFromQuery.current = true;
          const request = new AbortController();
          conversationRequest.current?.abort();
          conversationRequest.current = request;
          try {
            const body = await api<Item & { messages?: Item[]; jobs?: Item[] }>(
              `/api/v1/conversations/${conversationId}`,
              { signal: request.signal },
            );
            if (!request.signal.aborted) {
              selectConversation(conversationId);
              setMessages(body.messages ?? []);
              setJobs(body.jobs ?? []);
              setPlan(planFrom(body.plan));
              setConversationAgentId(typeof body.agentId === "string" ? body.agentId : "");
              setModelAlias(typeof body.modelAlias === "string" ? body.modelAlias : "");
              lateRunRef.current = "";
              setStream(emptyStream);
              setSavedRun(
                typeof body.activeRunId === "string" && body.activeRunId
                  ? { conversationId, runId: body.activeRunId }
                  : null,
              );
            }
          } catch (error) {
            if (!request.signal.aborted) {
              setConversationLoading(false);
              throw error;
            }
          }
        }
      }
    } catch (error) {
      setLoadError(error instanceof Error ? error : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t, selectConversation]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    function onNew() {
      clearUploads();
      clearCancellation();
      streamRequest.current?.abort();
      conversationRequest.current?.abort();
      const params = new URLSearchParams(window.location.search);
      params.delete("conversation");
      window.history.replaceState(null, "", `/chat${params.size ? `?${params}` : ""}`);
      runRef.current = "";
      selectConversation("");
      setMessages([]);
      setJobs([]);
      lateRunRef.current = "";
      setStream(emptyStream);
      setBanner("");
      setRunId("");
      setPlan([]);
      setAttachments([]);
    }
    window.addEventListener("ar-new-chat", onNew);
    return () => {
      window.removeEventListener("ar-new-chat", onNew);
      streamRequest.current?.abort();
      conversationRequest.current?.abort();
      modelRequest.current?.abort();
      actionRequest.current?.abort();
      uploadRequest.current?.abort();
      uploadRequest.current = null;
      cancelRequest.current?.abort();
      cancelRequest.current = null;
      lateRunRef.current = "";
    };
  }, [selectConversation, clearUploads, clearCancellation, setBanner]);

  useEffect(() => {
    if (editing?.id) {
      previousEdit.current = editing.id;
      editFieldRef.current?.focus({ preventScroll: true });
    } else if (previousEdit.current) {
      document
        .getElementById(`edit-message-${previousEdit.current}`)
        ?.focus({ preventScroll: true });
      previousEdit.current = "";
    }
  }, [editing?.id]);

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

  const openConversation = useCallback(
    async (id: string, keep?: StreamState) => {
      const changingContext = selectedConversation.current !== id;
      const request = new AbortController();
      conversationRequest.current?.abort();
      conversationRequest.current = request;
      if (!keep) {
        clearCancellation();
        streamRequest.current?.abort();
        runRef.current = "";
        setRunId("");
        setMessages([]);
        setJobs([]);
        setPlan([]);
        lateRunRef.current = "";
        setStream(emptyStream);
        if (changingContext) setAttachments([]);
      }
      selectConversation(id);
      setConversationLoading(true);
      const params = new URLSearchParams(window.location.search);
      params.set("conversation", id);
      window.history.replaceState(null, "", `/chat?${params.toString()}`);
      setBanner("");
      let body: Item & { messages?: Item[]; jobs?: Item[] };
      try {
        body = await api<Item & { messages?: Item[]; jobs?: Item[] }>(
          `/api/v1/conversations/${id}`,
          {
            signal: request.signal,
          },
        );
      } catch (error) {
        if (request.signal.aborted) return;
        setConversationLoading(false);
        setConversationProblem(true);
        throw error;
      }
      if (request.signal.aborted) return;
      setConversationLoading(false);
      setMessages(body.messages ?? []);
      setJobs(body.jobs ?? []);
      setPlan(planFrom(body.plan));
      setConversationAgentId(typeof body.agentId === "string" ? body.agentId : "");
      setModelAlias(typeof body.modelAlias === "string" ? body.modelAlias : "");
      setStream(
        keep
          ? {
              ...emptyStream,
              memories: keep.memories,
              recalled: keep.recalled,
              compacted: keep.compacted,
              toolFailure: keep.toolFailure,
              researchPhase: keep.researchPhase,
              researchQueries: keep.researchQueries,
              sourceCount: keep.sourceCount,
            }
          : emptyStream,
      );
      stickRef.current = true;
      setStuck(false);
      if (!keep)
        setSavedRun(
          typeof body.activeRunId === "string" && body.activeRunId
            ? { conversationId: id, runId: body.activeRunId }
            : null,
        );
      return body;
    },
    [selectConversation, clearCancellation, setBanner],
  );

  async function createConversation(request: AbortController) {
    const created = await api<Item>("/api/v1/conversations", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: conversationBody(agentId, modelAlias),
      signal: request.signal,
    });
    if (request.signal.aborted) return "";
    if (typeof created?.id !== "string" || !created.id) throw new Error(t("creationUnconfirmed"));
    const id = created.id;
    selectConversation(id, request);
    setConversationAgentId(typeof created.agentId === "string" ? created.agentId : "");
    const params = new URLSearchParams(window.location.search);
    params.set("conversation", id);
    window.history.replaceState(null, "", `/chat?${params.toString()}`);
    setHistoryQuery("");
    historyPage.setPage(1);
    setConversations((current) => [created, ...current]);
    return id;
  }

  async function startChat() {
    if (actionRequest.current || loading || loadError || !canStartChat) return;
    clearCancellation();
    const request = new AbortController();
    actionRequest.current = request;
    streamRequest.current?.abort();
    conversationRequest.current?.abort();
    streamRequest.current = request;
    setRunAction("create");
    setRunNotice("");
    setBanner("");
    runRef.current = "";
    setRunId("");
    lateRunRef.current = "";
    setStream(emptyStream);
    // Opening is the pending "New chat". A message sent meanwhile waits for it and goes there.
    const opened = (async () => {
      try {
        const id = await createConversation(request);
        if (!id || request.signal.aborted) return "";
        setAttachments([]);
        const shown = openConversation(id, emptyStream);
        // Opening takes over as the current request. If another conversation is opened
        // before this one is shown, that one is current and this is not where to send.
        const mine = conversationRequest.current;
        await shown;
        return conversationRequest.current === mine && !mine?.signal.aborted ? id : "";
      } catch (error) {
        if (!request.signal.aborted) setBanner(error instanceof Error ? error : t("error"));
        return "";
      } finally {
        if (actionRequest.current === request) {
          actionRequest.current = null;
          setRunAction(null);
        }
      }
    })();
    opening.current = opened;
    await opened;
    if (opening.current === opened) opening.current = null;
  }

  const readStream = useCallback(
    async (id: string, signal: AbortSignal): Promise<StreamState> => {
      let state = emptyStream;
      let attempt = 0;
      while (attempt < 4) {
        if (signal.aborted) return state;
        const response = await fetch(`/api/v1/runs/${id}/events`, {
          credentials: "include",
          signal,
          headers: streamHeaders(state.lastSeq),
        });
        if (!response.ok || !response.body) {
          attempt += 1;
          if (
            !shouldResumeStatus(response.status, attempt) ||
            !shouldResumeStream(state.status, attempt)
          ) {
            throw new Error(t("error"));
          }
          await waitForResume(250 * attempt, signal);
          continue;
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        const parser = createParser({
          onEvent(event) {
            if (signal.aborted) return;
            const payload = JSON.parse(event.data) as {
              type: string;
              seq: number;
              data?: {
                text?: string;
                items?: { id?: string; title?: string; status?: string }[];
                plan?: { id?: string; title?: string; status?: string }[] | string[];
                error?: { message?: string };
              };
            };
            if (payload.type === "plan.updated") {
              const items = payload.data?.items ?? payload.data?.plan;
              const nextPlan = planFrom(items);
              if (nextPlan.length) setPlan(nextPlan);
            }
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
        try {
          while (true) {
            const chunk = await reader.read();
            if (chunk.done) return state;
            parser.feed(decoder.decode(chunk.value, { stream: true }));
          }
        } catch (error) {
          if (signal.aborted) return state;
          attempt += 1;
          if (!shouldResumeStream(state.status, attempt)) throw error;
          await waitForResume(250 * attempt, signal);
        }
      }
      return state;
    },
    [t],
  );

  /** Read a finished run's stream again for the memories saved after its answer. */
  const readLateMemories = useCallback(async (id: string, from: number) => {
    lateRunRef.current = id;
    let seq = from;
    for (const wait of LATE_MEMORY_WAITS_MS) {
      await new Promise((resolve) => setTimeout(resolve, wait));
      if (lateRunRef.current !== id) return;
      const response = await fetch(`/api/v1/runs/${id}/events`, {
        credentials: "include",
        headers: streamHeaders(seq),
      }).catch(() => null);
      if (!response?.ok) continue;
      const found = lateMemoryEvents(await response.text(), seq);
      seq = found.seq;
      if (found.saved.length > 0 && lateRunRef.current === id) {
        setStream((current) => found.saved.reduce(reduceStream, current));
        return;
      }
    }
  }, []);

  async function undoMemory(factId: string) {
    try {
      await api(`/api/v1/memory/${factId}`, { method: "DELETE" });
      setStream((current) => ({
        ...current,
        memories: current.memories.filter((item) => item.factId !== factId),
      }));
    } catch (error) {
      setBanner(error instanceof Error ? error : t("error"));
    }
  }

  async function send(text: string) {
    if (!text.trim()) return;
    // A message typed straight after "New chat" waits until that conversation is open and
    // is sent there, rather than to a conversation of its own that the new one then covers.
    const waited = opening.current;
    const opened = waited ? await waited : "";
    if (
      // After waiting, the values this render saw are stale; the request refs below are not.
      (!waited && (generationBlocked || editing)) ||
      modelRequest.current ||
      actionRequest.current ||
      uploadRequest.current
    )
      return;
    clearCancellation();
    const request = new AbortController();
    actionRequest.current = request;
    streamRequest.current?.abort();
    streamRequest.current = request;
    setRunAction("send");
    setRunIssue(null);
    setRunNotice("");
    setUploadNotice("");
    setBanner("");
    runRef.current = "";
    setRunId("");
    lateRunRef.current = "";
    setStream(emptyStream);
    // A plan whose every step is finished belongs to the turn that ended.
    setPlan((current) =>
      current.every((step) => step.status === "done" || step.status === "cancelled") ? [] : current,
    );
    const submittedDraft = useComposer.getState().draft;
    // The new chat started with no attachments; this render's list belongs to the old one.
    const submittedAttachments = waited ? [] : attachments;
    // The conversation on the screen now, which is the new one when there is one.
    let conversationId = opened || selectedConversation.current;
    let attempted = false;
    let accepted = false;
    let run = "";
    try {
      if (!conversationId) conversationId = await createConversation(request);
      if (!conversationId || !actionIsCurrent(request, conversationId)) return;
      stickRef.current = true;
      attempted = true;
      const posted = await api<{ run?: { id?: string } }>(
        `/api/v1/conversations/${conversationId}/messages`,
        {
          method: "POST",
          signal: request.signal,
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({
            text,
            attachmentIds: submittedAttachments
              .filter((file) => !file.stored)
              .map((file) => file.id),
            fileIds: submittedAttachments.filter((file) => file.stored).map((file) => file.id),
            researchMode: researchOn,
            suggestFollowups: true,
            ...(taskTemplate.trim() ? { taskTemplate: taskTemplate.trim() } : {}),
            ...(checklist.trim()
              ? {
                  items: checklist
                    .split("\n")
                    .map((line) => line.trim())
                    .filter(Boolean),
                }
              : {}),
            ...(collectionIds.trim()
              ? {
                  collectionIds: collectionIds
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean),
                }
              : {}),
          }),
        },
      );
      if (!actionIsCurrent(request, conversationId)) return;
      if (typeof posted?.run?.id !== "string" || !posted.run.id)
        throw new Error(t("runReferenceMissing"));
      accepted = true;
      run = posted.run.id;
      if (
        submittedDraft.trim() === text.trim() &&
        useComposer.getState().draft === submittedDraft
      ) {
        setDraft("");
        if (composerRef.current) composerRef.current.style.height = "auto";
      }
      setAttachments((current) => current.filter((file) => !submittedAttachments.includes(file)));
      setRunAction("generate");
      await openConversation(conversationId, emptyStream);
      if (!actionIsCurrent(request, conversationId)) return;
      await observeActionRun(conversationId, run, request);
      if (!actionIsCurrent(request, conversationId)) return;
      const fresh = await api<{ items: Item[] }>("/api/v1/conversations", {
        signal: request.signal,
      });
      if (actionIsCurrent(request, conversationId)) setConversations(fresh.items ?? []);
    } catch (error) {
      if (request.signal.aborted) return;
      const detail = error instanceof Error ? error : t("error");
      // An error response the server sent is a definite answer: the message was not taken,
      // for example a quota that is used up. Only an answer that never came is unconfirmed.
      const refused = !accepted && error instanceof ApiError && error.status < 500;
      if (attempted && !refused && actionIsCurrent(request, conversationId)) {
        setRunIssue({ detail, accepted, runId: run || undefined, action: "send" });
        setStream((current) => ({ ...current, status: "failed" }));
      } else {
        setBanner(detail, t("messageNotSent"));
      }
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setRunAction(null);
        runRef.current = "";
      }
    }
  }

  async function stop() {
    const id = runRef.current;
    const streamController = streamRequest.current;
    const context = selectedConversation.current;
    if (
      !id ||
      !context ||
      !streamController ||
      streamController.signal.aborted ||
      cancelRequest.current ||
      cancelState
    )
      return;
    const request = new AbortController();
    cancelRequest.current = request;
    setCancelState("requesting");
    setCancelError("");
    const current = () =>
      !request.signal.aborted &&
      cancelRequest.current === request &&
      selectedConversation.current === context &&
      streamRequest.current === streamController &&
      runRef.current === id;
    let accepted = false;
    try {
      const result = await api<{ id?: string }>(`/api/v1/runs/${id}:cancel`, {
        method: "POST",
        body: "{}",
        signal: request.signal,
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      if (!current()) return;
      if (result?.id !== id) throw new Error(t("runReferenceMissing"));
      accepted = true;
      setCancelState("requested");
    } catch (error) {
      if (!current()) return;
      // A run may end between showing Stop and the server receiving it.
      try {
        const run = await api<{ status: string }>(`/api/v1/runs/${id}`, { signal: request.signal });
        if (!current()) return;
        if (isTerminalRunStatus(run.status)) {
          streamController.abort();
          setStream((state) => ({ ...state, status: "idle" }));
          setRunIssue({ detail: "", accepted: true, runId: id, status: run.status });
          return;
        }
      } catch {
        // Preserve the original cancellation error when its status cannot be read.
      }
      if (current()) setCancelError(error instanceof Error ? error : t("error"));
    } finally {
      if (cancelRequest.current === request && !accepted) {
        cancelRequest.current = null;
        setCancelState(null);
      }
    }
  }

  const actionIsCurrent = useCallback((request: AbortController, conversationId: string) => {
    return !request.signal.aborted && selectedConversation.current === conversationId;
  }, []);

  const presentRunState = useCallback(
    (run: string, status: string, cancelRequested = false) => {
      if (["queued", "running", "waiting_approval", "waiting_input"].includes(status)) {
        setRunIssue({ detail: "", accepted: true, runId: run, status, cancelRequested });
      } else if (isTerminalRunStatus(status)) {
        setRunIssue(null);
        setRunNotice(
          t(
            status === "completed"
              ? "actionUpdated"
              : status === "cancelled"
                ? "actionCancelled"
                : status === "interrupted"
                  ? "actionInterrupted"
                  : "actionFailed",
          ),
        );
      } else {
        throw new Error(t("actionStateUnavailable"));
      }
    },
    [t],
  );

  const observeActionRun = useCallback(
    async (id: string, run: string, request: AbortController) => {
      runRef.current = run;
      setRunId(run);
      setStream({ ...emptyStream, status: "streaming" });
      const streamed = await readStream(run, request.signal);
      if (!actionIsCurrent(request, id)) return;
      const current = await api<{ status: string; cancelRequested?: boolean }>(
        `/api/v1/runs/${run}`,
        {
          signal: request.signal,
        },
      );
      if (!actionIsCurrent(request, id)) return;
      await openConversation(id, streamed);
      if (!actionIsCurrent(request, id)) return;
      presentRunState(run, current.status, current.cancelRequested === true);
      if (streamed.status === "completed") void readLateMemories(run, streamed.lastSeq);
    },
    [actionIsCurrent, openConversation, presentRunState, readLateMemories, readStream],
  );

  useEffect(() => {
    if (!savedRun || runAction || actionRequest.current) return;
    const { conversationId: id, runId: run } = savedRun;
    if (selectedConversation.current !== id) return;
    const request = new AbortController();
    actionRequest.current = request;
    streamRequest.current?.abort();
    streamRequest.current = request;
    setSavedRun(null);
    setRunAction("refresh");
    setRunIssue(null);
    setRunNotice("");
    setRunId(run);
    void (async () => {
      try {
        const current = await api<{ status: string; cancelRequested?: boolean }>(
          `/api/v1/runs/${run}`,
          {
            signal: request.signal,
          },
        );
        if (!actionIsCurrent(request, id)) return;
        if (["queued", "running"].includes(current.status)) {
          if (current.cancelRequested === true) setCancelState("requested");
          await observeActionRun(id, run, request);
        } else {
          await openConversation(id, emptyStream);
          if (actionIsCurrent(request, id))
            presentRunState(run, current.status, current.cancelRequested === true);
        }
      } catch (error) {
        if (!actionIsCurrent(request, id)) return;
        setRunIssue({
          detail: error instanceof Error ? error : t("error"),
          accepted: true,
          runId: run,
        });
        setStream((current) => ({ ...current, status: "failed" }));
      } finally {
        if (actionRequest.current === request) {
          actionRequest.current = null;
          setRunAction(null);
          runRef.current = "";
        }
      }
    })();
    // Context changes and unmount use the shared request cancellation above.
  }, [
    savedRun,
    runAction,
    actionIsCurrent,
    observeActionRun,
    openConversation,
    presentRunState,
    t,
  ]);

  async function runMessageAction(
    kind: "regenerate" | "edit" | "resume",
    target: string,
    text = "",
  ) {
    if (
      !activeId ||
      generationBlocked ||
      modelRequest.current ||
      actionRequest.current ||
      uploadRequest.current
    )
      return;
    if (kind !== "edit" && editing) return;
    const id = activeId;
    clearCancellation();
    const request = new AbortController();
    actionRequest.current = request;
    streamRequest.current?.abort();
    streamRequest.current = request;
    setRunAction(kind);
    setRunIssue(null);
    setRunNotice("");
    setBanner("");
    runRef.current = "";
    setRunId("");
    let accepted = false;
    let run = kind === "resume" ? target : "";
    try {
      const result = await api<{ id?: string; run?: { id: string } }>(
        kind === "resume"
          ? `/api/v1/runs/${target}:resume`
          : `/api/v1/conversations/${id}/messages/${target}:${kind}`,
        {
          method: "POST",
          signal: request.signal,
          body: JSON.stringify(kind === "edit" ? { text } : {}),
        },
      );
      if (!actionIsCurrent(request, id)) return;
      const returnedId = kind === "resume" ? result.id : result.run?.id;
      if (typeof returnedId !== "string" || !returnedId) throw new Error(t("runReferenceMissing"));
      run = returnedId;
      accepted = true;
      if (kind === "edit") setEditing(null);
      // Load the saved branch before attaching streamed text to its assistant message.
      await openConversation(id, emptyStream);
      if (!actionIsCurrent(request, id)) return;
      await observeActionRun(id, run, request);
    } catch (error) {
      if (!actionIsCurrent(request, id)) return;
      setRunIssue({
        detail: error instanceof Error ? error : t("error"),
        accepted,
        runId: run || undefined,
      });
      setStream((current) => ({ ...current, status: "failed" }));
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setRunAction(null);
        runRef.current = "";
      }
    }
  }

  async function refreshRunAction(focusFrom?: HTMLElement) {
    if (!activeId || actionRequest.current || !runIssue) return;
    const restoreFocus = Boolean(focusFrom && document.activeElement === focusFrom);
    const id = activeId;
    const previousIssue = runIssue;
    const request = new AbortController();
    actionRequest.current = request;
    streamRequest.current?.abort();
    streamRequest.current = request;
    setRunAction("refresh");
    setRunNotice("");
    try {
      const body = await openConversation(id, emptyStream);
      if (!body || !actionIsCurrent(request, id)) return;
      if (
        editing &&
        body.messages?.some(
          (message) => message.id === editing.id && message.isActiveBranch === false,
        )
      )
        setEditing(null);
      const last = body.messages?.findLast(
        (message) => message.role === "assistant" && message.isActiveBranch !== false,
      );
      const candidate =
        typeof body.activeRunId === "string"
          ? body.activeRunId
          : previousIssue.runId || (typeof last?.runId === "string" ? last.runId : "");
      if (candidate) {
        const current = await api<{ status: string; cancelRequested?: boolean }>(
          `/api/v1/runs/${candidate}`,
          {
            signal: request.signal,
          },
        );
        if (!actionIsCurrent(request, id)) return;
        if (["queued", "running"].includes(current.status)) {
          if (current.cancelRequested === true) setCancelState("requested");
          await observeActionRun(id, candidate, request);
          return;
        }
        await openConversation(id, emptyStream);
        if (!actionIsCurrent(request, id)) return;
        if (["waiting_approval", "waiting_input"].includes(current.status)) {
          presentRunState(candidate, current.status, current.cancelRequested === true);
          return;
        }
        if (!isTerminalRunStatus(current.status)) throw new Error(t("actionStateUnavailable"));
      }
      setRunIssue(null);
      setRunNotice(t("actionUpdated"));
      if (
        restoreFocus &&
        (document.activeElement === focusFrom || document.activeElement === document.body)
      )
        composerRef.current?.focus({ preventScroll: true });
    } catch (error) {
      if (!actionIsCurrent(request, id)) return;
      setRunIssue({
        ...previousIssue,
        status: undefined,
        detail: error instanceof Error ? error : t("error"),
      });
      setStream((current) => ({ ...current, status: "failed" }));
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setRunAction(null);
        runRef.current = "";
      }
    }
  }

  async function regenerate(messageId: string) {
    await runMessageAction("regenerate", messageId);
  }

  async function editMessage(messageId: string, text: string) {
    if (text.trim()) await runMessageAction("edit", messageId, text);
  }

  async function resume(id: string) {
    await runMessageAction("resume", id);
  }

  function toggleDocument(document: Attached) {
    setAttachments((current) =>
      current.some((item) => item.id === document.id)
        ? current.filter((item) => item.id !== document.id)
        : [...current, document],
    );
  }

  function closePicker() {
    setPicking(false);
    composerRef.current?.focus();
  }

  function stopUpload() {
    if (!uploadRequest.current) return;
    clearUploads();
    setUploadNotice(t("uploadStopped"));
    composerRef.current?.focus({ preventScroll: true });
  }

  async function onUpload(files: FileList) {
    if (attachmentBlocked || uploadRequest.current) return;
    const selection = Array.from(files);
    if (!selection.length) return;
    const context = selectedConversation.current;
    const request = new AbortController();
    uploadRequest.current = request;
    setUploadIssue(null);
    setUploadNotice("");
    let index = 0;
    try {
      for (const file of selection) {
        setUploadState({ name: file.name, index: index + 1, total: selection.length });
        const body = new FormData();
        body.set("upload", file);
        body.set("mime_type", file.type);
        const saved = await api<{
          id?: string;
          name?: string;
          mimeType?: string;
          sizeBytes?: number;
          status?: string;
        }>("/api/v1/files:upload", { method: "POST", body, signal: request.signal });
        if (request.signal.aborted || selectedConversation.current !== context) return;
        if (
          !saved ||
          typeof saved.id !== "string" ||
          !saved.id ||
          typeof saved.name !== "string" ||
          !saved.name ||
          typeof saved.mimeType !== "string"
        )
          throw new Error(t("uploadUnconfirmed"));
        if (saved.status !== "ready") throw new Error(t("uploadNotReady"));
        const attached: Attached = {
          id: saved.id,
          name: saved.name,
          mimeType: saved.mimeType,
          sizeBytes: saved.sizeBytes,
        };
        setAttachments((current) => [
          ...current.filter((item) => item.id !== attached.id),
          attached,
        ]);
        index += 1;
      }
      setUploadNotice(t("uploadComplete"));
    } catch (caught) {
      if (request.signal.aborted || selectedConversation.current !== context) return;
      setUploadIssue({
        name: selection[index]?.name ?? "",
        detail: caught instanceof Error ? caught : t("error"),
        remaining: selection.length - index,
      });
    } finally {
      if (uploadRequest.current === request) {
        uploadRequest.current = null;
        setUploadState(null);
      }
    }
  }

  async function copyMessage(id: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      window.setTimeout(() => setCopiedId(""), 1200);
    } catch (error) {
      setBanner(error instanceof Error ? error : t("error"));
    }
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

  useEffect(() => {
    try {
      setDetailsOpen(window.localStorage.getItem(DETAILS_KEY) === "open");
    } catch {
      // Storage can be blocked. The panel then starts closed.
    }
  }, []);

  function toggleDetails() {
    setDetailsOpen((open) => {
      try {
        window.localStorage.setItem(DETAILS_KEY, open ? "closed" : "open");
      } catch {
        // The choice then lasts for this visit only.
      }
      return !open;
    });
  }

  const visible = messages.filter((message) => message.isActiveBranch !== false);
  const matchingConversations = useMemo(
    () =>
      conversations.filter((conversation) =>
        String(conversation.title || t("untitled"))
          .toLocaleLowerCase()
          .includes(historyQuery.trim().toLocaleLowerCase()),
      ),
    [conversations, historyQuery, t],
  );
  const historyPage = usePagedRows(matchingConversations, historyQuery);
  const activeTitle = String(
    conversations.find((conversation) => String(conversation.id) === activeId)?.title ||
      t("untitled"),
  );
  const latestAssistantId = [...visible]
    .reverse()
    .find((message) => message.role === "assistant")?.id;
  const lastRun = [...messages]
    .reverse()
    .map((message) => (message as { runId?: string }).runId)
    .find(Boolean);
  const detailRunId = runId || lastRun || "";
  const virtualizer = useVirtualizer({
    count: visible.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 120,
  });

  return (
    <AppShell flush>
      <div className="flex h-full min-h-0 min-w-0 flex-col md:flex-row">
        <aside
          aria-label={t("conversations")}
          className={cn(
            "shrink-0 min-h-0 min-w-0 flex-col overflow-hidden border-b border-[var(--border)] bg-[var(--card)] md:flex md:w-52 md:border-b-0 md:border-r xl:w-60",
            historyOpen ? "flex max-h-[60dvh] md:max-h-none" : "hidden",
          )}
        >
          <div className="px-4 pt-5">
            <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--muted-foreground)]">
              {t("recent")}
            </p>
            <Button
              disabled={Boolean(runAction) || loading || Boolean(loadError) || !canStartChat}
              className="h-9 w-full justify-start gap-2 border border-dashed border-[var(--border)] px-2 text-[13px] font-normal"
              onClick={() => {
                void startChat();
                setHistoryOpen(false);
              }}
              type="button"
              variant="ghost"
            >
              <Plus size={14} aria-hidden="true" />
              {t("newChat")}
            </Button>
          </div>
          {conversations.length > 5 || historyQuery ? (
            <label className="relative mx-3 mt-4 block">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-2.5 text-[var(--muted-foreground)]"
                size={15}
              />
              <span className="sr-only">{t("searchHistory")}</span>
              <input
                className="h-9 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] pl-9 pr-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                onChange={(event) => setHistoryQuery(event.target.value)}
                placeholder={t("searchHistory")}
                type="search"
                value={historyQuery}
              />
            </label>
          ) : null}
          <nav
            aria-label={t("conversations")}
            className="mt-4 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-3 pb-3"
          >
            {conversations.length === 0 && !loading ? (
              <p className="text-sm text-[var(--muted-foreground)]">{t("noConversations")}</p>
            ) : null}
            {matchingConversations.length === 0 && conversations.length > 0 ? (
              <p className="px-2 text-sm text-[var(--muted-foreground)]">{t("noHistoryMatches")}</p>
            ) : null}
            {historyPage.rows.map((conversation) => {
              const id = String(conversation.id);
              const selected = id === activeId;
              return (
                <button
                  aria-current={selected ? "true" : undefined}
                  className={cn(
                    "flex min-h-10 shrink-0 items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px]",
                    selected
                      ? "bg-[var(--muted)] font-medium"
                      : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]",
                  )}
                  key={id}
                  onClick={() => {
                    setRunId("");
                    void openConversation(id).catch((error: unknown) =>
                      setBanner(error instanceof Error ? error : t("error")),
                    );
                    setHistoryOpen(false);
                  }}
                  type="button"
                >
                  <MessageSquare size={14} className="shrink-0" aria-hidden="true" />
                  <span className="truncate">{String(conversation.title || t("untitled"))}</span>
                </button>
              );
            })}
          </nav>
          {historyPage.pages > 1 ? (
            <div className="shrink-0 border-t border-[var(--border)] px-2 py-3">
              <ListPagination {...historyPage} compact label={t("conversations")} />
            </div>
          ) : null}
        </aside>
        <section className="flex min-h-0 min-w-0 flex-1 flex-col md:flex-row">
          <div className="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-4 py-2 md:hidden">
            <span className="text-xs font-medium">{t("title")}</span>
            <button
              className="flex items-center gap-2 rounded-lg p-2 text-xs text-[var(--muted-foreground)]"
              aria-expanded={historyOpen}
              onClick={() => setHistoryOpen((open) => !open)}
              type="button"
            >
              <History size={14} aria-hidden="true" />
              {historyOpen ? t("hideHistory") : t("historyToggle")}
            </button>
          </div>
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            <h1 className="sr-only">{t("title")}</h1>
            <p className="sr-only">{session?.tenant?.name ?? t("tenant")}</p>
            <div className="sr-only" aria-atomic="false" aria-live="polite">
              {live ? `${t("streaming")}. ${live}` : ""}
            </div>
            {activeId && visible.length > 0 ? (
              <div className="hidden h-12 shrink-0 items-center justify-between gap-3 border-b border-[var(--border)] px-5 md:flex">
                <p className="truncate text-sm font-medium">{activeTitle}</p>
                <Button
                  aria-controls="chat-details"
                  aria-expanded={detailsOpen}
                  className="h-8 shrink-0 gap-1.5 px-2.5 text-xs font-normal"
                  onClick={toggleDetails}
                  type="button"
                  variant={detailsOpen ? "outline" : "ghost"}
                >
                  <PanelRight size={15} aria-hidden="true" />
                  {t("details")}
                </Button>
              </div>
            ) : null}
            {loading && !loadError ? (
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
                <div>
                  <ErrorMessage error={loadError} />
                </div>
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
              <section
                aria-labelledby="chat-welcome-title"
                // biome-ignore lint/a11y/noNoninteractiveTabindex: a scrollable region needs keyboard focus
                tabIndex={0}
                className="mx-auto flex min-h-0 w-full max-w-3xl flex-1 flex-col overflow-y-auto px-5 py-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--ring)] md:px-10"
              >
                <div className="my-auto">
                  <div className="mb-5 flex size-12 shrink-0 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-xs)]">
                    <Sparkles size={24} strokeWidth={1.4} aria-hidden="true" />
                  </div>
                  <p className="mb-3 text-[10px] font-medium uppercase tracking-[0.16em] text-[var(--muted-foreground)]">
                    {t("eyebrow")}
                  </p>
                  <h2
                    id="chat-welcome-title"
                    className="font-display text-[clamp(1.8rem,3.2vw,2.75rem)] leading-[1.15] tracking-tight"
                  >
                    {t("welcomeTitle")}
                  </h2>
                  <p className="mt-4 max-w-md text-[15px] leading-relaxed text-[var(--muted-foreground)]">
                    {t("empty")}
                  </p>
                  <p className="sr-only">{greeting}</p>
                  {!runAction && !runIssue && !uploading && !uploadIssue ? (
                    <div className="mt-7 grid grid-cols-1 gap-2 sm:grid-cols-3">
                      {[
                        { prompt: t("starter1"), label: t("starterLabel1"), icon: PenLine },
                        { prompt: t("starter2"), label: t("starterLabel2"), icon: Lightbulb },
                        { prompt: t("starter3"), label: t("starterLabel3"), icon: FileText },
                      ].map(({ prompt, label, icon: Icon }) => (
                        <button
                          className="group flex items-center gap-3 rounded-xl disabled:opacity-50 border border-[var(--border)] bg-[var(--card)] p-3 text-left shadow-[var(--shadow-xs)] hover:border-[var(--muted-foreground)] sm:block sm:p-4"
                          key={prompt}
                          disabled={generationBlocked || Boolean(editing)}
                          onClick={() => void send(prompt)}
                          type="button"
                        >
                          <Icon
                            size={18}
                            strokeWidth={1.5}
                            className="shrink-0 text-[var(--muted-foreground)]"
                            aria-hidden="true"
                          />
                          <span className="block sm:mt-4">
                            <span className="block text-xs font-semibold">{label}</span>
                            <span className="mt-1 block text-xs leading-relaxed text-[var(--muted-foreground)]">
                              {prompt}
                            </span>
                          </span>
                          <ArrowUpRight
                            size={14}
                            className="ml-auto shrink-0 text-[var(--muted-foreground)] sm:hidden"
                            aria-hidden="true"
                          />
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              </section>
            ) : null}
            <div
              className={cn(
                // `relative` keeps absolutely placed children, such as screen-reader labels,
                // inside this scroll area. Without it they stretch the whole page.
                "relative min-h-0 overflow-auto px-5 md:px-10",
                visible.length ? "flex-1 py-5" : "h-0",
              )}
              data-testid="message-scroll"
              onScroll={onScroll}
              ref={parentRef}
            >
              {jobs.length > 0 ? (
                <div className="mx-auto max-w-3xl px-5 pt-4">
                  <JobList jobs={jobs} />
                </div>
              ) : null}
              <div
                className={visible.length < 30 ? "mx-auto max-w-3xl" : "relative mx-auto max-w-3xl"}
                style={visible.length < 30 ? undefined : { height: virtualizer.getTotalSize() }}
              >
                {(visible.length < 30
                  ? visible.map((message, index) => ({ index, start: 0, message }))
                  : virtualizer.getVirtualItems().map((row) => ({
                      index: row.index,
                      start: row.start,
                      message: visible[row.index],
                    }))
                ).map((row) => {
                  const message = row.message;
                  if (!message) {
                    return null;
                  }
                  const streamingHere =
                    row.index === visible.length - 1 &&
                    message.role === "assistant" &&
                    stream.status === "streaming";
                  const body = streamingHere ? stream.text || textOf(message) : textOf(message);
                  const failedHere =
                    message.role === "assistant" && message.status === "failed" && !streamingHere;
                  const reason = failedHere
                    ? String((message.error as { message?: string } | undefined)?.message ?? "")
                    : "";
                  const id = String(message.id ?? row.index);
                  const mine = message.role === "user";
                  return (
                    <article
                      className={
                        visible.length < 30 ? "w-full py-3" : "absolute left-0 top-0 w-full py-3"
                      }
                      data-index={row.index}
                      data-testid={`message-${id}`}
                      key={id}
                      ref={visible.length < 30 ? undefined : virtualizer.measureElement}
                      style={
                        visible.length < 30
                          ? undefined
                          : { transform: `translateY(${row.start}px)` }
                      }
                    >
                      <div className={mine ? "flex justify-end" : "flex gap-3"}>
                        {mine ? null : (
                          <div
                            aria-hidden="true"
                            className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-xs)]"
                          >
                            <Sparkles size={14} strokeWidth={1.6} />
                          </div>
                        )}
                        <div
                          className={
                            mine
                              ? `${editing?.id === id ? "w-full max-w-full sm:max-w-[85%]" : "max-w-[80%]"} rounded-2xl rounded-br-md bg-[var(--muted)] px-4 py-2.5`
                              : "min-w-0 flex-1"
                          }
                        >
                          <p className="sr-only">{String(message.role)}</p>
                          {mine ? null : (
                            <p aria-hidden="true" className="mb-1.5 text-xs font-semibold">
                              {replyName(
                                message,
                                agentIndex,
                                t("defaultAgent"),
                                conversationAgentId || agentId,
                              )}
                            </p>
                          )}
                          {editing?.id === id ? (
                            <form
                              aria-label={t("editMessage")}
                              className="space-y-2"
                              onSubmit={(event) => {
                                event.preventDefault();
                                void editMessage(id, editing.text);
                              }}
                            >
                              <textarea
                                aria-label={t("editMessage")}
                                ref={editFieldRef}
                                rows={4}
                                disabled={Boolean(runAction)}
                                className="min-h-24 max-h-64 w-full resize-y rounded-lg border border-[var(--border)] bg-[var(--card)] p-2"
                                onChange={(event) => setEditing({ id, text: event.target.value })}
                                value={editing.text}
                              />
                              <div className="flex flex-wrap gap-2">
                                <Button disabled={generationBlocked} type="submit">
                                  {t("saveEdit")}
                                </Button>
                                <Button
                                  disabled={Boolean(runAction)}
                                  type="button"
                                  variant="outline"
                                  onClick={() => setEditing(null)}
                                >
                                  {t("cancelEdit")}
                                </Button>
                              </div>
                            </form>
                          ) : failedHere ? (
                            <FailedReply
                              busy={generationBlocked || Boolean(editing)}
                              onRetry={() => void regenerate(id)}
                              reason={reason}
                              said={body === reason ? "" : body}
                            />
                          ) : mine ? (
                            <MarkdownView text={body} />
                          ) : (
                            <MessageBody
                              message={message}
                              onFollowup={(prompt) => setDraft(prompt)}
                              prompts={streamingHere ? stream.followups : undefined}
                              reasoning={streamingHere ? stream.reasoning : undefined}
                              reasoningMs={streamingHere ? stream.reasoningMs : undefined}
                              text={body}
                            />
                          )}
                          {mine && editing?.id !== id ? (
                            <button
                              className="mt-1 text-xs underline"
                              id={`edit-message-${id}`}
                              disabled={generationBlocked}
                              onClick={() => setEditing({ id, text: body })}
                              type="button"
                            >
                              {t("edit")}
                            </button>
                          ) : null}
                          {failedHere ? (
                            <button
                              className="mt-2 text-xs underline"
                              disabled={generationBlocked || Boolean(editing)}
                              onClick={() => {
                                const target = String(
                                  (message as { runId?: string; run_id?: string }).runId ??
                                    (message as { run_id?: string }).run_id ??
                                    runId,
                                );
                                if (target) void resume(target);
                              }}
                              type="button"
                            >
                              {t("resume")}
                            </button>
                          ) : null}
                          {!streamingHere ? <AttachmentList files={attachedOf(message)} /> : null}
                          {(() => {
                            // One list for a reply's tool calls, while it is written and
                            // after. The same rows stay on the page when the reply
                            // finishes, so a call a person opened stays open.
                            const live = streamingHere && stream.tools.length > 0;
                            const calls: Record<string, unknown>[] = live
                              ? stream.tools.map((tool) => ({
                                  qualifiedName: tool.name,
                                  status: tool.status,
                                  resultPreview: tool.preview,
                                  arguments: tool.arguments,
                                  presentation: tool.presentation,
                                  timeline: tool.timeline,
                                }))
                              : Array.isArray(message.toolCalls)
                                ? message.toolCalls.map((call) =>
                                    call && typeof call === "object"
                                      ? (call as Record<string, unknown>)
                                      : {},
                                  )
                                : [];
                            if (calls.length === 0) return null;
                            return (
                              <div>
                                {live ? (
                                  <p className="text-xs font-medium text-[var(--muted-foreground)]">
                                    {t("working")}
                                  </p>
                                ) : null}
                                {calls.map((row, position) => (
                                  <ToolCallCard
                                    call={row}
                                    // Calls are only ever added at the end, and two calls of
                                    // one tool can return the same text, so the position names one.
                                    // biome-ignore lint/suspicious/noArrayIndexKey: see above
                                    key={`${id}-call-${position}`}
                                    label={t("toolCall")}
                                  />
                                ))}
                              </div>
                            );
                          })()}
                          {message.loadedSkill && typeof message.loadedSkill === "object" ? (
                            <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                              {t("loadedSkill", {
                                name: String(
                                  (message.loadedSkill as { name?: string }).name || "skill",
                                ),
                                reason: String(
                                  (message.loadedSkill as { reason?: string }).reason || "",
                                ),
                              })}
                            </p>
                          ) : null}
                          {message.retrieval &&
                          typeof message.retrieval === "object" &&
                          Array.isArray((message.retrieval as { hits?: unknown[] }).hits) ? (
                            <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                              {t("retrievalTrace", {
                                count: (message.retrieval as { hits: unknown[] }).hits.length,
                                chars: Number(
                                  (message.retrieval as { usedChars?: number }).usedChars || 0,
                                ),
                              })}
                            </p>
                          ) : null}
                          <ReadingNote reading={readingOf(message)} />
                          <ReviewTable rows={reviewsOf(message)} />

                          {streamingHere && !body && stream.tools.length === 0 ? (
                            <p
                              className="text-sm text-[var(--muted-foreground)]"
                              data-testid="reply-working"
                            >
                              {t("workingOnIt")}
                            </p>
                          ) : null}
                          {streamingHere ? <span aria-hidden="true" className="caret" /> : null}
                          {!mine && id === latestAssistantId ? (
                            <PlanChecklist items={stream.plan.length ? stream.plan : plan} />
                          ) : null}
                          {streamingHere &&
                          stream.warnings.some((item) => item.code === "embedding_unconfigured") ? (
                            <p className="mt-1 text-xs text-[var(--destructive)]" role="alert">
                              {
                                stream.warnings.find(
                                  (item) => item.code === "embedding_unconfigured",
                                )?.message
                              }
                            </p>
                          ) : null}
                          {streamingHere &&
                          stream.warnings.some((item) => item.code === "model_fallback_used") ? (
                            <p
                              className="mt-1 text-xs text-[var(--muted-foreground)]"
                              role="status"
                            >
                              {t("fallbackUsed")}
                            </p>
                          ) : null}
                        </div>
                      </div>
                      <div
                        className={`mt-1 flex flex-wrap items-center gap-1 ${mine ? "justify-end" : "pl-8"}`}
                      >
                        <Button
                          aria-label={copiedId === id ? t("copied") : t("copy")}
                          title={copiedId === id ? t("copied") : t("copy")}
                          className="size-8 p-0 text-[var(--muted-foreground)]"
                          onClick={() => void copyMessage(id, body)}
                          type="button"
                          variant="ghost"
                        >
                          {copiedId === id ? (
                            <Check size={13} aria-hidden="true" />
                          ) : (
                            <Copy size={13} aria-hidden="true" />
                          )}
                        </Button>
                        {message.role === "assistant" && !failedHere && id ? (
                          <Button
                            aria-label={t("regenerate")}
                            title={t("regenerate")}
                            className="size-8 p-0 text-[var(--muted-foreground)]"
                            disabled={generationBlocked || Boolean(editing)}
                            onClick={() => void regenerate(id)}
                            type="button"
                            variant="ghost"
                          >
                            <RefreshCw size={13} aria-hidden="true" />
                          </Button>
                        ) : null}
                        {message.role === "assistant" && !failedHere && !streamingHere ? (
                          <AcceptReply
                            disabled={
                              stream.status === "streaming" ||
                              Boolean(runAction) ||
                              conversationLoading
                            }
                            messageId={id}
                            onRefresh={async () => {
                              if (
                                !activeId ||
                                actionRequest.current ||
                                selectedConversation.current !== activeId
                              )
                                return;
                              try {
                                await openConversation(activeId);
                              } catch (caught) {
                                if (selectedConversation.current === activeId)
                                  setBanner(caught instanceof Error ? caught : t("acceptError"));
                                throw caught;
                              }
                            }}
                            onAccepted={(review) =>
                              setMessages((current) =>
                                current.map((item) =>
                                  item.id === message.id ? { ...item, review } : item,
                                ),
                              )
                            }
                            review={message.review as ReplyReview | undefined}
                          />
                        ) : null}
                        {message.role === "assistant" &&
                        traceOf(message, id === latestAssistantId ? runId : "") ? (
                          <a
                            aria-label={t("viewTrace")}
                            title={t("viewTrace")}
                            className="flex size-8 items-center justify-center rounded-md text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
                            href={`/runs/${traceOf(message, id === latestAssistantId ? runId : "")}`}
                          >
                            <ArrowUpRight size={15} aria-hidden="true" />
                          </a>
                        ) : null}
                        {message.role === "assistant" && !failedHere ? (
                          <FeedbackButtons
                            initial={String(
                              (message.feedback as { rating?: string } | undefined)?.rating ?? "",
                            )}
                            messageId={id}
                          />
                        ) : null}
                        <CitationList
                          citations={
                            streamingHere && stream.citations.length
                              ? stream.citations
                              : citationsOf(message)
                          }
                          conversationId={activeId}
                          messageId={message.role === "assistant" && !streamingHere ? id : ""}
                        />
                        {!mine ? (
                          <span className="ml-auto flex items-center gap-2 pl-2 text-[11px] text-[var(--muted-foreground)]">
                            {(streamingHere ? stream.answeredModel : message.answeredModel) ? (
                              <span data-testid="answered-by">
                                {t("answeredBy", {
                                  model: String(
                                    streamingHere ? stream.answeredModel : message.answeredModel,
                                  ),
                                })}
                              </span>
                            ) : null}
                            {!failedHere ? (
                              <ReplyReviewStatus
                                review={
                                  streamingHere ? null : (message.review as ReplyReview | undefined)
                                }
                              />
                            ) : null}
                          </span>
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
              <div className="px-6 text-sm" role="alert">
                <div>
                  {banner.prefix ? <p>{banner.prefix}</p> : null}
                  <ErrorMessage error={banner.error} />
                </div>
                {conversationProblem ? (
                  <Button
                    className="mt-2"
                    type="button"
                    variant="outline"
                    onClick={() =>
                      void openConversation(activeId).catch((error: unknown) =>
                        setBanner(error instanceof Error ? error : t("error")),
                      )
                    }
                  >
                    {t("retry")}
                  </Button>
                ) : null}
              </div>
            ) : null}
            <div className="mx-auto w-full max-w-3xl px-4 md:px-8">
              <MemoryIndicator
                compacted={stream.compacted}
                memories={stream.memories}
                onUndo={(factId) => void undoMemory(factId)}
                recalled={stream.recalled}
              />
            </div>
            <form
              aria-label={t("composeMessage")}
              className="shrink-0 px-4 pb-4 md:px-8 md:pb-6"
              onDragOver={(event) => {
                event.preventDefault();
              }}
              onDrop={(event) => {
                event.preventDefault();
                if (event.dataTransfer.files?.length) void onUpload(event.dataTransfer.files);
              }}
              onSubmit={(event) => {
                event.preventDefault();
                const text = draft.trim();
                if (!text) return;
                // While "New chat" is opening, send waits for it and checks again.
                if (
                  !opening.current &&
                  (generationBlocked ||
                    editing ||
                    modelRequest.current ||
                    actionRequest.current ||
                    uploadRequest.current)
                ) {
                  return;
                }
                void send(text);
              }}
            >
              {stream.toolFailure ? (
                <p
                  className="mx-auto mb-3 max-w-3xl text-sm text-[var(--muted-foreground)]"
                  role="status"
                >
                  {stream.toolFailure}
                </p>
              ) : null}
              {stream.researchQueries.length > 0 || stream.sourceCount > 0 ? (
                <section className="mx-auto mb-3 max-w-3xl rounded-xl border border-[var(--border)] px-3 py-2 text-sm">
                  <h2 className="font-medium">{t("researchPhase")}</h2>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {t(stream.researchPhase === "done" ? "researchDone" : "researchRunning")} ·{" "}
                    {t("sourcesFound", { count: stream.sourceCount })}
                    {stream.verified ? ` · ${t("verified")} ${stream.verified}` : ""}
                  </p>
                  <p className="mt-2 text-xs font-medium text-[var(--muted-foreground)]">
                    {t("researchQuestions")}
                  </p>
                  <ol className="mt-1 list-decimal pl-5">
                    {stream.researchQueries.map((query) => (
                      <li key={query.id}>{query.text}</li>
                    ))}
                  </ol>
                </section>
              ) : null}
              {picking ? (
                <DocumentPicker
                  chosen={attachments.map((item) => item.id)}
                  onClose={closePicker}
                  onToggle={toggleDocument}
                />
              ) : null}
              <div className="mx-auto flex max-w-3xl flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] p-3 shadow-[var(--shadow-composer)] focus-within:border-[var(--muted-foreground)] md:p-4">
                {uploadState ? (
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <p role="status" className="min-w-0 text-xs text-[var(--muted-foreground)]">
                      {t("uploadProgress", { index: uploadState.index, total: uploadState.total })}
                      <span className="block truncate" title={uploadState.name}>
                        {uploadState.name}
                      </span>
                    </p>
                    <Button
                      type="button"
                      variant="outline"
                      className="shrink-0"
                      onClick={stopUpload}
                    >
                      {t("stopUpload")}
                    </Button>
                  </div>
                ) : null}
                {uploadIssue ? (
                  <div
                    role="alert"
                    className="mb-3 rounded-lg border border-[var(--border)] p-3 text-sm"
                  >
                    <p className="font-medium">{t("uploadError")}</p>
                    <p className="mt-1 truncate text-xs" title={uploadIssue.name}>
                      {uploadIssue.name}
                    </p>
                    <div className="mt-1 break-words text-xs text-[var(--muted-foreground)]">
                      <ErrorMessage error={uploadIssue.detail} />
                    </div>
                    <p className="mt-2 text-xs">
                      {t("uploadRemaining", { count: uploadIssue.remaining })}
                    </p>
                    <Button
                      type="button"
                      variant="outline"
                      className="mt-2"
                      onClick={() => {
                        setUploadIssue(null);
                        composerRef.current?.focus({ preventScroll: true });
                      }}
                    >
                      {t(attachments.length ? "keepAttachedFiles" : "continueWithoutFiles")}
                    </Button>
                  </div>
                ) : null}
                {uploadNotice ? (
                  <p role="status" className="mb-2 text-xs text-[var(--muted-foreground)]">
                    {uploadNotice}
                  </p>
                ) : null}
                <AttachmentList
                  busy={submitting || uploading}
                  files={attachments}
                  onRemove={(id) => {
                    setUploadNotice("");
                    setAttachments((current) => current.filter((item) => item.id !== id));
                  }}
                />
                <label className="sr-only" htmlFor="composer">
                  {t("composer")}
                </label>
                <textarea
                  className="max-h-44 min-h-12 w-full resize-none border-0 bg-transparent px-1 py-1 text-[15px] composer-field"
                  disabled={loading}
                  id="composer"
                  onChange={(event) => {
                    const typed = event.target.value;
                    const caret = event.target.selectionStart ?? typed.length;
                    if (mentionStarted(draft, typed, caret)) {
                      // "@" opens the document picker. It is not part of the message.
                      setDraft(typed.slice(0, caret - 1) + typed.slice(caret));
                      setPicking(true);
                    } else setDraft(typed);
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
                  title={t("hint")}
                  rows={2}
                  value={draft}
                />
                <details className="mb-2 rounded-lg text-xs text-[var(--muted-foreground)]">
                  <summary className="w-fit cursor-pointer rounded-md px-1 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
                    {t("chatOptions")}
                  </summary>
                  <div className="mt-1 flex flex-wrap items-center gap-2 rounded-lg border border-[var(--border)] p-3">
                    <Button
                      aria-pressed={researchOn}
                      className="h-8 px-2 text-xs font-normal text-[var(--muted-foreground)]"
                      onClick={() => setResearchOn((current) => !current)}
                      type="button"
                      variant={researchOn ? "outline" : "ghost"}
                    >
                      {t("research")}
                    </Button>
                    <ReferencePicker
                      label={t("agent")}
                      items={agentChoices}
                      getDescription={(agent) => agent.slug || agent.id}
                      hideLabel
                      emptyLabel={
                        defaultAgent && !agentProblem ? defaultAgentName : availability("choose")
                      }
                      selection={selectedAgent ? agentReference(selectedAgent) : null}
                      emptyMessage={availability("empty")}
                      resetLabel={defaultAgent ? t("useDefaultAgent") : undefined}
                      clearable={Boolean(defaultAgent)}
                      help={`${t("agentChoiceHelp")} ${availability("help")}`}
                      disabled={
                        loading ||
                        modelSaving ||
                        Boolean(runAction) ||
                        Boolean(runIssue) ||
                        stream.status === "streaming"
                      }
                      onChange={chooseAgent}
                      value={agentId}
                    />
                    <ReferencePicker
                      label={t("model")}
                      items={aliasChoices}
                      getDescription={() => ""}
                      hideLabel
                      emptyLabel={t("modelDefault")}
                      resetLabel={t("useAgentModel")}
                      help={t("modelChoiceHelp")}
                      disabled={
                        loading ||
                        conversationLoading ||
                        conversationProblem ||
                        modelSaving ||
                        Boolean(runAction) ||
                        Boolean(runIssue) ||
                        Boolean(modelProblem) ||
                        stream.status === "streaming"
                      }
                      onChange={(next) => void chooseModel(next)}
                      value={modelAlias}
                    />
                    <details className="text-xs text-[var(--muted-foreground)]">
                      <summary className="cursor-pointer py-2">{t("taskOptions")}</summary>
                      <div className="mt-2 grid gap-2">
                        <input
                          aria-label={t("taskTemplate")}
                          className="h-8 rounded-md border border-[var(--border)] bg-transparent px-2"
                          onChange={(event) => setTaskTemplate(event.target.value)}
                          placeholder={t("taskTemplateHint")}
                          value={taskTemplate}
                        />
                        <textarea
                          aria-label={t("checklist")}
                          className="min-h-16 rounded-md border border-[var(--border)] bg-transparent px-2 py-1"
                          onChange={(event) => setChecklist(event.target.value)}
                          placeholder={t("checklistHint")}
                          value={checklist}
                        />
                        <input
                          aria-label={t("collections")}
                          className="h-8 rounded-md border border-[var(--border)] bg-transparent px-2"
                          onChange={(event) => setCollectionIds(event.target.value)}
                          placeholder={t("collectionsHint")}
                          value={collectionIds}
                        />
                      </div>
                    </details>
                  </div>
                </details>
                {!loading && !loadError && (agentProblem || (!activeId && !canStartChat)) ? (
                  <div
                    className="mb-3 rounded-lg border border-[var(--border)] p-3 text-sm"
                    role="alert"
                  >
                    <p>
                      {agentProblem
                        ? availability("requestedUnavailable")
                        : agentChoices.length
                          ? availability("chooseHelp")
                          : availability("empty")}
                    </p>
                    {defaultAgent && agentProblem ? (
                      <Button
                        className="mt-2"
                        type="button"
                        variant="outline"
                        onClick={() => chooseAgent("")}
                      >
                        {t("useDefaultAgent")}
                      </Button>
                    ) : null}
                  </div>
                ) : null}
                {cancelState || runAction || editing || runNotice ? (
                  <p className="mb-2 text-xs text-[var(--muted-foreground)]" role="status">
                    {cancelState
                      ? t(cancelState === "requesting" ? "stopPending" : "stopRequested")
                      : runAction
                        ? t(`actions.${runAction}`)
                        : editing
                          ? t("finishEdit")
                          : runNotice}
                  </p>
                ) : null}
                {cancelError ? (
                  <div
                    role="alert"
                    className="mb-3 rounded-lg border border-[var(--border)] p-3 text-sm"
                  >
                    <p>{t("stopUnconfirmed")}</p>
                    <div className="mt-1 break-words text-xs text-[var(--muted-foreground)]">
                      <ErrorMessage error={cancelError} />
                    </div>
                    {runId ? (
                      <a
                        className="mt-2 inline-block underline"
                        href={`/runs/${encodeURIComponent(runId)}`}
                      >
                        {t("viewTrace")}
                      </a>
                    ) : null}
                  </div>
                ) : null}
                {runIssue ? (
                  <div
                    className="mb-3 rounded-lg border border-[var(--border)] p-3 text-sm"
                    role={runIssue.detail ? "alert" : "status"}
                  >
                    <p>
                      {runIssue.status && isTerminalRunStatus(runIssue.status)
                        ? t("stopEndedRefresh")
                        : runIssue.cancelRequested
                          ? t("stopRequested")
                          : runIssue.status === "waiting_approval"
                            ? t("actionWaitingApproval")
                            : runIssue.status === "waiting_input"
                              ? t("actionWaitingInput")
                              : runIssue.status
                                ? t("actionStillRunning")
                                : t(
                                    runIssue.accepted
                                      ? "actionAcceptedRecovery"
                                      : runIssue.action === "send"
                                        ? "messageUnconfirmed"
                                        : "actionUnconfirmed",
                                  )}
                    </p>
                    {runIssue.detail ? (
                      <div className="mt-1 break-words text-xs text-[var(--muted-foreground)]">
                        <ErrorMessage error={runIssue.detail} />
                      </div>
                    ) : null}
                    <div className="mt-2 flex flex-wrap items-center gap-3">
                      <Button
                        disabled={Boolean(runAction)}
                        onClick={(event) => void refreshRunAction(event.currentTarget)}
                        type="button"
                        variant="outline"
                      >
                        {t("refreshChat")}
                      </Button>
                      {runIssue.runId ? (
                        <a
                          className="underline"
                          href={`/runs/${encodeURIComponent(runIssue.runId)}`}
                        >
                          {t("viewTrace")}
                        </a>
                      ) : null}
                      {runIssue.status === "waiting_approval" ||
                      runIssue.status === "waiting_input" ? (
                        <a className="underline" href="/inbox">
                          {t("openInbox")}
                        </a>
                      ) : null}
                    </div>
                  </div>
                ) : null}
                {modelSaving || modelNotice ? (
                  <p className="mb-2 text-xs text-[var(--muted-foreground)]" role="status">
                    {modelSaving
                      ? t(modelAction === "refreshing" ? "modelRefreshing" : "modelSaving")
                      : modelNotice}
                  </p>
                ) : null}
                {modelProblem ? (
                  <div
                    className="mb-3 rounded-lg border border-[var(--destructive)] p-3 text-sm"
                    role="alert"
                  >
                    <p>{t("modelUnconfirmed")}</p>
                    <div className="mt-1 break-words text-xs">
                      <ErrorMessage error={modelProblem} />
                    </div>
                    <Button
                      className="mt-2"
                      disabled={modelSaving}
                      onClick={() => void chooseModel(modelAlias, true)}
                      type="button"
                      variant="outline"
                    >
                      {t("modelRefresh")}
                    </Button>
                  </div>
                ) : null}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 flex-wrap items-center gap-1">
                    <Button
                      aria-label={t("pickDocuments")}
                      aria-expanded={picking}
                      className="h-8 px-2 text-xs font-normal text-[var(--muted-foreground)]"
                      disabled={attachmentBlocked}
                      onClick={() => setPicking((open) => !open)}
                      type="button"
                      variant="ghost"
                    >
                      {t("pickDocuments")}
                    </Button>
                    <input
                      accept={accept}
                      disabled={attachmentBlocked}
                      aria-label={t("attach")}
                      className="sr-only"
                      multiple
                      onChange={(event) => {
                        if (event.target.files?.length) {
                          void onUpload(event.target.files);
                        }
                        event.target.value = "";
                      }}
                      ref={fileRef}
                      type="file"
                    />
                    <Button
                      className="h-8 px-2 text-xs font-normal text-[var(--muted-foreground)]"
                      onClick={() => fileRef.current?.click()}
                      disabled={attachmentBlocked}
                      type="button"
                      variant="ghost"
                    >
                      <Paperclip size={15} aria-hidden="true" />
                      <span className="ml-1.5">{t("attach")}</span>
                    </Button>
                  </div>
                  {stream.status === "streaming" ? (
                    <Button
                      className="h-8 px-3 text-xs"
                      disabled={!runId || Boolean(cancelState)}
                      onClick={() => void stop()}
                      type="button"
                      variant="outline"
                    >
                      {t(cancelState ? "stopping" : "stop")}
                    </Button>
                  ) : (
                    <Button
                      aria-label={t("send")}
                      className="size-9 rounded-xl p-0"
                      disabled={!draft.trim() || generationBlocked || Boolean(editing)}
                      type="submit"
                    >
                      <ArrowUp size={18} aria-hidden="true" />
                    </Button>
                  )}
                </div>
              </div>
              <p className="mt-3 text-center text-[10px] text-[var(--muted-foreground)]">
                {t("privateNote")}
              </p>
            </form>
          </div>
          {activeId ? (
            <div
              className={cn(
                "hidden h-full shrink-0 overflow-hidden transition-[width] duration-200 ease-out motion-reduce:transition-none md:block",
                detailsOpen ? "w-80" : "w-0",
              )}
              id="chat-details"
            >
              {detailsOpen ? (
                <div className="flex h-full w-80 flex-col">
                  {detailRunId ? (
                    <RunDetails
                      agents={agents}
                      runId={detailRunId}
                      settled={stream.status !== "streaming"}
                    />
                  ) : null}
                  <div className="min-h-0 flex-1">
                    <WorkspacePanel
                      conversationId={activeId}
                      revision={
                        messages.length +
                        stream.tools.length +
                        (stream.status === "completed" ? 1 : 0)
                      }
                    />
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}
