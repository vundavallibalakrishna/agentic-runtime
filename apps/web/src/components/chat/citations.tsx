"use client";

import { useTranslations } from "next-intl";
import { type ComponentProps, useMemo, useState } from "react";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableScroll,
} from "@/components/ui/table";
import { formatDataValue } from "@/lib/format";

import { CitationDetails } from "./citation-details";

export type CitationChip = {
  index: number;
  title: string;
  snippet: string;
  uri: string;
  documentId?: string;
  anchor?: string;
  page?: number | string;
  pageFrom?: number;
  pageTo?: number;
  charFrom?: number;
  charTo?: number;
  verified?: boolean;
  status?: string;
};

export function citationsOf(message: Record<string, unknown>): CitationChip[] {
  const content = message.content;
  if (!Array.isArray(content)) {
    return [];
  }
  const chips: CitationChip[] = [];
  for (const part of content) {
    if (!part || typeof part !== "object") {
      continue;
    }
    const row = part as { type?: string; citation?: CitationChip; index?: number };
    if (row.type === "citation_ref" && row.citation) {
      chips.push({ ...row.citation, index: row.citation.index ?? row.index ?? chips.length + 1 });
    }
  }
  return chips;
}

export function readingOf(message: Record<string, unknown>): Record<string, unknown> | null {
  const content = message.content;
  if (!Array.isArray(content)) return null;
  for (const part of content) {
    if (!part || typeof part !== "object") continue;
    const row = part as { type?: string };
    if (row.type === "reading") return row as Record<string, unknown>;
  }
  return null;
}

export function ReadingNote({ reading }: { reading: Record<string, unknown> | null }) {
  const t = useTranslations("chat");
  const tools = [
    ...new Set(
      Array.isArray(reading?.tools)
        ? reading.tools.filter(
            (value): value is string => typeof value === "string" && Boolean(value.trim()),
          )
        : [],
    ),
  ];
  const pagination = usePagedRows(tools);
  const scalar = (value: unknown) =>
    typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
  const strategy = scalar(reading?.strategy);
  const coverage = scalar(reading?.coverage);
  const scope = scalar(reading?.scope);
  const context = [
    strategy ? t("readingStrategy", { value: strategy }) : "",
    coverage ? t("readingCoverage", { value: coverage }) : "",
    scope ? t("readingScope", { value: scope }) : "",
  ].filter(Boolean);
  if (!reading || (!tools.length && !context.length)) return null;
  return (
    <div className="mt-2 text-xs text-[var(--muted-foreground)]">
      {context.length ? <p>{context.join(" · ")}</p> : null}
      {tools.length ? (
        <details className="mt-1">
          <summary className="cursor-pointer">
            {t("toolsUsedCount", { count: tools.length })}
          </summary>
          <ul className="mt-2 space-y-1">
            {pagination.rows.map((tool) => (
              <li className="break-all" key={tool}>
                {tool}
              </li>
            ))}
          </ul>
          {tools.length > pagination.pageSize ? (
            <div className="mt-3">
              <ListPagination {...pagination} compact />
            </div>
          ) : null}
        </details>
      ) : null}
    </div>
  );
}

export function reviewsOf(message: Record<string, unknown>): Record<string, unknown>[] {
  const content = message.content;
  if (!Array.isArray(content)) return [];
  for (const part of content) {
    if (!part || typeof part !== "object") continue;
    const row = part as { type?: string; rows?: unknown };
    if (row.type === "review" && Array.isArray(row.rows)) {
      return row.rows.filter(
        (item) => item && typeof item === "object" && !Array.isArray(item),
      ) as Record<string, unknown>[];
    }
  }
  return [];
}

export function ReviewTable({ rows }: { rows: Record<string, unknown>[] }) {
  const t = useTranslations("chat");
  const [open, setOpen] = useState(false);
  if (rows.length === 0) return null;
  return (
    <details
      className="mt-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cursor-pointer text-sm font-medium">
        {t("reviewRowsSummary", { count: rows.length })}
      </summary>
      {open ? <ReviewRows rows={rows} /> : null}
    </details>
  );
}

function ReviewRows({ rows }: { rows: Record<string, unknown>[] }) {
  const t = useTranslations("chat");
  const [query, setQuery] = useState("");
  const columns = useMemo(() => [...new Set(rows.flatMap((row) => Object.keys(row)))], [rows]);
  const columnPage = usePagedRows(columns);
  const matching = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return rows.flatMap((row, offset) =>
      !needle ||
      Object.values(row).some((value) =>
        formatDataValue(value).toLocaleLowerCase().includes(needle),
      )
        ? [{ row, offset }]
        : [],
    );
  }, [rows, query]);
  const pagination = usePagedRows(matching, query);
  return (
    <div className="mt-4 space-y-3">
      <p className="text-xs text-[var(--muted-foreground)]">{t("reviewRowsHelp")}</p>
      <Input
        type="search"
        aria-label={t("reviewRowsSearch")}
        placeholder={t("reviewRowsSearch")}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {!matching.length ? (
        <p role="status" className="text-sm">
          {t("reviewRowsNoMatches")}
        </p>
      ) : null}
      {columns.length > columnPage.pageSize ? (
        <div className="space-y-2 rounded-lg bg-[var(--muted)] p-3">
          <p className="text-xs font-medium">{t("reviewColumns")}</p>
          <ListPagination {...columnPage} compact label={t("reviewColumns")} />
        </div>
      ) : null}
      {matching.length > 0 && columns.length > 0 ? (
        <TableScroll
          label={t("reviewRowsTitle")}
          className="max-h-96 rounded-lg border border-[var(--border)]"
        >
          <Table aria-label={t("reviewRowsTitle")}>
            <TableHeader>
              <TableRow>
                {columnPage.rows.map((column) => (
                  <TableHead scope="col" className="min-w-32 max-w-96 break-words" key={column}>
                    {column}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagination.rows.map(({ row, offset }) => (
                <TableRow key={offset}>
                  {columnPage.rows.map((column) => (
                    <TableCell key={column} className="min-w-32 max-w-96 align-top">
                      <ReviewCell value={row[column]} />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableScroll>
      ) : null}
      {columns.length === 0 ? <p className="text-sm">{t("reviewRowsNoFields")}</p> : null}
      <ListPagination {...pagination} label={t("reviewRowsTitle")} />
    </div>
  );
}

function ReviewCell({ value }: { value: unknown }) {
  const t = useTranslations("chat");
  const [open, setOpen] = useState(false);
  const text = formatDataValue(value);
  return text.length > 240 ? (
    <details open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="cursor-pointer whitespace-pre-wrap break-words">
        {text.slice(0, 240)}…{" "}
        <span className="text-xs text-[var(--muted-foreground)]">{t("reviewCellExpand")}</span>
      </summary>
      {open ? (
        <TableScroll label={t("reviewCellValue")} className="mt-2 max-h-64">
          <pre className="whitespace-pre-wrap break-words text-xs">{text}</pre>
        </TableScroll>
      ) : null}
    </details>
  ) : (
    <span className="whitespace-pre-wrap break-words">{text}</span>
  );
}

export function CitationList(props: ComponentProps<typeof CitationDetails>) {
  return (
    <CitationDetails key={`${props.conversationId ?? ""}:${props.messageId ?? ""}`} {...props} />
  );
}
