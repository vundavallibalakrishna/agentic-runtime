"use client";

import { Paperclip } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

export type Attached = { id: string; name: string; mimeType: string; sizeBytes?: number };

const KIB = 1024;

export function fileSize(bytes: number | undefined): string {
  if (bytes === undefined || !Number.isFinite(bytes)) return "";
  if (bytes < KIB) return `${bytes} B`;
  if (bytes < KIB * KIB) return `${(bytes / KIB).toFixed(1)} kB`;
  return `${(bytes / (KIB * KIB)).toFixed(1)} MB`;
}

/** The files that came with a message, or that are about to. Each opens, or can be taken off. */
export function AttachmentList({
  files,
  onRemove,
  busy,
}: {
  files: Attached[];
  onRemove?: (id: string) => void;
  busy?: boolean;
}) {
  const t = useTranslations("chat");
  if (files.length === 0) return null;
  return (
    <ul aria-label={t("attachedFiles")} className="mt-2 flex flex-wrap gap-2">
      {files.map((file) => {
        const detail = [file.mimeType, fileSize(file.sizeBytes)].filter(Boolean).join(", ");
        return (
          <li
            className="flex items-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-xs"
            key={file.id}
          >
            <Paperclip aria-hidden="true" size={12} />
            <a
              className="underline-offset-2 hover:underline"
              download={file.name}
              href={`/api/v1/files/${file.id}/content`}
              title={detail}
            >
              {file.name}
            </a>
            {detail ? <span className="text-[var(--muted-foreground)]">({detail})</span> : null}
            {onRemove ? (
              <Button
                aria-label={t("removeAttachment", { name: file.name })}
                className="h-5 px-1 text-xs"
                disabled={busy}
                onClick={() => onRemove(file.id)}
                type="button"
                variant="ghost"
              >
                ×
              </Button>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

/** The files a stored message carries, from its content parts. */
export function attachedOf(message: Record<string, unknown>): Attached[] {
  const content = message.content;
  if (!Array.isArray(content)) return [];
  const files: Attached[] = [];
  for (const part of content) {
    if (!part || typeof part !== "object") continue;
    const row = part as {
      type?: string;
      fileId?: string;
      name?: string;
      mimeType?: string;
      sizeBytes?: number;
    };
    if (row.type !== "file" || !row.fileId) continue;
    files.push({
      id: String(row.fileId),
      name: String(row.name ?? "file"),
      mimeType: String(row.mimeType ?? ""),
      sizeBytes: typeof row.sizeBytes === "number" ? row.sizeBytes : undefined,
    });
  }
  return files;
}
