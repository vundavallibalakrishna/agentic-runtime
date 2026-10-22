"use client";

import { Background, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useState } from "react";

import type { TraceEdge, TraceNode } from "./trace";

const nodeStyle = {
  background: "var(--card)",
  color: "var(--foreground)",
  border: "1px solid var(--border)",
  borderRadius: 12,
  fontSize: 13,
  padding: 8,
};

export function RunTraceGraph({ nodes, edges }: { nodes: TraceNode[]; edges: TraceEdge[] }) {
  const [colorMode, setColorMode] = useState<"light" | "dark">("light");

  useEffect(() => {
    const root = document.documentElement;
    const sync = () => setColorMode(root.classList.contains("dark") ? "dark" : "light");
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return (
    <div className="h-[28rem] overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <ReactFlow
        colorMode={colorMode}
        edges={edges.map((edge) => ({ id: edge.id, source: edge.source, target: edge.target }))}
        elementsSelectable={false}
        fitView
        nodes={nodes.map((node) => ({
          id: node.id,
          position: { x: node.x, y: node.y },
          data: { label: `${node.label}${node.status ? ` · ${node.status}` : ""}` },
          style: nodeStyle,
        }))}
        nodesConnectable={false}
        nodesDraggable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
      </ReactFlow>
    </div>
  );
}
