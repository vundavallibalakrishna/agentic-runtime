"use client";

import { useTranslations } from "next-intl";

type FileRow = { fileId?: string; file_id?: string; name?: string };
type Hit = { title?: string; url?: string; snippet?: string };

export function JobMeter({ progress }: { progress: Progress }) {
  const t = useTranslations("chat");
  const completed = Number(progress.completed ?? 0);
  const total = Number(progress.total ?? 0);
  const status = text(progress.status);
  const label = text(progress.label);
  const fraction =
    status === "interrupted"
      ? t("jobInterrupted", { completed, total })
      : status === "failed"
        ? t("jobFailed")
        : total > 0
          ? t("jobProgress", { completed, total })
          : label;
  return (
    <div className="mt-2">
      <p className="text-[var(--muted-foreground)]">
        {label ? `${label}. ` : ""}
        {fraction}
      </p>
      {total > 0 ? (
        <progress
          aria-label={label || fraction}
          className="mt-1 h-2 w-full appearance-none overflow-hidden rounded-full bg-[var(--muted)] accent-[var(--foreground)] [&::-moz-progress-bar]:bg-[var(--foreground)] [&::-webkit-progress-bar]:bg-[var(--muted)] [&::-webkit-progress-value]:bg-[var(--foreground)]"
          max={total}
          value={Math.min(completed, total)}
        />
      ) : null}
      {text(progress.detail) ? (
        <p className="mt-1 text-[var(--muted-foreground)]">{text(progress.detail)}</p>
      ) : null}
    </div>
  );
}

export function JobList({ jobs }: { jobs: Record<string, unknown>[] }) {
  if (jobs.length === 0) {
    return null;
  }
  return (
    <div className="space-y-2">
      {jobs.map((job) => (
        <JobMeter
          key={text(job.id)}
          progress={{
            completed: Number(job.completed ?? 0),
            total: Number(job.total ?? 0),
            label: text(job.label),
            status: text(job.status),
            detail: text(job.detail),
          }}
        />
      ))}
    </div>
  );
}

function text(value: unknown) {
  return value == null ? "" : String(value);
}

function presentationOf(call: Record<string, unknown>) {
  const raw = call.presentation;
  return raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
}

type Progress = {
  completed?: number;
  total?: number;
  label?: string;
  status?: string;
  detail?: string;
};

function progressOf(presentation: Record<string, unknown>): Progress | null {
  const raw = presentation.progress;
  if (!raw || typeof raw !== "object") {
    return null;
  }
  return raw as Progress;
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
  const progress = progressOf(presentation);
  return (
    <section className="mt-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm">
      <p className="sr-only">{label}</p>
      <p className="font-medium">{name}</p>
      <p className="text-[var(--muted-foreground)]">{text(call.status ?? "")}</p>
      {progress ? <JobMeter progress={progress} /> : null}
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
      {kind === "query" || kind === "table" ? (
        <div className="mt-2">
          {text(presentation.sql) ? (
            <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--muted)] p-2 text-xs">
              {text(presentation.sql)}
            </pre>
          ) : null}
          <table className="mt-2 w-full text-left text-xs">
            <thead>
              <tr>
                {(Array.isArray(presentation.columns) ? presentation.columns : []).map((column) => (
                  <th className="border-b border-[var(--border)] pr-2" key={text(column)}>
                    {text(typeof column === "object" ? (column as { name?: string }).name : column)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(Array.isArray(presentation.rows) ? presentation.rows : []).map((row) => {
                const cells = Array.isArray(row) ? row : [];
                const key = cells.map((cell) => text(cell)).join("|");
                return (
                  <tr key={key || text(row)}>
                    {cells.map((cell) => (
                      <td
                        className="border-b border-[var(--border)] pr-2"
                        key={`${key}-${text(cell)}`}
                      >
                        {text(cell)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
          {presentation.truncated ? (
            <p className="mt-1 text-[var(--muted-foreground)]">{t("truncated")}</p>
          ) : null}
        </div>
      ) : null}
      {kind === "summary" || kind === "check" || kind === "gaps" ? (
        <ul className="mt-2 space-y-2">
          {(Array.isArray(presentation.claims)
            ? presentation.claims
            : Array.isArray(presentation.rows)
              ? presentation.rows
              : []
          ).map((item: unknown) => {
            const row = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
            const citation =
              row.citation && typeof row.citation === "object"
                ? (row.citation as Record<string, unknown>)
                : row;
            const anchor = text(citation.anchor);
            const documentId = text(
              citation.documentId ??
                citation.document_id ??
                presentation.documentId ??
                presentation.document_id,
            );
            const label = text(row.text ?? row.requirement);
            return (
              <li key={`${label}-${anchor}`}>
                <p>{label}</p>
                {text(row.verdict) ? (
                  <p className="text-[var(--muted-foreground)]">
                    {text(row.verdict)} {text(row.confidence)}
                  </p>
                ) : null}
                {anchor ? (
                  <a className="underline" href={`/documents/${documentId}#${anchor}`}>
                    {anchor}
                  </a>
                ) : null}
                {text(row.reason) ? (
                  <p className="text-[var(--muted-foreground)]">{text(row.reason)}</p>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      {kind === "compare" ? (
        <ul className="mt-2 space-y-2">
          {(Array.isArray(presentation.changes) ? presentation.changes : []).map((item) => {
            const row = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
            const key = `${text(row.op)}-${text(row.heading)}`;
            return (
              <li key={key}>
                <p className="font-medium">
                  {text(row.op)} {text(row.heading)}
                </p>
                <p className="whitespace-pre-wrap text-xs">{text(row.before)}</p>
                <p className="whitespace-pre-wrap text-xs">{text(row.after)}</p>
              </li>
            );
          })}
        </ul>
      ) : null}
      {kind === "rewrite" ? (
        <div className="mt-2">
          <p>{text(presentation.instruction)}</p>
          <a className="underline" href={`/documents/rewrites/${text(presentation.id)}`}>
            {text(presentation.status)}
          </a>
        </div>
      ) : null}
      {kind === "redact" ? (
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs">
          {text(presentation.redacted)}
        </pre>
      ) : null}
      {kind === "extract" ? (
        <ul className="mt-2 space-y-1">
          {(Array.isArray(presentation.fields) ? presentation.fields : []).map((item) => {
            const row = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
            return (
              <li key={text(row.field)}>
                {text(row.field)}: {row.value == null ? text(row.reason) : text(row.value)}
              </li>
            );
          })}
        </ul>
      ) : null}
      {kind === "chart"
        ? files
            .filter((file) => text(file.name).endsWith(".png"))
            .map((file) => {
              const id = text(file.fileId ?? file.file_id);
              return id ? (
                <img
                  alt={text(presentation.title) || "chart"}
                  className="mt-2 max-w-full rounded-lg border border-[var(--border)]"
                  key={id}
                  src={`/api/v1/files/${id}/content`}
                />
              ) : null;
            })
        : null}
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
      kind !== "query" &&
      kind !== "table" &&
      kind !== "chart" &&
      kind !== "summary" &&
      kind !== "check" &&
      kind !== "gaps" &&
      kind !== "compare" &&
      kind !== "rewrite" &&
      kind !== "redact" &&
      kind !== "extract" &&
      kind !== "document" &&
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
