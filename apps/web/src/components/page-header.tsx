import type { ReactNode } from "react";

export function PageHeader({
  title,
  body,
  actions,
}: {
  title: string;
  body: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-[var(--muted-foreground)]">
          {body}
        </p>
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2 sm:pt-1">{actions}</div>
      ) : null}
    </header>
  );
}
