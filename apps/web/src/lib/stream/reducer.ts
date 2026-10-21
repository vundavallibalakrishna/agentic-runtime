export type StreamEvent = {
  type: string;
  seq: number;
  data?: { text?: string; messageId?: string };
};

export type StreamState = {
  status: "idle" | "streaming" | "completed" | "cancelled" | "failed";
  text: string;
  lastSeq: number;
};

export const emptyStream: StreamState = { status: "idle", text: "", lastSeq: 0 };

export function reduceStream(state: StreamState, event: StreamEvent): StreamState {
  if (event.seq <= state.lastSeq) {
    return state;
  }
  const next = { ...state, lastSeq: event.seq };
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
