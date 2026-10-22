type StreamTool = {
  name: string;
  status: string;
  preview: string;
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
  };
};

export type StreamState = {
  status: "idle" | "streaming" | "completed" | "cancelled" | "failed";
  text: string;
  lastSeq: number;
  tools: StreamTool[];
};

export const emptyStream: StreamState = { status: "idle", text: "", lastSeq: 0, tools: [] };

export function reduceStream(state: StreamState, event: StreamEvent): StreamState {
  if (event.seq <= state.lastSeq) {
    return state;
  }
  const next = { ...state, lastSeq: event.seq, tools: state.tools };
  if (
    event.type === "tool_call.completed" ||
    event.type === "tool_call.failed" ||
    event.type === "tool_call.approval_required" ||
    event.type === "tool_call.approval_resolved"
  ) {
    const tool = {
      name: event.data?.qualifiedName ?? "tool",
      status: event.data?.status ?? event.type,
      preview: event.data?.resultPreview ?? "",
    };
    return { ...next, status: "streaming", tools: [...state.tools, tool] };
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
  if (event.type === "run.started" || event.type === "run.queued") {
    return { ...next, status: "streaming" };
  }
  return next;
}
