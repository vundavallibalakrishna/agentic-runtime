"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { api } from "@/lib/api";

export type CitationChip = {
  index: number;
  title: string;
  snippet: string;
  uri: string;
  documentId?: string;
  anchor?: string;
  page?: number | string;
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

export function reviewsOf(message: Record<string, unknown>): Record<string, unknown>[] {
  const content = message.content;
  if (!Array.isArray(content)) return [];
  for (const part of content) {
    if (!part || typeof part !== "object") continue;
    const row = part as { type?: string; rows?: unknown };
    if (row.type === "review" && Array.isArray(row.rows)) {
      return row.rows.filter((item) => item && typeof item === "object") as Record<
        string,
        unknown
      >[];
    }
  }
  return [];
}

export function ReviewTable({ rows }: { rows: Record<string, unknown>[] }) {
  const t = useTranslations("chat");
  if (rows.length === 0) return null;
  return (
    <div className="mt-3 overflow-x-auto rounded-xl border border-[var(--border)]">
      <table className="w-full text-left text-sm">
        <thead className="bg-[var(--muted)] text-xs text-[var(--muted-foreground)]">
          <tr>
            <th className="px-3 py-2 font-medium">{t("reviewItem")}</th>
            <th className="px-3 py-2 font-medium">{t("reviewStatus")}</th>
            <th className="px-3 py-2 font-medium">{t("reviewQuote")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const anchor = String(row.anchor || "");
            const documentId = String(row.documentId || row.document_id || "");
            const quote = String(row.quote || row.text || "");
            const status = String(row.status || row.verdict || "");
            const key = `${String(row.id || row.heading || "")}-${anchor}-${quote.slice(0, 24)}`;
            return (
              <tr className="border-t border-[var(--border)]" key={key}>
                <td className="px-3 py-2">{String(row.heading || row.text || row.id || "")}</td>
                <td className="px-3 py-2">
                  {status === "notFound" || status === "not_supported"
                    ? t("notFound")
                    : t("supported")}
                </td>
                <td className="px-3 py-2">
                  {documentId && anchor ? (
                    <a className="underline" href={`/documents/${documentId}#${anchor}`}>
                      {quote || anchor}
                    </a>
                  ) : (
                    quote
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function CitationList({
  citations,
  conversationId,
  messageId,
}: {
  citations: CitationChip[];
  conversationId?: string;
  messageId?: string;
}) {
  const t = useTranslations("chat");
  const [open, setOpen] = useState<CitationChip | null>(null);
  const [why, setWhy] = useState("");
  if (citations.length === 0) {
    return null;
  }
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {citations.map((citation) => {
        const verified = citation.verified === true || citation.status === "supported";
        return (
          <span className="group relative" key={`${citation.index}-${citation.title}`}>
            <Button
              className="h-7 px-2 text-xs font-normal"
              onClick={() => setOpen(citation)}
              type="button"
              variant="outline"
            >
              {t("citation", { index: citation.index, title: citation.title || t("source") })}
              {verified ? (
                <span className="ml-1 text-[var(--muted-foreground)]">{t("verified")}</span>
              ) : null}
            </Button>
            {citation.snippet ? (
              <span
                className="pointer-events-none absolute bottom-full left-0 z-10 mb-1 hidden w-64 rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 text-left text-xs leading-relaxed shadow-[var(--shadow-composer)] group-hover:block"
                role="tooltip"
              >
                {citation.snippet}
              </span>
            ) : null}
          </span>
        );
      })}
      {conversationId && messageId && !messageId.startsWith("local-") ? (
        <Button
          className="h-7 px-2 text-xs font-normal text-[var(--muted-foreground)]"
          onClick={() => {
            void api<Record<string, unknown>>(
              `/api/v1/conversations/${conversationId}/messages/${messageId}/grounding`,
            )
              .then((report) => setWhy(JSON.stringify(report.claims ?? report, null, 2)))
              .catch(() => setWhy(t("whyEmpty")));
          }}
          type="button"
          variant="ghost"
        >
          {t("why")}
        </Button>
      ) : null}
      {open ? (
        <Dialog
          open={!!open}
          onOpenChange={(next) => {
            if (!next) setOpen(null);
          }}
        >
          <DialogContent title={open.title || t("source")}>
            {open.anchor ? (
              <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                {open.page ? `p.${open.page} ` : ""}
                {open.anchor}
              </p>
            ) : null}
            <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{open.snippet}</p>
            {open.documentId ? (
              <a
                className="mt-2 inline-block text-sm underline"
                href={`/documents/${open.documentId}${open.anchor ? `#${open.anchor}` : ""}`}
              >
                {open.title || t("source")}
              </a>
            ) : null}
            {open.uri ? (
              <p className="mt-2 break-all text-xs text-[var(--muted-foreground)]">{open.uri}</p>
            ) : null}
            <Button className="mt-4" onClick={() => setOpen(null)} type="button" variant="outline">
              {t("closePreview")}
            </Button>
          </DialogContent>
        </Dialog>
      ) : null}
      {why ? (
        <pre className="mt-2 w-full overflow-auto rounded-lg bg-[var(--muted)] p-3 text-xs">
          {why}
        </pre>
      ) : null}
    </div>
  );
}
