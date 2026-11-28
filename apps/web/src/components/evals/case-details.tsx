"use client";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { TableScroll } from "@/components/ui/table";
import { formatDataValue } from "@/lib/format";
import type { SavedCase } from "./case-data";

export function CaseReceipt({ value, compact = false }: { value: SavedCase; compact?: boolean }) {
  const t = useTranslations("evals");
  const [open, setOpen] = useState(false);
  return (
    <div
      className={`${compact ? "space-y-2" : "space-y-3"} rounded-lg border border-[var(--border)] p-3 text-sm`}
    >
      <p className="break-words font-medium">{value.name}</p>
      <p title={value.id} className="break-all text-xs text-[var(--muted-foreground)]">
        {t("caseReference", { id: compact ? value.id.slice(-8) : value.id })}
      </p>
      {!compact ? <p className="text-[var(--muted-foreground)]">{t("copiedCaseHelp")}</p> : null}
      {value.assertions.some(
        (row) => row.type === "lexical_overlap" || row.type === "llm_judge",
      ) ? (
        <p>{t(compact ? "assertionTypes.lexical_overlap" : "copiedCaseNotJudged")}</p>
      ) : null}
      <details open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary
          aria-label={t("caseDetailsFor", { name: value.name, id: value.id })}
          className="cursor-pointer"
        >
          {t("copiedCaseDetails")}
        </summary>
        {open ? (
          <TableScroll
            label={t("copiedCaseDetails")}
            className="mt-3 max-h-64 rounded-lg border border-[var(--border)] p-3 text-xs"
          >
            <pre className="whitespace-pre-wrap break-words">
              {formatDataValue({ input: value.input, assertions: value.assertions })}
            </pre>
          </TableScroll>
        ) : null}
      </details>
    </div>
  );
}
