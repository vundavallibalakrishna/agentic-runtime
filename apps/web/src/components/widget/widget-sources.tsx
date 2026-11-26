"use client";

import { ExternalLink } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import { citationsOf } from "@/components/chat/citations";

/** A web address a visitor can open. Anything else (a stored file, an internal id) is not. */
function openable(uri: string): string {
  try {
    const url = new URL(uri);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
  } catch {
    return "";
  }
}

type Source = { numbers: number[]; title: string; href: string };

/** One line per page or document, with every number the answer gave it, in order. */
function grouped(message: Record<string, unknown>): Source[] {
  const found = new Map<string, Source>();
  for (const cited of citationsOf(message)) {
    const href = openable(cited.uri || "");
    const title = cited.title || href;
    const key = href || `title:${title}`;
    const known = found.get(key);
    if (known) {
      if (!known.numbers.includes(cited.index)) known.numbers.push(cited.index);
    } else found.set(key, { numbers: [cited.index], title, href });
  }
  return [...found.values()];
}

/**
 * The sources an answer cites, shown when the visitor asks for them: the answer carries
 * its numbers, and a button under it opens the list. Numbered as the answer numbers them. Two passages from one
 * page are one line with both numbers. A page on the web is a link that opens in a new
 * tab, outside the chat frame; any other source is named only, since a visitor cannot
 * open the workspace's documents.
 */
export function WidgetSources({ message }: { message: Record<string, unknown> }) {
  const t = useTranslations("widget");
  const [open, setOpen] = useState(false);
  const list = useId();
  const sources = grouped(message);
  if (sources.length === 0) return null;
  return (
    <section aria-label={t("sources")} className="mt-2">
      <button
        aria-controls={list}
        aria-expanded={open}
        className="text-xs text-muted-foreground underline underline-offset-2"
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        {t(open ? "hideSources" : "showSources", { count: sources.length })}
      </button>
      {open ? (
        <ol className="mt-1 space-y-1 text-sm" id={list}>
          {sources.map((source) => (
            <li className="flex gap-2" key={source.href || source.title}>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                [{source.numbers.join(", ")}]
              </span>
              {source.href ? (
                <a
                  className="min-w-0 break-words underline underline-offset-2"
                  href={source.href}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  {source.title || t("source")}
                  <ExternalLink
                    aria-hidden="true"
                    className="ml-1 inline-block align-[-1px]"
                    size={12}
                  />
                  <span className="sr-only">{t("opensNewTab")}</span>
                </a>
              ) : (
                <span className="min-w-0 break-words">{source.title || t("source")}</span>
              )}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
