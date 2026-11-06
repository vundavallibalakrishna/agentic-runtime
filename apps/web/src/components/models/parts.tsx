"use client";

import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

import type { TestResult } from "./types";

const SELECT =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 text-sm disabled:opacity-60";

export function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-1">
      <label className="text-sm font-medium" htmlFor={id}>
        {label}
      </label>
      {children}
      {hint ? (
        <p className="text-xs leading-relaxed text-[var(--muted-foreground)]" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function Select({
  id,
  value,
  onChange,
  disabled,
  label,
  children,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  label?: string;
  children: ReactNode;
}) {
  return (
    <select
      aria-label={label}
      className={SELECT}
      disabled={disabled}
      id={id}
      onChange={(event) => onChange(event.target.value)}
      value={value}
    >
      {children}
    </select>
  );
}

/** An error the person can act on, with room around it and a way to dismiss or retry. */
export function Problem({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div
      className="flex flex-wrap items-center gap-3 rounded-lg border border-[var(--destructive)] bg-[var(--card)] px-4 py-3 text-sm"
      role="alert"
    >
      <p className="min-w-0 flex-1 leading-relaxed">{children}</p>
      {action}
    </div>
  );
}

/** What a test returned, said in words: it answered, or why it did not. */
export function TestLine({ result }: { result: TestResult | "running" | undefined }) {
  const t = useTranslations("models");
  if (result === undefined) {
    return null;
  }
  if (result === "running") {
    return (
      <p className="text-xs text-[var(--muted-foreground)]" role="status">
        {t("testing")}
      </p>
    );
  }
  return (
    <p className="break-words text-xs leading-relaxed" role="status">
      <span className="font-medium">{result.ok ? t("testPassed") : t("testFailed")}</span>{" "}
      <span className="text-[var(--muted-foreground)]">
        {result.ok
          ? t("testAnswer", { output: result.output, ms: result.latencyMs })
          : result.output}
      </span>
    </p>
  );
}

export function RowActions({ children }: { children: ReactNode }) {
  return <div className="flex shrink-0 flex-wrap items-center gap-1">{children}</div>;
}

export function SmallButton({
  children,
  onClick,
  disabled,
  label,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <Button
      aria-label={label}
      className="px-2 py-1 text-xs"
      disabled={disabled}
      onClick={onClick}
      type="button"
      variant="outline"
    >
      {children}
    </Button>
  );
}
