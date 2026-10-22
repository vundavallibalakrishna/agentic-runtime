export type TraceNode = {
  id: string;
  label: string;
  kind: "run" | "child" | "step" | "tool";
  status: string;
  x: number;
  y: number;
};

export type TraceEdge = {
  id: string;
  source: string;
  target: string;
};

type RunRow = {
  id?: string;
  status?: string;
  trigger?: string;
  agentName?: string;
  agentSlug?: string;
};

type StepRow = {
  id?: string;
  kind?: string;
  detail?: { agent?: string; childRunId?: string };
};

type ToolRow = {
  id?: string;
  qualifiedName?: string;
  status?: string;
};

export function buildTrace(input: {
  run: RunRow;
  children: RunRow[];
  steps: StepRow[];
  tools: ToolRow[];
}): { nodes: TraceNode[]; edges: TraceEdge[] } {
  const runId = input.run.id || "run";
  const nodes: TraceNode[] = [
    {
      id: runId,
      label: input.run.trigger || "run",
      kind: "run",
      status: input.run.status || "",
      x: 0,
      y: 0,
    },
  ];
  const edges: TraceEdge[] = [];
  input.children.forEach((child, index) => {
    const id = child.id || `child-${index}`;
    nodes.push({
      id,
      label: child.agentName || child.agentSlug || "Subagent",
      kind: "child",
      status: child.status || "",
      x: 280,
      y: index * 96,
    });
    edges.push({ id: `${runId}-${id}`, source: runId, target: id });
  });
  input.steps.forEach((step, index) => {
    const id = step.id || `step-${index}`;
    nodes.push({
      id,
      label: step.detail?.agent || step.kind || "step",
      kind: "step",
      status: step.kind || "",
      x: 0,
      y: 120 + index * 72,
    });
    edges.push({ id: `${runId}-${id}`, source: runId, target: id });
  });
  input.tools.forEach((tool, index) => {
    const id = tool.id || `tool-${index}`;
    nodes.push({
      id,
      label: tool.qualifiedName || "tool",
      kind: "tool",
      status: tool.status || "",
      x: 280,
      y: 120 + input.children.length * 96 + index * 72,
    });
    edges.push({ id: `${runId}-${id}`, source: runId, target: id });
  });
  return { nodes, edges };
}
