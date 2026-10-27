import type { ComponentPropsWithRef } from "react";

import { cn } from "@/lib/utils";

export function Input({ className, ...props }: ComponentPropsWithRef<"input">) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)]",
        className,
      )}
      {...props}
    />
  );
}
