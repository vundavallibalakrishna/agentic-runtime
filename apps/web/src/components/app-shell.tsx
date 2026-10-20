"use client";

import { Bot } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

export function AppShell({
  children,
  extraLinks = [],
}: {
  children: ReactNode;
  extraLinks?: { href: string; label: string }[];
}) {
  const t = useTranslations("shell");
  const links = [
    { href: "/", label: t("navHome") },
    { href: "/agents", label: t("navAgents") },
    ...extraLinks,
  ];
  return (
    <div className="grid min-h-screen grid-cols-[220px_1fr]">
      <aside className="border-r border-[var(--border)] p-4">
        <p className="flex items-center gap-2 text-sm font-semibold">
          <Bot aria-hidden="true" size={16} />
          {t("product")}
        </p>
        <nav className="mt-4 flex flex-col gap-2 text-sm" aria-label="Primary">
          {links.map((link) => (
            <a key={link.href} href={link.href}>
              {link.label}
            </a>
          ))}
        </nav>
      </aside>
      <main className="p-6">{children}</main>
    </div>
  );
}
