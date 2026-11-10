type StreamTool = {
  name: string;
  status: string;
  preview: string;
  arguments?: string;
  presentation?: Record<string, unknown>;
};

export type StreamEvent = {
  type: string;
  seq: number;
  data?: {
    text?: string;
    messageId?: string;
    qualifiedName?: string;
    status?: string;
    resultPreview?: string;
    argumentsPreview?: string;
    presentation?: Record<string, unknown>;
    citation?: StreamCitation;
    factId?: string;
    content?: string;
    scope?: string;
    count?: number;
    code?: string;
    message?: string;
    phase?: string;
    sourceCount?: number;
    queries?: { id?: string; text?: string; title?: string }[];
  };
};

type StreamCitation = {
  index: number;
  title: string;
  snippet: string;
  uri: string;
  documentId?: string;
};

export type StreamMemory = {
  factId: string;
  content: string;
  scope: string;
  status: string;
};

type ResearchQuery = { id: string; text: string };

export type StreamState = {
  status: "idle" | "streaming" | "completed" | "cancelled" | "failed";
  text: string;
  lastSeq: number;
  tools: StreamTool[];
  citations: StreamCitation[];
  memories: StreamMemory[];
  recalled: number;
  compacted: boolean;
  toolFailure: string;
  researchPhase: string;
  researchQueries: ResearchQuery[];
  sourceCount: number;
};

export const emptyStream: StreamState = {
  status: "idle",
  text: "",
  lastSeq: 0,
  tools: [],
  citations: [],
  memories: [],
  recalled: 0,
  compacted: false,
  toolFailure: "",
  researchPhase: "",
  researchQueries: [],
  sourceCount: 0,
};

export function reduceStream(state: StreamState, event: StreamEvent): StreamState {
  if (event.seq <= state.lastSeq) {
    return state;
  }
  const next = {
    ...state,
    lastSeq: event.seq,
    tools: state.tools,
    citations: state.citations,
    memories: state.memories,
  };
  if (event.type === "citation.added") {
    const raw = event.data?.citation;
    if (!raw || typeof raw !== "object") {
      return next;
    }
    const citation = raw as StreamCitation;
    return { ...next, citations: [...state.citations, citation] };
  }
  if (event.type === "tool_call.started") {
    const tool: StreamTool = {
      name: event.data?.qualifiedName ?? "tool",
      status: "running",
      preview: "",
      arguments: event.data?.argumentsPreview ?? "",
      presentation: event.data?.presentation,
    };
    return { ...next, status: "streaming", tools: [...state.tools, tool] };
  }
  if (event.type === "tool_call.approval_required") {
    const preview = event.data?.resultPreview ?? event.data?.text ?? "";
    const tool = {
      name: event.data?.qualifiedName ?? "tool",
      status: "awaiting_approval",
      preview,
      presentation: event.data?.presentation,
    };
    return {
      ...next,
      status: "streaming",
      text: preview || state.text,
      tools: [...state.tools, tool],
    };
  }
  if (
    event.type === "tool_call.completed" ||
    event.type === "tool_call.failed" ||
    event.type === "tool_call.approval_resolved"
  ) {
    const tool: StreamTool = {
      name: event.data?.qualifiedName ?? "tool",
      status: event.data?.status ?? event.type,
      preview: event.data?.resultPreview ?? "",
      arguments: event.data?.argumentsPreview,
      presentation: event.data?.presentation,
    };
    const running = state.tools.findIndex(
      (item) => item.name === tool.name && item.status === "running",
    );
    const tools =
      running === -1
        ? [...state.tools, tool]
        : state.tools.map((item, index) =>
            index === running
              ? { ...item, ...tool, arguments: item.arguments || tool.arguments }
              : item,
          );
    return { ...next, status: "streaming", tools };
  }
  if (event.type === "message.delta") {
    return { ...next, status: "streaming", text: state.text + (event.data?.text ?? "") };
  }
  if (event.type === "message.completed") {
    return { ...next, status: "completed", text: event.data?.text ?? state.text };
  }
  if (event.type === "message.started" && event.data && "reset" in event.data) {
    return { ...next, status: "streaming", text: "" };
  }
  if (event.type === "run.cancelled") {
    return { ...next, status: "cancelled" };
  }
  if (event.type === "run.failed") {
    return { ...next, status: "failed" };
  }
  if (event.type === "memory.saved" && event.data?.factId) {
    const memory = {
      factId: event.data.factId,
      content: event.data.content ?? "",
      scope: event.data.scope ?? "user",
      status: event.data.status ?? "active",
    };
    return { ...next, memories: [...state.memories, memory] };
  }
  if (event.type === "memory.recalled") {
    return { ...next, recalled: event.data?.count ?? 0 };
  }
  if (event.type === "context.compacted") {
    return { ...next, compacted: true };
  }
  if (event.type === "warning" && event.data?.code === "tool_failed") {
    return {
      ...next,
      toolFailure: event.data.message ?? "A tool call failed and was not recovered.",
    };
  }
  if (event.type === "research.progress") {
    const queries = Array.isArray(event.data?.queries)
      ? event.data.queries.map((item, index) => ({
          id: String(item.id ?? index + 1),
          text: String(item.text ?? item.title ?? ""),
        }))
      : state.researchQueries;
    return {
      ...next,
      status: "streaming",
      researchPhase: event.data?.phase ?? state.researchPhase,
      researchQueries: queries.filter((item) => item.text),
      sourceCount: event.data?.sourceCount ?? state.sourceCount,
    };
  }
  if (event.type === "run.started" || event.type === "run.queued") {
    return { ...next, status: "streaming" };
  }
  return next;
}
