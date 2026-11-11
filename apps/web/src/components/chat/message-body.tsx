"use client";

import { Followups, followupsOf } from "@/components/chat/followups";
import { ChartView } from "@/components/chat/interactive-chart";
import { MarkdownView } from "@/components/chat/markdown-view";
import { ThinkingBlock } from "@/components/chat/thinking-block";
import { ArtifactView } from "@/components/computer/artifact-view";

type Part = {
  type?: string;
  text?: string;
  fileId?: string;
  file_id?: string;
  name?: string;
  mimeType?: string;
  mime_type?: string;
  alt?: string;
};

function partsOf(message: Record<string, unknown>): Part[] {
  return Array.isArray(message.content) ? (message.content as Part[]) : [];
}

function chartCalls(message: Record<string, unknown>): {
  presentation: Record<string, unknown>;
  files: { id: string; name: string }[];
}[] {
  const calls = message.toolCalls;
  if (!Array.isArray(calls)) return [];
  const found: {
    presentation: Record<string, unknown>;
    files: { id: string; name: string }[];
  }[] = [];
  for (const call of calls) {
    if (!call || typeof call !== "object") continue;
    const presentation = (call as { presentation?: unknown }).presentation;
    if (!presentation || typeof presentation !== "object") continue;
    const row = presentation as Record<string, unknown>;
    if (row.kind !== "chart") continue;
    const raw = Array.isArray(row.files) ? row.files : [];
    const files = raw.flatMap((file) => {
      if (!file || typeof file !== "object") return [];
      const item = file as { fileId?: string; file_id?: string; name?: string };
      const id = String(item.fileId ?? item.file_id ?? "");
      if (!id) return [];
      return [{ id, name: String(item.name ?? "chart.png") }];
    });
    found.push({ presentation: row, files });
  }
  return found;
}

function imageParts(message: Record<string, unknown>) {
  const figures: { id: string; name: string; mime: string }[] = [];
  for (const part of partsOf(message)) {
    if (part.type === "image") {
      const id = String(part.fileId ?? part.file_id ?? "");
      if (id) figures.push({ id, name: part.alt || "image", mime: "image/png" });
    }
    if (part.type === "file") {
      const id = String(part.fileId ?? part.file_id ?? "");
      const mime = String(part.mimeType ?? part.mime_type ?? "");
      const name = String(part.name ?? "file");
      if (id && (mime.startsWith("image/") || /\.(png|jpe?g|gif|webp)$/i.test(name))) {
        figures.push({ id, name, mime: mime || "image/png" });
      }
    }
  }
  const calls = message.toolCalls;
  if (Array.isArray(calls)) {
    for (const call of calls) {
      if (!call || typeof call !== "object") continue;
      const presentation = (call as { presentation?: unknown }).presentation;
      if (!presentation || typeof presentation !== "object") continue;
      const files = (presentation as { files?: unknown }).files;
      if (!Array.isArray(files)) continue;
      for (const file of files) {
        if (!file || typeof file !== "object") continue;
        const row = file as { fileId?: string; file_id?: string; name?: string; mimeType?: string };
        const id = String(row.fileId ?? row.file_id ?? "");
        const name = String(row.name ?? "");
        if (
          id &&
          /\.(png|jpe?g|gif|webp)$/i.test(name) &&
          !figures.some((item) => item.id === id)
        ) {
          figures.push({ id, name, mime: row.mimeType || "image/png" });
        }
      }
    }
  }
  return figures;
}

export function MessageBody({
  message,
  text,
  reasoning,
  reasoningMs,
  prompts,
  onFollowup,
}: {
  message: Record<string, unknown>;
  text: string;
  reasoning?: string;
  reasoningMs?: number;
  prompts?: string[];
  onFollowup?: (prompt: string) => void;
}) {
  const storedReasoning = typeof message.reasoning === "string" ? message.reasoning : "";
  const thought = reasoning || storedReasoning;
  const next = prompts ?? followupsOf(message);
  const charts = chartCalls(message);
  const chartFiles = new Set(charts.flatMap((chart) => chart.files.map((file) => file.id)));
  const imageAlt = new Map(
    partsOf(message)
      .filter((part) => part.type === "image")
      .map((part) => [String(part.fileId ?? part.file_id ?? ""), String(part.alt ?? "")]),
  );
  const retrieval =
    message.retrieval && typeof message.retrieval === "object"
      ? (message.retrieval as { error?: unknown }).error
      : undefined;
  return (
    <div>
      <ThinkingBlock durationMs={reasoningMs} text={thought} />
      {text ? <MarkdownView text={text} /> : null}
      {typeof retrieval === "string" && retrieval ? (
        <p className="mt-2 text-sm text-[var(--destructive)]" role="alert">
          {retrieval}
        </p>
      ) : null}
      {charts.map((chart) => (
        <ChartView
          alt={imageAlt.get(chart.files[0]?.id ?? "")}
          files={chart.files}
          key={chart.files.map((file) => file.id).join("-") || String(chart.presentation.title)}
          presentation={chart.presentation}
        />
      ))}
      <div className="mt-3 space-y-3">
        {imageParts(message)
          .filter((file) => !chartFiles.has(file.id))
          .map((file) => (
            <ArtifactView
              file={{ id: file.id, name: file.name, mimeType: file.mime }}
              key={file.id}
            />
          ))}
      </div>
      {onFollowup ? <Followups onPick={onFollowup} prompts={next} /> : null}
    </div>
  );
}
