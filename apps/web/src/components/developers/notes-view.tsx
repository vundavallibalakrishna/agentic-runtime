"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { MarkdownView } from "@/components/chat/markdown-view";
import { Input } from "@/components/ui/input";
import notes from "@/generated/developer-notes.json";
import { cn } from "@/lib/utils";

type Note = { slug: string; title: string; body: string };

const NOTES = notes as Note[];

/** The notes with the workspace's own address and agent in the samples. Never a key. */
export function filled(body: string, values: { baseUrl: string; agentSlug: string }): string {
  return body
    .replaceAll("{{BASE_URL}}", values.baseUrl)
    .replaceAll("{{AGENT_SLUG}}", values.agentSlug);
}

/** Every note as one Markdown file, to hand to someone who has no sign-in here. */
export function wholeGuide(values: { baseUrl: string; agentSlug: string }): string {
  return NOTES.map((note) => filled(note.body, values).replace(/\]\(\?note=[^)]*\)/g, "]")).join(
    "\n\n---\n\n",
  );
}

export function NotesView({ baseUrl, agentSlug }: { baseUrl: string; agentSlug: string }) {
  const t = useTranslations("developers");
  const [slug, setSlug] = useState(NOTES[0]?.slug ?? "");
  const [query, setQuery] = useState("");

  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get("note");
    if (wanted && NOTES.some((note) => note.slug === wanted)) setSlug(wanted);
  }, []);

  const shown = useMemo(() => {
    const words = query.trim().toLowerCase();
    return words
      ? NOTES.filter((note) => `${note.title}\n${note.body}`.toLowerCase().includes(words))
      : NOTES;
  }, [query]);
  const current = NOTES.find((note) => note.slug === slug) ?? NOTES[0];

  function open(next: string) {
    setSlug(next);
    const params = new URLSearchParams(window.location.search);
    params.set("note", next);
    window.history.replaceState(null, "", `${window.location.pathname}?${params}`);
  }

  return (
    <div className="grid items-start gap-8 lg:grid-cols-[16rem_minmax(0,1fr)]">
      <nav aria-label={t("notesList")} className="min-w-0">
        <label className="block text-sm" htmlFor="notes-search">
          {t("search")}
          <Input
            className="mt-1"
            id="notes-search"
            onChange={(event) => setQuery(event.target.value)}
            type="search"
            value={query}
          />
        </label>
        {shown.length === 0 ? (
          <p className="mt-4 text-sm text-[var(--muted-foreground)]">{t("noMatch")}</p>
        ) : (
          <ul className="mt-4 space-y-1">
            {shown.map((note) => (
              <li key={note.slug}>
                <button
                  aria-current={note.slug === current?.slug ? "page" : undefined}
                  className={cn(
                    "w-full rounded-lg px-3 py-2 text-left text-sm",
                    note.slug === current?.slug
                      ? "bg-[var(--muted)] font-medium"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
                  )}
                  onClick={() => open(note.slug)}
                  type="button"
                >
                  {note.title}
                </button>
              </li>
            ))}
          </ul>
        )}
      </nav>
      <article className="min-w-0" data-testid="note">
        {current ? <MarkdownView text={filled(current.body, { baseUrl, agentSlug })} /> : null}
      </article>
    </div>
  );
}
