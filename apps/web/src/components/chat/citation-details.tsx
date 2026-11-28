"use client";

import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { TableScroll } from "@/components/ui/table";
import type { CitationChip } from "./citations";
import { GroundingDetails } from "./grounding-details";

export function CitationDetails({
  citations,
  conversationId,
  messageId,
}: {
  citations: CitationChip[];
  conversationId?: string;
  messageId?: string;
}) {
  const t = useTranslations("chat");
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [whyOpen, setWhyOpen] = useState(false);
  const saved = Boolean(conversationId && messageId && !messageId.startsWith("local-"));
  if (!citations.length && !saved) return null;
  return (
    <div className="flex flex-wrap items-center gap-1">
      {citations.length ? (
        <Dialog open={sourcesOpen} onOpenChange={setSourcesOpen}>
          <DialogTrigger>
            <Button type="button" variant="ghost" className="max-w-full text-xs">
              {t("sourcesSummary", { count: citations.length })}
            </Button>
          </DialogTrigger>
          {sourcesOpen ? (
            <DialogContent title={t("sourcesTitle")}>
              <SourceBrowser citations={citations} />
              <Button
                type="button"
                variant="outline"
                className="mt-4"
                onClick={() => setSourcesOpen(false)}
              >
                {t("closePreview")}
              </Button>
            </DialogContent>
          ) : null}
        </Dialog>
      ) : null}
      {saved ? (
        <Dialog open={whyOpen} onOpenChange={setWhyOpen}>
          <DialogTrigger>
            <Button type="button" variant="ghost" className="text-xs">
              {t("why")}
            </Button>
          </DialogTrigger>
          {whyOpen && conversationId && messageId ? (
            <DialogContent title={t("whyTitle")}>
              <GroundingDetails conversationId={conversationId} messageId={messageId} />
              <Button
                type="button"
                variant="outline"
                className="mt-4"
                onClick={() => setWhyOpen(false)}
              >
                {t("closePreview")}
              </Button>
            </DialogContent>
          ) : null}
        </Dialog>
      ) : null}
    </div>
  );
}
function verified(citation: CitationChip) {
  return citation.verified === true || citation.status === "supported";
}
function SourceBrowser({ citations }: { citations: CitationChip[] }) {
  const t = useTranslations("chat");
  const [query, setQuery] = useState("");
  const [onlyVerified, setOnlyVerified] = useState(false);
  const [selectedOffset, setSelectedOffset] = useState<number | null>(null);
  const selected = selectedOffset == null ? null : citations[selectedOffset];
  const matching = useMemo(
    () =>
      citations.flatMap((citation, offset) => {
        const needle = query.trim().toLocaleLowerCase();
        return (!onlyVerified || verified(citation)) &&
          [
            citation.title,
            citation.snippet,
            citation.uri,
            citation.anchor,
            String(citation.index),
          ].some((value) => value?.toLocaleLowerCase().includes(needle))
          ? [{ citation, offset }]
          : [];
      }),
    [citations, query, onlyVerified],
  );
  const pagination = usePagedRows(matching, `${query}:${onlyVerified}`);
  const page = selected?.page ?? selected?.pageFrom;
  return selected ? (
    <div className="mt-4 space-y-3">
      <Button type="button" variant="outline" onClick={() => setSelectedOffset(null)}>
        {t("backToSources")}
      </Button>
      <h2 className="break-words text-sm font-semibold">{selected.title || t("source")}</h2>
      {verified(selected) ? <Badge>{t("verified")}</Badge> : null}
      {page != null ? (
        <p className="break-words text-xs text-[var(--muted-foreground)]">
          {t("sourcePage", {
            page: String(page),
            end: selected.pageTo != null && selected.pageTo !== page ? `–${selected.pageTo}` : "",
          })}
        </p>
      ) : null}
      {selected.anchor ? <p className="break-words text-xs">{selected.anchor}</p> : null}
      {selected.snippet ? (
        <TableScroll label={t("sourcePassage")} className="max-h-64">
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
            {selected.snippet}
          </p>
        </TableScroll>
      ) : (
        <p className="text-sm text-[var(--muted-foreground)]">{t("sourceNoPassage")}</p>
      )}
      {selected.documentId ? (
        <a
          className="inline-block break-words text-sm underline"
          href={`/documents/${encodeURIComponent(selected.documentId)}${selected.anchor ? `#${encodeURIComponent(selected.anchor)}` : ""}`}
        >
          {t("openSourceDocument")}
        </a>
      ) : null}
      {selected.uri ? (
        <p className="break-all text-xs text-[var(--muted-foreground)]">{selected.uri}</p>
      ) : null}
    </div>
  ) : (
    <div className="mt-4 space-y-3">
      <Input
        type="search"
        aria-label={t("sourceSearch")}
        placeholder={t("sourceSearch")}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={onlyVerified}
          onChange={(event) => setOnlyVerified(event.target.checked)}
        />
        {t("sourcesVerifiedOnly")}
      </label>
      {!matching.length ? (
        <p role="status" className="text-sm">
          {t("sourcesNoMatches")}
        </p>
      ) : null}
      <ul className="divide-y divide-[var(--border)]">
        {pagination.rows.map(({ citation, offset }) => (
          <li key={offset} className="py-2">
            <Button
              type="button"
              variant="ghost"
              className="h-auto w-full min-w-0 justify-start whitespace-normal break-words text-left text-sm"
              onClick={() => setSelectedOffset(offset)}
            >
              {t("citation", { index: citation.index, title: citation.title || t("source") })}
            </Button>
            {verified(citation) ? (
              <p className="px-3 text-xs text-[var(--muted-foreground)]">{t("verified")}</p>
            ) : null}
          </li>
        ))}
      </ul>
      <ListPagination {...pagination} label={t("sourcesTitle")} />
    </div>
  );
}
