"use client";

import { useTranslations } from "next-intl";

type FileRow = { fileId?: string; file_id?: string; name?: string };
type Hit = { title?: string; url?: string; snippet?: string };

function text(value: unknown) {
  return value == null ? "" : String(value);
}

function presentationOf(call: Record<string, unknown>) {
  const raw = call.presentation;
  return raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
}

function filesOf(presentation: Record<string, unknown>): FileRow[] {
  const raw = presentation.files;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.filter((item): item is FileRow => !!item && typeof item === "object");
}

export function ToolCallCard({ call, label }: { call: Record<string, unknown>; label: string }) {
  const t = useTranslations("chat");
  const name = text(call.qualifiedName ?? call.qualified_name ?? "tool");
  const preview = text(call.resultPreview ?? call.result_preview ?? "");
  const approvalId = text(call.approvalId ?? call.approval_id ?? "");
  const waiting = text(call.status ?? "") === "awaiting_approval";
  const presentation = presentationOf(call);
  const kind = text(presentation.kind);
  const error = call.error;
  const connect =
    error && typeof error === "object"
      ? text(
          (error as { connectUrl?: string; connect_url?: string }).connectUrl ??
            (error as { connect_url?: string }).connect_url ??
            "",
        )
      : "";
  const files = filesOf(presentation);
  const hits = Array.isArray(presentation.results) ? (presentation.results as Hit[]) : [];
  return (
    <section className="mt-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm">
      <p className="sr-only">{label}</p>
      <p className="font-medium">{name}</p>
      <p className="text-[var(--muted-foreground)]">{text(call.status ?? "")}</p>
      {kind === "code" || kind === "shell" ? (
        <div className="mt-2 space-y-2">
          <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--muted)] p-2 text-xs">
            {text(presentation.command)}
          </pre>
          <p>
            {t("exitCode")} {text(presentation.exitCode ?? presentation.exit_code)}
          </p>
          {text(presentation.stdout) ? (
            <pre className="overflow-x-auto whitespace-pre-wrap text-xs">
              {text(presentation.stdout)}
            </pre>
          ) : null}
          {text(presentation.stderr) ? (
            <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-[var(--destructive)]">
              {text(presentation.stderr)}
            </pre>
          ) : null}
        </div>
      ) : null}
      {kind === "fetch" ? (
        <div className="mt-2">
          <p className="font-medium">{text(presentation.title)}</p>
          <p className="text-[var(--muted-foreground)]">{text(presentation.url)}</p>
          <p className="mt-1 whitespace-pre-wrap">{text(presentation.snippet)}</p>
        </div>
      ) : null}
      {kind === "search" ? (
        <ul className="mt-2 space-y-2">
          {hits.map((hit) => (
            <li key={`${hit.url}-${hit.title}`}>
              <p className="font-medium">{hit.title}</p>
              <p className="text-[var(--muted-foreground)]">{hit.url}</p>
              <p>{hit.snippet}</p>
            </li>
          ))}
        </ul>
      ) : null}
      {kind === "http" || kind === "mcp" || kind === "openapi" || kind === "described" ? (
        <div className="mt-2">
          <p>
            {text(presentation.method)} {text(presentation.url)}
          </p>
          <p>
            {t("httpStatus")} {text(presentation.status)}
          </p>
          {text(presentation.snippet) ? (
            <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-xs">
              {text(presentation.snippet)}
            </pre>
          ) : null}
        </div>
      ) : null}
      {files.length > 0 ? (
        <ul className="mt-2 space-y-1">
          {files.map((file) => {
            const id = text(file.fileId ?? file.file_id);
            return (
              <li key={id || file.name}>
                {id ? (
                  <a className="underline" href={`/api/v1/files/${id}/content`}>
                    {t("downloadFile", { name: file.name || id })}
                  </a>
                ) : (
                  <span>{file.name}</span>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}
      {kind !== "code" &&
      kind !== "shell" &&
      kind !== "fetch" &&
      kind !== "search" &&
      kind !== "http" &&
      kind !== "mcp" &&
      kind !== "openapi" &&
      kind !== "described" &&
      preview ? (
        <p className="mt-1 whitespace-pre-wrap">{preview}</p>
      ) : null}
      {waiting && approvalId ? (
        <a className="mt-2 inline-block underline" href={`/approvals/${approvalId}`}>
          {t("reviewApproval")}
        </a>
      ) : null}
      {connect ? (
        <a className="mt-2 inline-block underline" href={connect}>
          {t("connectAccount")}
        </a>
      ) : null}
    </section>
  );
}
