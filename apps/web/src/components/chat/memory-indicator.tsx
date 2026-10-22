"use client";

import { useTranslations } from "next-intl";

import type { StreamMemory } from "@/lib/stream/reducer";

type Props = {
  memories: StreamMemory[];
  recalled: number;
  compacted: boolean;
  onUndo: (factId: string) => void;
};

export function MemoryIndicator({ memories, recalled, compacted, onUndo }: Props) {
  const t = useTranslations("chat");
  if (memories.length === 0 && recalled === 0 && !compacted) {
    return null;
  }
  return (
    <div className="mt-2 space-y-1 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm">
      {memories.map((memory) => (
        <p className="flex flex-wrap items-center gap-2" key={memory.factId} role="status">
          <span>{t("memorySaved", { content: memory.content })}</span>
          <button className="underline" onClick={() => onUndo(memory.factId)} type="button">
            {t("memoryUndo")}
          </button>
        </p>
      ))}
      {recalled > 0 ? <p role="status">{t("memoryRecalled", { count: recalled })}</p> : null}
      {compacted ? <p role="status">{t("memoryCompacted")}</p> : null}
    </div>
  );
}
