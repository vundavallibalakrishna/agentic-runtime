"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { ArtifactView } from "@/components/computer/artifact-view";
import { api } from "@/lib/api";

type Row = Record<string, unknown>;

export function WorkspacePanel({
  conversationId,
  revision = 0,
}: {
  conversationId: string;
  revision?: number;
}) {
  const t = useTranslations("computer");
  const [files, setFiles] = useState<Row[]>([]);
  const [tree, setTree] = useState<Row[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"files" | "computer">("files");

  useEffect(() => {
    if (!conversationId) {
      return;
    }
    void revision;
    let gone = false;
    setLoading(true);
    setError("");
    void (async () => {
      try {
        const listed = await api<{ items: Row[] }>(
          `/api/v1/files?conversationId=${conversationId}`,
        );
        const sandbox = await api<Row>(`/api/v1/conversations/${conversationId}/sandbox`).catch(
          () => null,
        );
        let entries: Row[] = [];
        if (sandbox && typeof sandbox.id === "string") {
          const page = await api<{ items: Row[] }>(`/api/v1/sandboxes/${sandbox.id}/files`);
          entries = page.items ?? [];
          if (!gone) {
            setStatus(String(sandbox.status ?? ""));
          }
        }
        if (!gone) {
          setFiles(listed.items ?? []);
          setTree(entries);
        }
      } catch (caught) {
        if (!gone) {
          setError(caught instanceof Error ? caught.message : t("error"));
        }
      } finally {
        if (!gone) {
          setLoading(false);
        }
      }
    })();
    return () => {
      gone = true;
    };
  }, [conversationId, revision, t]);

  if (!conversationId) {
    return null;
  }
  return (
    <aside
      aria-label={t("title")}
      className="border-t border-[var(--border)] bg-[var(--card)] px-4 py-3 md:border-t-0 md:border-l"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium">{t("title")}</h2>
        {status ? <p className="text-xs text-[var(--muted-foreground)]">{status}</p> : null}
      </div>
      <div className="mb-3 flex gap-2">
        <button className="text-sm underline" onClick={() => setTab("files")} type="button">
          {t("artifacts")}
        </button>
        <button className="text-sm underline" onClick={() => setTab("computer")} type="button">
          {t("workspace")}
        </button>
      </div>
      {loading ? <p className="text-sm text-[var(--muted-foreground)]">{t("loading")}</p> : null}
      {error ? (
        <p className="text-sm" role="alert">
          {error}
        </p>
      ) : null}
      {!loading && tab === "files" && files.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
      ) : null}
      {tab === "files"
        ? files.map((file) => (
            <div className="mb-3" key={String(file.id)}>
              <p className="mb-1 text-xs text-[var(--muted-foreground)]">{String(file.name)}</p>
              <ArtifactView
                file={{
                  id: String(file.id ?? ""),
                  name: String(file.name ?? ""),
                  mimeType: String(file.mimeType ?? ""),
                  preview: previewOf(file.preview),
                }}
              />
            </div>
          ))
        : null}
      {tab === "computer" && tree.length === 0 && !loading ? (
        <p className="text-sm text-[var(--muted-foreground)]">{t("emptyWorkspace")}</p>
      ) : null}
      {tab === "computer" ? (
        <ul className="space-y-1 font-mono text-xs">
          {tree.map((entry) => (
            <li key={String(entry.path)}>{String(entry.path)}</li>
          ))}
        </ul>
      ) : null}
    </aside>
  );
}

function previewOf(value: unknown): { rows?: string[][] } | undefined {
  if (!value || typeof value !== "object") {
    return undefined;
  }
  const rows = (value as { rows?: unknown }).rows;
  if (!Array.isArray(rows)) {
    return undefined;
  }
  return {
    rows: rows.filter(Array.isArray).map((row) => row.map((cell) => String(cell))),
  };
}
