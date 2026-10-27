"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

export function SettingsMode({
  advanced,
  onChange,
}: {
  advanced: boolean;
  onChange: (advanced: boolean) => void;
}) {
  const t = useTranslations("layout");
  return (
    <fieldset className="inline-flex w-fit gap-1 rounded-lg border border-[var(--border)] bg-[var(--muted)] p-1">
      <legend className="sr-only">{t("settingsMode")}</legend>
      {[false, true].map((value) => (
        <button
          key={String(value)}
          type="button"
          aria-pressed={advanced === value}
          onClick={() => onChange(value)}
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-medium",
            advanced === value
              ? "bg-[var(--card)] text-[var(--foreground)] shadow-[var(--shadow-xs)]"
              : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
          )}
        >
          {value ? t("advanced") : t("simple")}
        </button>
      ))}
    </fieldset>
  );
}
