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
      {citations.map((citation) => (
        <Button
          className="h-7 px-2 text-xs font-normal"
          key={`${citation.index}-${citation.title}`}
          onClick={() => setOpen(citation)}
          type="button"
          variant="outline"
        >
          {t("citation", { index: citation.index, title: citation.title || t("source") })}
        </Button>
      ))}
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
            <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{open.snippet}</p>
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
