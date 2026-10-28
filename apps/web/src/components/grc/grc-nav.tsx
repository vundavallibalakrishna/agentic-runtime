"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";

const grcTabs = [
  { href: "/grc", id: "frameworks", label: "frameworks" },
  { href: "/grc/controls", id: "controls", label: "controls" },
  { href: "/grc/evidence", id: "evidence", label: "evidence" },
  { href: "/grc/tests", id: "tests", label: "tests" },
  { href: "/grc/findings", id: "findings", label: "findings" },
  { href: "/grc/connectors", id: "connectors", label: "connectors" },
  { href: "/grc/workflows", id: "workflows", label: "workflows" },
] as const;

export function GrcNav({ section }: { section: string }) {
  const t = useTranslations("grc");
  return (
    <nav aria-label={t("title")} className="mb-6 flex flex-wrap gap-2">
      {grcTabs.map((tab) => (
        <Link
          className={cn(
            "rounded-lg px-3 py-2 text-sm",
            section === tab.id
              ? "bg-[var(--nav-active)] font-semibold"
              : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]",
          )}
          href={tab.href}
          key={tab.id}
        >
          {t(tab.label)}
        </Link>
      ))}
    </nav>
  );
}
