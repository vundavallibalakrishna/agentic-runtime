"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";

/** Copies `value` and says so for a moment. `label` names what is copied, for a reader. */
export function CopyButton({ value, label }: { value: string; label?: string }) {
  const t = useTranslations("detail");
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }
  const text = copied ? t("copied") : t("copy");
  return (
    <Button
      aria-label={label ? `${text}: ${label}` : undefined}
      onClick={() => void copy()}
      type="button"
      variant="outline"
    >
      {text}
    </Button>
  );
}
