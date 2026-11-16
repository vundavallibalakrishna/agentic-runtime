import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type Fact = { label: string; value: ReactNode };

/** The facts about one record: a label column and a value column. A fact with no value is left out. */
export function Facts({
  items,
  align = "start",
  className,
}: {
  items: Fact[];
  align?: "start" | "end";
  className?: string;
}) {
  const shown = items.filter(
    (item) => item.value !== null && item.value !== undefined && item.value !== "",
  );
  return (
    <dl className={cn("grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-2.5 text-sm", className)}>
      {shown.map((item) => (
        <div className="contents" key={item.label}>
          <dt className="text-[var(--muted-foreground)]">{item.label}</dt>
          <dd className={cn("m-0 min-w-0 break-words", align === "end" ? "text-right" : "")}>
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
