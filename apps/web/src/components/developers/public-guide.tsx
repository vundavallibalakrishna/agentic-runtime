"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { NotesView } from "@/components/developers/notes-view";

/** The same notes for someone with no sign-in. Nothing about a workspace is on this page. */
export function PublicGuide() {
  const t = useTranslations("developers");
  const [origin, setOrigin] = useState("<BASE_URL>");
  useEffect(() => setOrigin(window.location.origin), []);
  return (
    <main className="mx-auto min-h-dvh max-w-6xl bg-[var(--background)] px-4 py-10 text-[var(--foreground)]">
      <header className="mb-8 border-b border-[var(--border)] pb-6">
        <h1 className="text-2xl font-semibold tracking-tight">{t("notesTitle")}</h1>
        <p className="mt-2 text-sm text-[var(--muted-foreground)]">{t("publicBody")}</p>
      </header>
      <NotesView agentSlug="<agent-slug>" baseUrl={origin} />
    </main>
  );
}
