"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TableScroll } from "@/components/ui/table";
import { ApiError, apiErrorGuidance, type DisplayError } from "@/lib/api";

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
  error: DisplayError;
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
          <div className="min-w-0 flex-1 break-words">
            <ErrorMessage error={error} />
          </div>
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

export function ActionStatus({
  busy,
  notice,
  busyLabel,
}: {
  busy: boolean;
  notice?: string;
  busyLabel?: string;
}) {
  const t = useTranslations("detail");
  return (
    <p
      role="status"
      className={busy || notice ? "my-3 text-sm text-[var(--muted-foreground)]" : "sr-only"}
    >
      {busy ? (busyLabel ?? t("working")) : notice}
    </p>
  );
}

/** One presentation path for API guidance and the original diagnostic detail. */
export function ErrorMessage({ error }: { error: DisplayError }) {
  const t = useTranslations("apiErrors");
  const [disclosure, setDisclosure] = useState<{ error: DisplayError; open: boolean } | null>(null);
  const guidance = apiErrorGuidance(error);
  const message = error instanceof Error ? error.message : error;
  if (!guidance) return <>{message || t("unknown")}</>;
  const open = disclosure?.error === error && disclosure.open;
  return (
    <div className="min-w-0 space-y-2 break-words">
      <p>{t(guidance)}</p>
      <details
        open={open}
        onToggle={(event) => setDisclosure({ error, open: event.currentTarget.open })}
      >
        <summary className="cursor-pointer text-xs font-medium underline underline-offset-4">
          {t("details")}
        </summary>
        {open ? (
          <TableScroll
            label={t("details")}
            className="mt-2 max-h-48 rounded-lg border border-[var(--border)] p-3 text-xs"
          >
            {error instanceof ApiError ? (
              <p className="mb-2">
                {t("status", { status: error.status })}
                {error.code ? ` · ${error.code}` : ""}
              </p>
            ) : null}
            <p className="whitespace-pre-wrap break-words">{message || t("noDetails")}</p>
          </TableScroll>
        ) : null}
      </details>
    </div>
  );
}
