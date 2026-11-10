export type PlanStep = { id: string; title: string; status: string };

type TimelineEntry = { kind: string; text: string };

type StreamWarning = { code: string; message: string };

type StreamTool = {
  name: string;
  status: string;
  preview: string;
  arguments?: string;
  presentation?: Record<string, unknown>;
  timeline: TimelineEntry[];
  attempt?: number;
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
    items?: { id?: string; title?: string; status?: string }[];
    plan?: { id?: string; title?: string; status?: string }[] | string[];
    answeredModel?: string;
    attempt?: number;
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
  plan: PlanStep[];
  reasoning: string;
  reasoningMs: number;
  answeredModel: string;
  warnings: StreamWarning[];
  followups: string[];
  verified: number;
  reasoningStartedAt: number;
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
  plan: [],
  reasoning: "",
  reasoningMs: 0,
  answeredModel: "",
  warnings: [],
  followups: [],
  verified: 0,
  reasoningStartedAt: 0,
};

function planSteps(data: StreamEvent["data"]): PlanStep[] {
  const raw = data?.items ?? data?.plan;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item, index) => {
      if (typeof item === "string") {
        return { id: String(index + 1), title: item, status: "pending" };
      }
      const title = String(item.title ?? "");
      if (!title) return null;
      return {
        id: String(item.id ?? index + 1),
        title,
        status: String(item.status ?? "pending"),
      };
    })
    .filter((item): item is PlanStep => item !== null);
}

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
    const citation = raw as StreamCitation & { verified?: boolean; status?: string };
    const verified =
      citation.verified === true || citation.status === "supported"
        ? state.verified + 1
        : state.verified;
    return { ...next, citations: [...state.citations, citation], verified };
  }
  if (event.type === "tool_call.started") {
    const name = event.data?.qualifiedName ?? "tool";
    const tool: StreamTool = {
      name,
      status: "running",
      preview: "",
      arguments: event.data?.argumentsPreview ?? "",
      presentation: event.data?.presentation,
      timeline: [{ kind: "arguments", text: event.data?.argumentsPreview ?? "" }],
      attempt: event.data?.attempt,
    };
    const failed = [...state.tools]
      .reverse()
      .find((item) => item.name === name && item.status === "failed");
    if (failed) {
      tool.timeline = [
        ...failed.timeline,
        { kind: "retry", text: "Trying again." },
        ...tool.timeline,
      ];
    }
    return { ...next, status: "streaming", tools: [...state.tools, tool] };
  }
  if (event.type === "tool_call.approval_required") {
    const preview = event.data?.resultPreview ?? event.data?.text ?? "";
    const tool = {
      name: event.data?.qualifiedName ?? "tool",
      status: "awaiting_approval",
      preview,
      presentation: event.data?.presentation,
      timeline: [{ kind: "arguments", text: preview }],
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
      timeline: [
        {
          kind: event.type === "tool_call.failed" ? "repair" : "result",
          text: event.data?.resultPreview ?? event.data?.message ?? "",
        },
      ],
      attempt: event.data?.attempt,
    };
    const running = state.tools.findIndex(
      (item) => item.name === tool.name && item.status === "running",
    );
    const tools =
      running === -1
        ? [...state.tools, tool]
        : state.tools.map((item, index) =>
            index === running
              ? {
                  ...item,
                  ...tool,
                  arguments: item.arguments || tool.arguments,
                  timeline: [...item.timeline, ...tool.timeline],
                }
              : item,
          );
    return { ...next, status: "streaming", tools };
  }
  if (event.type === "message.delta") {
    return { ...next, status: "streaming", text: state.text + (event.data?.text ?? "") };
  }
  if (event.type === "reasoning.delta") {
    return {
      ...next,
      status: "streaming",
      reasoning: state.reasoning + (event.data?.text ?? ""),
      reasoningStartedAt: state.reasoningStartedAt || Date.now(),
    };
  }
  if (event.type === "message.completed") {
    const payload = event.data as
      | { content?: unknown; answeredModel?: string; text?: string }
      | undefined;
    const rawContent = payload?.content;
    const parts = Array.isArray(rawContent) ? rawContent : [];
    const prompts = parts.flatMap((part) => {
      if (!part || typeof part !== "object") return [];
      const row = part as { type?: string; prompts?: unknown };
      if (row.type !== "followups" || !Array.isArray(row.prompts)) return [];
      return row.prompts.filter((item): item is string => typeof item === "string");
    });
    const reasoningMs = state.reasoningStartedAt
      ? Date.now() - state.reasoningStartedAt
      : state.reasoningMs;
    return {
      ...next,
      status: "completed",
      text: payload?.text ?? state.text,
      answeredModel: payload?.answeredModel ?? state.answeredModel,
      followups: prompts.length ? prompts : state.followups,
      reasoningMs,
    };
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
  if (event.type === "plan.updated") {
    const plan = planSteps(event.data);
    return { ...next, status: "streaming", plan: plan.length ? plan : state.plan };
  }
  if (event.type === "warning" && event.data?.code) {
    const warning = { code: event.data.code, message: event.data.message ?? "" };
    const tools =
      event.data.code === "repair" && state.tools.length
        ? state.tools.map((item, index) =>
            index === state.tools.length - 1
              ? { ...item, timeline: [...item.timeline, { kind: "repair", text: warning.message }] }
              : item,
          )
        : state.tools;
    if (event.data.code === "tool_failed") {
      return {
        ...next,
        tools,
        toolFailure: warning.message || state.toolFailure,
        warnings: [...state.warnings, warning],
      };
    }
    return { ...next, tools, warnings: [...state.warnings, warning] };
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
