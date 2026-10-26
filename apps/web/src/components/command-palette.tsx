"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

export type PaletteCommand = {
  id: string;
  label: string;
  hint?: string;
  run: () => void;
};

export function CommandPalette({ commands }: { commands: PaletteCommand[] }) {
  const t = useTranslations("shell");
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const meta = event.metaKey || event.ctrlKey;
      if (meta && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      }
      if (meta && event.shiftKey && event.key.toLowerCase() === "o") {
        event.preventDefault();
        commands.find((command) => command.id === "new-chat")?.run();
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [commands]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return commands;
    }
    return commands.filter((command) => command.label.toLowerCase().includes(needle));
  }, [commands, query]);

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setQuery("");
        }
      }}
    >
      <Dialog.Trigger asChild>
        <button
          aria-label={`${t("search")} ⌘K`}
          className="flex items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2.5 py-2 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
          type="button"
        >
          <Search size={14} aria-hidden="true" />
          <span className="hidden md:inline">{t("search")}</span>
          <kbd className="hidden rounded border border-[var(--border)] bg-[var(--card)] px-1 text-[10px] md:inline">
            ⌘K
          </kbd>
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[var(--scrim)]" />
        <Dialog.Content className="fixed z-50 left-1/2 top-[12vh] w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--card)] p-3 shadow-[var(--shadow)]">
          <Dialog.Title className="sr-only">{t("paletteTitle")}</Dialog.Title>
          <Dialog.Description className="sr-only">{t("paletteDescription")}</Dialog.Description>
          <input
            aria-label={t("command")}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("jumpTo")}
            value={query}
          />
          <ul className="mt-2 max-h-80 overflow-auto">
            {visible.length === 0 ? (
              <li className="px-2 py-3 text-sm text-[var(--muted-foreground)]">{t("noMatches")}</li>
            ) : null}
            {visible.map((command) => (
              <li key={command.id}>
                <button
                  className="flex w-full items-center justify-between rounded-lg px-2 py-2 text-left text-sm hover:bg-[var(--muted)]"
                  onClick={() => {
                    setOpen(false);
                    command.run();
                  }}
                  type="button"
                >
                  <span>{command.label}</span>
                  {command.hint ? (
                    <span className="text-xs text-[var(--muted-foreground)]">{command.hint}</span>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
