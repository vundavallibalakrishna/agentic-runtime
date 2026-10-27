import { Inbox } from "lucide-react";
import type { ReactNode } from "react";

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
    <div className="grid items-start gap-8 xl:grid-cols-[minmax(0,1fr)_20rem]">
      <section className="min-w-0">
        {title ? <h2 className="mb-4 text-sm font-semibold">{title}</h2> : null}
        {children}
      </section>
      <aside className="management-form min-w-0 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 className="mb-5 text-base font-semibold">{formTitle}</h2>
        {form}
      </aside>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-6 flex min-h-48 flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)] px-6 py-10 text-center">
      <div className="mb-4 rounded-xl bg-[var(--muted)] p-3 text-[var(--muted-foreground)]">
        <Inbox size={20} aria-hidden="true" />
      </div>
      <p className="max-w-sm text-sm leading-relaxed text-[var(--muted-foreground)]">{title}</p>
      {children ? <div className="mt-4">{children}</div> : null}
    </div>
  );
}
