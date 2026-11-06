import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return <table className={cn("w-full text-sm", className)} {...props} />;
}

export function TableHeader({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn("text-left text-[var(--muted-foreground)]", className)} {...props} />;
}

export function TableBody(props: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody {...props} />;
}

export function TableRow(props: HTMLAttributes<HTMLTableRowElement>) {
  return <tr {...props} />;
}

export function TableHead({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={cn("px-2 py-1 font-medium", className)} {...props} />;
}

export function TableCell({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("px-2 py-1", className)} {...props} />;
}

/**
 * The frame around a table that may be wider than its space. It scrolls sideways, and a
 * region that scrolls must be reachable by keyboard and have a name, or a keyboard user
 * cannot see the columns that are off screen.
 */
export function TableScroll({
  label,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement> & { label: string }) {
  return (
    <section
      aria-label={label}
      className={cn("overflow-x-auto", className)}
      // biome-ignore lint/a11y/noNoninteractiveTabindex: a scrollable region needs keyboard focus
      tabIndex={0}
      {...props}
    />
  );
}
