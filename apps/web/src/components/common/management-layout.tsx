import { Inbox, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { ErrorMessage } from "@/components/common/detail-state";
import { Button } from "@/components/ui/button";
import type { DisplayError } from "@/lib/api";

export function ManagementLayout({
  children,
  title,
  formTitle,
  form,
}: {
  children: ReactNode;
  title?: string;
  formTitle: string;
  form: ReactNode;
}) {
  return (
    <div
      className={`grid items-start gap-8 ${form == null ? "" : "xl:grid-cols-[minmax(0,1fr)_20rem]"}`}
    >
      <section className="min-w-0">
        {title ? <h2 className="mb-4 text-sm font-semibold">{title}</h2> : null}
        {children}
      </section>
      {form == null ? null : (
        <aside className="management-form min-w-0 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
          <h2 className="mb-5 text-base font-semibold">{formTitle}</h2>
          {form}
        </aside>
      )}
    </div>
  );
}

export function ErrorState({
  message,
  retryLabel,
  onRetry,
}: {
  message: DisplayError;
  retryLabel: string;
  onRetry: () => void;
}) {
  return (
    <div
      role="alert"
      className="mb-6 flex min-h-48 flex-col items-center justify-center rounded-xl border border-[var(--destructive)]/40 bg-[var(--destructive)]/5 px-6 py-10 text-center"
    >
      <div className="mb-4 rounded-xl bg-[var(--destructive)]/10 p-3 text-[var(--destructive)]">
        <TriangleAlert size={20} aria-hidden="true" />
      </div>
      <div className="max-w-sm text-sm leading-relaxed text-[var(--foreground)]">
        <ErrorMessage error={message} />
      </div>
      <Button className="mt-4" variant="outline" onClick={onRetry} type="button">
        {retryLabel}
      </Button>
    </div>
  );
}

export function EmptyState({
  title,
  children,
  compact = false,
}: {
  title: string;
  children?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div
      className={`mb-6 rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)] ${compact ? "px-4 py-5" : "flex min-h-48 flex-col items-center justify-center px-6 py-10 text-center"}`}
    >
      {!compact ? (
        <div className="mb-4 rounded-xl bg-[var(--muted)] p-3 text-[var(--muted-foreground)]">
          <Inbox size={20} aria-hidden="true" />
        </div>
      ) : null}
      <p className="max-w-sm text-sm leading-relaxed text-[var(--muted-foreground)]">{title}</p>
      {children ? <div className="mt-4">{children}</div> : null}
    </div>
  );
}
