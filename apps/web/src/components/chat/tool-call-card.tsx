"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { Input } from "@/components/ui/input";
import { TableScroll } from "@/components/ui/table";
import { formatDataValue as text } from "@/lib/format";

type FileRow = { fileId?: string; file_id?: string; name?: string };
type Hit = { title?: string; url?: string; snippet?: string };

function JobMeter({ progress }: { progress: Progress }) {
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

function ToolTimeline({ call }: { call: Record<string, unknown> }) {
  const t = useTranslations("chat");
  const raw = call.timeline;
  const entries = Array.isArray(raw)
    ? raw.filter(
        (item): item is { kind?: string; text?: string } => !!item && typeof item === "object",
      )
    : [];
  if (entries.length === 0) return null;
  const seen = new Map<string, number>();
  return (
    <ol
      aria-label={t("toolTimeline")}
      className="mt-2 space-y-1 border-l border-[var(--border)] pl-3 text-xs"
    >
      {entries.map((entry) => {
        const mark = `${entry.kind ?? "step"}-${entry.text ?? ""}`;
        const count = seen.get(mark) ?? 0;
        seen.set(mark, count + 1);
        return (
          <li key={`${mark}-${count}`}>
            <span className="text-[var(--muted-foreground)]">{timelineLabel(entry.kind, t)}</span>
            {entry.text ? <p className="whitespace-pre-wrap">{entry.text}</p> : null}
          </li>
        );
      })}
    </ol>
  );
}

function timelineLabel(
  kind: string | undefined,
  t: (key: "timelineArguments" | "timelineResult" | "timelineRetry" | "timelineRepair") => string,
): string {
  if (kind === "arguments") return t("timelineArguments");
  if (kind === "result") return t("timelineResult");
  if (kind === "retry") return t("timelineRetry");
  if (kind === "repair") return t("timelineRepair");
  return kind || "step";
}

const MISMATCH_LABELS: Record<
  string,
  "crosscheckValue" | "crosscheckCount" | "crosscheckSummary" | "crosscheckOther"
> = {
  value_mismatch: "crosscheckValue",
  count_mismatch: "crosscheckCount",
  summary_mismatch: "crosscheckSummary",
};

/** The places one document disagrees with itself, each with the passages quoted. */
function Crosscheck({ presentation }: { presentation: Record<string, unknown> }) {
  const t = useTranslations("chat");
  const findings = (Array.isArray(presentation.findings) ? presentation.findings : []).filter(
    (item): item is Record<string, unknown> => !!item && typeof item === "object",
  );
  const documentId = text(presentation.documentId ?? presentation.document_id);
  const read = Number(presentation.passagesRead ?? presentation.passages_read ?? 0);
  const discarded = Number(presentation.discarded ?? 0);
  return (
    <div className="mt-2" data-testid="crosscheck">
      {findings.length === 0 ? (
        <p>{t("crosscheckNone", { count: read })}</p>
      ) : (
        <ul className="space-y-2">
          {findings.map((row) => {
            const quotes = (Array.isArray(row.quotes) ? row.quotes : []).filter(
              (item): item is Record<string, unknown> => !!item && typeof item === "object",
            );
            return (
              <li
                key={`${text(row.statement)}-${quotes.map((quote) => text(quote.anchor)).join("-")}`}
              >
                <p>{text(row.statement)}</p>
                <p className="text-[var(--muted-foreground)]">
                  {t(MISMATCH_LABELS[text(row.kind)] ?? "crosscheckOther")}
                </p>
                {quotes.map((quote) => {
                  const anchor = text(quote.anchor);
                  return (
                    <p
                      className="whitespace-pre-wrap text-xs text-[var(--muted-foreground)]"
                      key={`${anchor}-${text(quote.quote)}`}
                    >
                      <a
                        className="underline"
                        href={`/documents/${encodeURIComponent(documentId)}#${encodeURIComponent(anchor)}`}
                      >
                        {anchor}
                      </a>{" "}
                      {text(quote.quote)}
                    </p>
                  );
                })}
              </li>
            );
          })}
        </ul>
      )}
      {discarded > 0 ? (
        <p className="mt-1 text-[var(--muted-foreground)]">
          {t("crosscheckDiscarded", { count: discarded })}
        </p>
      ) : null}
    </div>
  );
}

/** Tool text that may be wider than the card. It scrolls, so the keyboard must reach it. */
/** How a sample was drawn, so the person can repeat it: the tool's own summary, not its raw text. */
function CalledAgents({ presentation }: { presentation: Record<string, unknown> }) {
  const t = useTranslations("chat");
  const agents = (Array.isArray(presentation.agents) ? presentation.agents : []).filter(
    (item): item is Record<string, unknown> => Boolean(item) && typeof item === "object",
  );
  return (
    <ul className="mt-2 space-y-3" data-testid="called-agents">
      {agents.map((row, position) => {
        const runId = text(row.childRunId ?? row.child_run_id);
        const agent = text(row.agent) || t("calledAgentUnnamed");
        return (
          // An agent can be called twice in one call, so the position names the row.
          // biome-ignore lint/suspicious/noArrayIndexKey: see above
          <li key={`${runId}-${position}`}>
            <p>
              <span className="font-medium">{agent}</span>
              <span className="text-[var(--muted-foreground)]">
                {" · "}
                {friendlyStatus(text(row.status), t)}
              </span>
            </p>
            {text(row.task) ? (
              <p className="whitespace-pre-wrap text-[var(--muted-foreground)]">{text(row.task)}</p>
            ) : null}
            {text(row.summary) ? (
              <p className="mt-1 whitespace-pre-wrap">{text(row.summary)}</p>
            ) : null}
            {runId ? (
              <Link className="mt-1 inline-block underline" href={`/runs/${runId}`}>
                {t("calledAgentSteps", { agent })}
              </Link>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function SampleFacts({ facts }: { facts: unknown }) {
  const t = useTranslations("chat");
  if (!facts || typeof facts !== "object") return null;
  const row = facts as Record<string, unknown>;
  const read = (camel: string, snake: string) => row[camel] ?? row[snake];
  const seed = read("seed", "seed");
  const picked = Number(read("judgmentalRows", "judgmental_rows") ?? 0);
  const lines = [
    t("sampleMethod", { method: String(read("method", "method") ?? "") }),
    seed === null || seed === undefined ? "" : t("sampleSeed", { seed: String(seed) }),
    t("samplePopulation", { count: Number(read("populationRows", "population_rows") ?? 0) }),
    t("sampleDrawn", { count: Number(read("sampledRows", "sampled_rows") ?? 0) }),
    picked > 0 ? t("sampleHandPicked", { count: picked }) : "",
  ].filter(Boolean);
  return (
    <p className="mt-2 text-xs text-[var(--muted-foreground)]" data-testid="sample-facts">
      {lines.join(" · ")}
    </p>
  );
}

function Block({ className, children }: { className: string; children: ReactNode }) {
  return (
    // biome-ignore lint/a11y/noNoninteractiveTabindex: a scrollable region needs keyboard focus
    <pre className={`max-h-80 overflow-auto break-words ${className}`} tabIndex={0}>
      {children}
    </pre>
  );
}

function SavedDiff({ before, after }: { before: unknown; after: unknown }) {
  const t = useTranslations("chat");
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div>
        <p className="text-xs text-[var(--muted-foreground)]">{t("resultBefore")}</p>
        <TableScroll label={t("resultBefore")} className="max-h-64">
          <p className="whitespace-pre-wrap break-words text-xs">{text(before)}</p>
        </TableScroll>
      </div>
      <div>
        <p className="text-xs text-[var(--muted-foreground)]">{t("resultAfter")}</p>
        <TableScroll label={t("resultAfter")} className="max-h-64">
          <p className="whitespace-pre-wrap break-words text-xs">{text(after)}</p>
        </TableScroll>
      </div>
    </div>
  );
}

function resultValues(presentation: Record<string, unknown>, kind: string): unknown[] {
  const value =
    kind === "compare"
      ? presentation.changes
      : kind === "rewrite"
        ? presentation.hunks
        : ["judge", "check", "missing"].includes(kind) && Array.isArray(presentation.claims)
          ? presentation.claims
          : presentation.rows;
  return Array.isArray(value) ? value : [];
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

const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"];

function isImageName(name: string): boolean {
  const lower = name.toLowerCase();
  return IMAGE_EXTENSIONS.some((extension) => lower.endsWith(extension));
}

const TOOL_LABELS: Record<string, "toolChart"> = {
  "general.chart": "toolChart",
  chart: "toolChart",
};

const STATUS_LABELS: Record<
  string,
  "statusDone" | "statusWorking" | "statusFailed" | "statusWaiting" | "statusStopped"
> = {
  succeeded: "statusDone",
  completed: "statusDone",
  running: "statusWorking",
  failed: "statusFailed",
  denied: "statusFailed",
  rejected: "statusFailed",
  expired: "statusFailed",
  timed_out: "statusFailed",
  timeout: "statusFailed",
  upstream_timeout: "statusFailed",
  budget_exceeded: "statusFailed",
  cancelled: "statusStopped",
  awaiting_approval: "statusWaiting",
};

function friendlyName(qualified: string, t: (key: "toolChart") => string): string {
  const known = TOOL_LABELS[qualified];
  if (known) return t(known);
  const leaf = qualified.split(".").pop() || qualified;
  return leaf.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function failureOf(
  call: Record<string, unknown>,
  presentation: Record<string, unknown>,
): { status: string; message: string } {
  // The label is the tool result's status. An error on the call is shown beside it
  // and does not change a status the result already named.
  const raw = text(call.status ?? "");
  const error = call.error;
  const fromError =
    error && typeof error === "object"
      ? text(
          (error as { message?: unknown; detail?: unknown; code?: unknown }).message ??
            (error as { detail?: unknown }).detail ??
            (error as { code?: unknown }).code,
        )
      : text(error);
  const fromPresentation = text(presentation.kind) === "error" ? text(presentation.message) : "";
  return { status: raw, message: fromError || fromPresentation };
}

function friendlyStatus(
  status: string,
  t: (
    key: "statusDone" | "statusWorking" | "statusFailed" | "statusWaiting" | "statusStopped",
  ) => string,
): string {
  const known = STATUS_LABELS[status];
  return known ? t(known) : status.replaceAll("_", " ");
}

export function ToolCallCard({ call, label }: { call: Record<string, unknown>; label: string }) {
  const t = useTranslations("chat");
  const qualified = text(call.qualifiedName ?? call.qualified_name ?? "tool");
  const presentation = useMemo(() => presentationOf(call), [call]);
  const called = presentation.kind === "agents";
  const name = called ? t("calledAgents") : friendlyName(qualified, t);
  const failure = failureOf(call, presentation);
  const status = friendlyStatus(failure.status, t);
  const preview = text(call.resultPreview ?? call.result_preview ?? "");
  const approvalId = text(call.approvalId ?? call.approval_id ?? "");
  const waiting = text(call.status ?? "") === "awaiting_approval";
  const error = call.error;
  const connect =
    error && typeof error === "object"
      ? text(
          (error as { connectUrl?: string; connect_url?: string }).connectUrl ??
            (error as { connect_url?: string }).connect_url ??
            "",
        )
      : "";
  const needsAction = waiting || Boolean(connect);
  const [expanded, setExpanded] = useState(needsAction);
  const [query, setQuery] = useState("");
  const kind = text(presentation.kind);
  const argumentText =
    call.arguments && typeof call.arguments === "object" && Object.keys(call.arguments).length === 0
      ? ""
      : text(call.arguments);

  const files = filesOf(presentation);
  const hits = Array.isArray(presentation.results) ? (presentation.results as Hit[]) : [];
  const progress = progressOf(presentation);

  useEffect(() => {
    if (needsAction) setExpanded(true);
  }, [needsAction]);
  // Original offsets keep identical saved rows distinct when paging and filtering.
  const resultRows = useMemo(
    () =>
      resultValues(presentation, kind).map((value, offset) => ({
        value,
        key: `row-${offset}`,
      })),
    [presentation, kind],
  );
  const matchingRows = useMemo(
    () =>
      resultRows.filter(
        (row) =>
          !query.trim() ||
          text(row.value).toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
      ),
    [resultRows, query],
  );
  const pagination = usePagedRows(matchingRows, `${text(call.id)}::${qualified}::${query}`);
  const savedRewriteText =
    kind === "rewrite" &&
    resultRows.length === 0 &&
    (presentation.original != null || presentation.proposed != null);
  const pagedOutput = [
    "query",
    "table",
    "pivot",
    "sample",
    "judge",
    "check",
    "missing",
    "compare",
    "rewrite",
  ].includes(kind);

  return (
    // One line until a person opens it. It starts open only when it needs them: an approval
    // to give, or an account to connect.
    <details
      className="mt-1.5 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm"
      data-testid="tool-call"
      open={expanded}
      onToggle={(event) => setExpanded(event.currentTarget.open)}
    >
      <summary className="cursor-pointer select-none text-xs">
        <span className="sr-only">{label} </span>
        <span className="font-medium">{name}</span>
        <span aria-hidden="true" className="text-[var(--muted-foreground)]">
          {" · "}
        </span>
        <span className="text-[var(--muted-foreground)]">{status}</span>
        {failure.message ? (
          <span className="mt-1 block text-[var(--destructive)]">{failure.message}</span>
        ) : null}
      </summary>
      {expanded ? (
        <>
          <p className="mt-2 break-all text-xs text-[var(--muted-foreground)]">
            {t("toolIdentifier")}: {qualified}
          </p>
          {argumentText ? (
            <details className="mt-2">
              <summary className="cursor-pointer text-[var(--muted-foreground)]">
                {t("toolDetails")}
              </summary>
              <Block className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs">
                {argumentText}
              </Block>
            </details>
          ) : null}
          <ToolTimeline call={call} />
          {progress ? <JobMeter progress={progress} /> : null}
          {pagedOutput ? (
            <div className="mt-2 space-y-2">
              {resultRows.length > 0 ? (
                <Input
                  type="search"
                  aria-label={t("toolResultSearch")}
                  placeholder={t("toolResultSearch")}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              ) : null}
              {!matchingRows.length && !savedRewriteText ? (
                <p className="text-[var(--muted-foreground)]">
                  {t(query ? "toolNoResultMatches" : "toolNoResultRows")}
                </p>
              ) : null}
            </div>
          ) : null}
          {kind === "code" || kind === "shell" ? (
            <div className="mt-2 space-y-2">
              <Block className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--muted)] p-2 text-xs">
                {text(presentation.command)}
              </Block>
              <p>
                {t("exitCode")} {text(presentation.exitCode ?? presentation.exit_code)}
              </p>
              {text(presentation.stdout) ? (
                <Block className="overflow-x-auto whitespace-pre-wrap text-xs">
                  {text(presentation.stdout)}
                </Block>
              ) : null}
              {text(presentation.stderr) ? (
                <Block className="overflow-x-auto whitespace-pre-wrap text-xs text-[var(--destructive)]">
                  {text(presentation.stderr)}
                </Block>
              ) : null}
            </div>
          ) : null}
          {kind === "fetch" ? (
            <div className="mt-2">
              <p className="font-medium">{text(presentation.title)}</p>
              <p className="text-[var(--muted-foreground)]">{text(presentation.url)}</p>
              <p className="mt-1 max-h-80 overflow-auto whitespace-pre-wrap break-words">
                {text(presentation.snippet)}
              </p>
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
                <Block className="mt-1 overflow-x-auto whitespace-pre-wrap text-xs">
                  {text(presentation.snippet)}
                </Block>
              ) : null}
            </div>
          ) : null}
          {kind === "sample" ? <SampleFacts facts={presentation.sample} /> : null}
          {kind === "query" || kind === "table" || kind === "pivot" || kind === "sample" ? (
            <div className="mt-2 min-w-0 max-w-full">
              {text(presentation.sql) ? (
                <Block className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--muted)] p-2 text-xs">
                  {text(presentation.sql)}
                </Block>
              ) : null}
              <TableScroll label={t("toolResultTable")} className="mt-2 max-w-full">
                <table aria-label={t("toolResultTable")} className="w-full text-left text-xs">
                  <thead>
                    <tr>
                      {(Array.isArray(presentation.columns) ? presentation.columns : []).map(
                        (column) => (
                          <th className="border-b border-[var(--border)] pr-2" key={text(column)}>
                            {text(
                              typeof column === "object"
                                ? (column as { name?: string }).name
                                : column,
                            )}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {pagination.rows.map((row) => {
                      const cells = (Array.isArray(row.value) ? row.value : []).map(
                        (value, column) => ({ value, key: `cell-${column}` }),
                      );
                      return (
                        <tr key={row.key}>
                          {cells.map((cell) => (
                            <td className="border-b border-[var(--border)] pr-2" key={cell.key}>
                              {text(cell.value)}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </TableScroll>
            </div>
          ) : null}
          {kind === "summary" ||
          kind === "check" ||
          kind === "judge" ||
          kind === "gaps" ||
          kind === "missing" ? (
            <ul className="mt-2 space-y-2">
              {pagination.rows.map((item) => {
                const row =
                  item.value && typeof item.value === "object"
                    ? (item.value as Record<string, unknown>)
                    : {};
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
                  <li key={item.key} className="min-w-0 break-words">
                    <p>{label}</p>
                    {text(row.verdict) ? (
                      <p className="text-[var(--muted-foreground)]">
                        {text(row.verdict)} {text(row.confidence)}
                      </p>
                    ) : null}
                    {anchor ? (
                      <a
                        className="underline"
                        href={`/documents/${encodeURIComponent(documentId)}#${encodeURIComponent(anchor)}`}
                      >
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
          {kind === "compare" || kind === "rewrite" ? (
            <div className="mt-2 space-y-3">
              {kind === "rewrite" ? (
                <>
                  {text(presentation.instruction) ? (
                    <p className="whitespace-pre-wrap break-words">
                      {text(presentation.instruction)}
                    </p>
                  ) : null}
                  {text(presentation.status) ? (
                    <p className="text-[var(--muted-foreground)]">{text(presentation.status)}</p>
                  ) : null}
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {t("savedProposalReadOnly")}
                  </p>
                </>
              ) : null}
              {savedRewriteText ? (
                <SavedDiff before={presentation.original} after={presentation.proposed} />
              ) : null}
              <ul className="divide-y divide-[var(--border)]">
                {pagination.rows.map((item) => {
                  const row =
                    item.value && typeof item.value === "object"
                      ? (item.value as Record<string, unknown>)
                      : {};
                  return (
                    <li key={item.key} className="py-3 space-y-2">
                      <p className="break-words font-medium">
                        {[text(row.op), text(row.heading)].filter(Boolean).join(" · ")}
                      </p>
                      <SavedDiff before={row.before} after={row.after} />
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
          {kind === "crosscheck" ? <Crosscheck presentation={presentation} /> : null}
          {kind === "agents" ? <CalledAgents presentation={presentation} /> : null}
          {kind === "redact" ? (
            <Block className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs">
              {text(presentation.redacted)}
            </Block>
          ) : null}
          {pagedOutput && resultRows.length > 0 ? (
            <div className="mt-3">
              <ListPagination {...pagination} compact />
            </div>
          ) : null}
          {pagedOutput && presentation.truncated === true ? (
            <p className="mt-1 text-[var(--muted-foreground)]">{t("truncated")}</p>
          ) : null}
          {kind === "extract" ? (
            <ul className="mt-2 space-y-1">
              {(Array.isArray(presentation.fields) ? presentation.fields : []).map((item) => {
                const row =
                  item && typeof item === "object" ? (item as Record<string, unknown>) : {};
                return (
                  <li key={text(row.field)}>
                    {text(row.field)}: {row.value == null ? text(row.reason) : text(row.value)}
                  </li>
                );
              })}
            </ul>
          ) : null}
          {kind === "chart" ? (
            <p
              className="mt-2 text-xs text-[var(--muted-foreground)]"
              data-testid="chart-reference"
            >
              {text(presentation.title) || t("toolChart")}
              {files.map((file) => {
                const id = text(file.fileId ?? file.file_id);
                const name = text(file.name) || id;
                return id ? (
                  <a className="ml-2 underline" href={`/api/v1/files/${id}/content`} key={id}>
                    {name}
                  </a>
                ) : (
                  <span className="ml-2" key={name}>
                    {name}
                  </span>
                );
              })}
            </p>
          ) : null}
          {kind !== "chart" &&
            files
              .filter((file) => isImageName(text(file.name)))
              .map((file) => {
                const id = text(file.fileId ?? file.file_id);
                return id ? (
                  // biome-ignore lint/performance/noImgElement: authenticated same-origin file content must retain the browser session.
                  <img
                    alt={text(file.name) || text(presentation.title) || "image"}
                    className="mt-2 max-w-full rounded-lg border border-[var(--border)]"
                    key={id}
                    src={`/api/v1/files/${id}/content`}
                  />
                ) : null;
              })}
          {files.filter((file) => !isImageName(text(file.name))).length > 0 ? (
            <ul className="mt-2 space-y-1">
              {files
                .filter((file) => !isImageName(text(file.name)))
                .map((file) => {
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
          kind !== "pivot" &&
          kind !== "sample" &&
          kind !== "chart" &&
          kind !== "summary" &&
          kind !== "check" &&
          kind !== "judge" &&
          kind !== "gaps" &&
          kind !== "missing" &&
          kind !== "compare" &&
          kind !== "crosscheck" &&
          kind !== "agents" &&
          kind !== "rewrite" &&
          kind !== "redact" &&
          kind !== "extract" &&
          kind !== "document" &&
          preview ? (
            <p className="mt-1 max-h-80 overflow-auto whitespace-pre-wrap break-words">{preview}</p>
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
        </>
      ) : null}
    </details>
  );
}
