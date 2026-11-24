"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { BackButton } from "@/components/common/detail-state";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Side = { id?: string; title?: string; filename?: string };
type Section = {
  status: "changed" | "added" | "removed";
  heading?: string;
  leftAnchor?: string;
  rightAnchor?: string;
  leftQuote?: string;
  rightQuote?: string;
};
type Comparison = {
  left?: Side;
  right?: Side;
  counts?: Record<string, number>;
  sections?: Section[];
  total?: number;
};

const TONES: Record<Section["status"], Tone> = {
  changed: "warning",
  added: "success",
  removed: "danger",
};
const COUNTED = ["changed", "added", "removed", "unchanged"] as const;

function nameOf(side: Side | undefined): string {
  return side?.title || side?.filename || "";
}

/**
 * What differs between two stored documents, section by section.
 *
 * The comparison works on the stored text and asks no model, so every line shown is the
 * document's own words. Each side links to the passage in its document.
 */
export function CompareScreen({ left, right }: { left: string; right: string }) {
  const t = useTranslations("documents");
  const [body, setBody] = useState<Comparison | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!left || !right) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      setBody(
        await api<Comparison>(
          `/api/v1/library-documents/${left}/diff?otherDocumentId=${encodeURIComponent(right)}`,
        ),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("compareError"));
    } finally {
      setLoading(false);
    }
  }, [left, right, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const sections = body?.sections ?? [];
  const total = body?.total ?? sections.length;
  const before = nameOf(body?.left);
  const after = nameOf(body?.right);
  return (
    <AppShell>
      <PageHeader
        actions={<BackButton href="/documents">{t("back")}</BackButton>}
        body={body ? t("compareNamed", { before, after }) : t("compareBody")}
        title={t("compareTitle")}
      />
      {loading ? <Skeleton className="h-48 w-full" /> : null}
      {!loading && (!left || !right) ? <EmptyState title={t("comparePick")} /> : null}
      {error ? (
        <p className="mb-4 text-sm text-[var(--destructive)]" role="alert">
          {error}{" "}
          <Button onClick={() => void load()} type="button" variant="outline">
            {t("retry")}
          </Button>
        </p>
      ) : null}
      {!loading && body ? (
        <div className="space-y-5">
          <ul aria-label={t("compareSummary")} className="flex flex-wrap gap-2">
            {COUNTED.map((key) => (
              <li key={key}>
                <Badge tone={key === "unchanged" ? "neutral" : TONES[key]}>
                  {t(`compareCount.${key}`, { count: body.counts?.[key] ?? 0 })}
                </Badge>
              </li>
            ))}
          </ul>
          {sections.length === 0 ? <EmptyState title={t("compareSame")} /> : null}
          {total > sections.length ? (
            <p className="text-sm text-[var(--muted-foreground)]">
              {t("compareShown", { shown: sections.length, total })}
            </p>
          ) : null}
          <ul className="space-y-4">
            {sections.map((section) => (
              <li
                className="detail-panel p-5"
                key={`${section.status}-${section.leftAnchor}-${section.rightAnchor}`}
              >
                <div className="mb-3 flex flex-wrap items-center gap-3">
                  <h2 className="panel-title">{section.heading || t("compareNoHeading")}</h2>
                  <Badge tone={TONES[section.status]}>{t(`compareStatus.${section.status}`)}</Badge>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <Quote
                    anchor={section.leftAnchor}
                    document={left}
                    empty={t("compareNotIn", { name: before })}
                    label={before}
                    open={t("compareOpen")}
                    text={section.leftQuote}
                  />
                  <Quote
                    anchor={section.rightAnchor}
                    document={right}
                    empty={t("compareNotIn", { name: after })}
                    label={after}
                    open={t("compareOpen")}
                    text={section.rightQuote}
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </AppShell>
  );
}

function Quote({
  label,
  text,
  anchor,
  document,
  empty,
  open,
}: {
  label: string;
  text?: string;
  anchor?: string;
  document: string;
  empty: string;
  open: string;
}) {
  return (
    <div className="min-w-0">
      <p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">{label}</p>
      {text ? (
        <>
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{text}</p>
          {anchor ? (
            <a
              aria-label={`${open}: ${label}, ${anchor}`}
              className="mt-2 inline-block text-xs underline"
              href={`/documents/${document}#${anchor}`}
            >
              {open} <span className="font-mono">{anchor}</span>
            </a>
          ) : null}
        </>
      ) : (
        <p className="text-sm italic text-[var(--muted-foreground)]">{empty}</p>
      )}
    </div>
  );
}
