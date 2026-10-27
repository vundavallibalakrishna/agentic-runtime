"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function BackButton({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Button asChild variant="outline">
      <Link href={href}>{children}</Link>
    </Button>
  );
}

export function DetailState({
  loading,
  error,
  onRetry,
}: {
  loading: boolean;
  error: string;
  onRetry?: () => void;
}) {
  const t = useTranslations("detail");
  return (
    <>
      {error ? (
        <div
          className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 text-sm"
          role="alert"
        >
          <p className="min-w-0 break-words">{error}</p>
          {onRetry ? (
            <Button variant="outline" disabled={loading} onClick={onRetry}>
              {t("retry")}
            </Button>
          ) : null}
        </div>
      ) : null}
      {loading ? (
        <div aria-busy="true" className="space-y-4" role="status">
          <span className="sr-only">{t("loading")}</span>
          <Skeleton className="h-12 w-2/3" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : null}
    </>
  );
}

export function ActionStatus({ busy, notice }: { busy: boolean; notice?: string }) {
  const t = useTranslations("detail");
  return (
    <p
      role="status"
      className={busy || notice ? "my-3 text-sm text-[var(--muted-foreground)]" : "sr-only"}
    >
      {busy ? t("working") : notice}
    </p>
  );
}
