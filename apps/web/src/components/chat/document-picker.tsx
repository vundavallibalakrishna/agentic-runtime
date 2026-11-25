"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import type { Attached } from "@/components/chat/attachment-list";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Row = Record<string, unknown>;

function asAttached(item: Row): Attached {
  return {
    id: String(item.fileId || item.file_id || ""),
    name: String(item.title || item.filename || "document"),
    mimeType: String(item.mediaType || item.media_type || "text/plain"),
    stored: true,
  };
}

/**
 * Choose library documents to send with a message. It opens from the Documents button
 * and when "@" is typed in the message box. A chosen document goes on the message as
 * its file id, the same as an attachment.
 */
export function DocumentPicker({
  chosen,
  onToggle,
  onClose,
}: {
  chosen: string[];
  onToggle: (document: Attached) => void;
  onClose: () => void;
}) {
  const t = useTranslations("chat");
  const [documents, setDocuments] = useState<Attached[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const search = useRef<HTMLInputElement>(null);

  useEffect(() => {
    search.current?.focus();
    let cancelled = false;
    api<{ items?: Row[] }>("/api/v1/library-documents")
      .then((page) => {
        if (!cancelled) setDocuments((page.items ?? []).map(asAttached).filter((item) => item.id));
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : t("error"));
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  const shown = useMemo(() => {
    const words = query.trim().toLowerCase();
    const all = documents ?? [];
    return words ? all.filter((item) => item.name.toLowerCase().includes(words)) : all;
  }, [documents, query]);
  const current = shown[Math.min(active, Math.max(shown.length - 1, 0))];

  function onKey(event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((at) => Math.min(at + 1, Math.max(shown.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((at) => Math.max(at - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      // Enter in the search box takes the highlighted document. On a checkbox it does
      // what Space does.
      if (current && event.currentTarget === search.current) onToggle(current);
      else if (event.currentTarget instanceof HTMLInputElement) event.currentTarget.click();
    }
  }

  return (
    <section
      aria-label={t("pickerTitle")}
      className="mx-auto mb-2 max-w-3xl rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 text-sm shadow-[var(--shadow-xs)]"
      data-testid="document-picker"
    >
      <div className="flex items-end gap-2">
        <label className="min-w-0 flex-1" htmlFor="document-search">
          {t("pickerSearch")}
          <Input
            className="mt-1"
            id="document-search"
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={onKey}
            ref={search}
            type="search"
            value={query}
          />
        </label>
        <Button onClick={onClose} type="button" variant="outline">
          {t("pickerDone")}
        </Button>
      </div>
      {error ? <p role="alert">{error}</p> : null}
      {documents === null && !error ? (
        <p className="mt-3 text-[var(--muted-foreground)]" role="status">
          {t("pickerLoading")}
        </p>
      ) : null}
      {documents !== null && shown.length === 0 ? (
        <p className="mt-3 text-[var(--muted-foreground)]">
          {documents.length === 0 ? t("pickerEmpty") : t("pickerNoMatch")}
        </p>
      ) : null}
      <ul className="mt-2 max-h-56 overflow-y-auto">
        {shown.map((item) => (
          <li key={item.id}>
            <label
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2",
                item.id === current?.id ? "bg-[var(--muted)]" : "",
              )}
            >
              <input
                checked={chosen.includes(item.id)}
                onChange={() => onToggle(item)}
                onKeyDown={onKey}
                type="checkbox"
              />
              <span className="min-w-0 break-words">{item.name}</span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Whether the text just typed is an "@" that starts a word, which opens the picker. */
export function mentionStarted(before: string, after: string, caret: number): boolean {
  if (after.length !== before.length + 1 || after[caret - 1] !== "@") return false;
  const previous = after[caret - 2];
  return previous === undefined || /\s/.test(previous);
}
