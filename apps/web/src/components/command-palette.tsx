"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useMemo, useState } from "react";

export type PaletteCommand = {
  id: string;
  label: string;
  hint?: string;
  run: () => void;
};

export function CommandPalette({ commands }: { commands: PaletteCommand[] }) {
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
        window.dispatchEvent(new Event("ar-new-chat"));
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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
          className="hidden items-center gap-2 rounded-md px-2 py-1.5 text-[13px] text-[var(--muted-foreground)] hover:bg-[var(--muted)] md:inline-flex"
          type="button"
        >
          Search
          <kbd className="rounded bg-[var(--muted)] px-1.5 text-xs">⌘K</kbd>
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-[var(--scrim)]" />
        <Dialog.Content className="fixed left-1/2 top-[12vh] w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--card)] p-3 shadow-[var(--shadow)]">
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Dialog.Description className="sr-only">
            Jump to a page or start a new chat.
          </Dialog.Description>
          <input
            aria-label="Command"
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Jump to…"
            value={query}
          />
          <ul className="mt-2 max-h-80 overflow-auto">
            {visible.length === 0 ? (
              <li className="px-2 py-3 text-sm text-[var(--muted-foreground)]">No matches.</li>
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
