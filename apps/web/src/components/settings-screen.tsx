"use client";

import { ChevronRight, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { AppShell, useShellNav } from "@/components/app-shell";
import { navSectionLabels, navSections } from "@/components/nav";

const tile =
  "group flex min-h-14 items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm font-medium shadow-[var(--shadow-xs)] transition-colors hover:border-[var(--primary)]";

/** Settings: every screen that is not chat or agents, grouped, one click away. */
export function SettingsScreen() {
  return (
    <AppShell>
      <SettingsHub />
    </AppShell>
  );
}

function SettingsHub() {
  const t = useTranslations("shell");
  const { items, packLinks, ready } = useShellNav();
  const more = items.filter((item) => !item.home);
  const empty = ready && more.length === 0 && packLinks.length === 0;

  return (
    <div className="mx-auto w-full max-w-4xl">
      <h1 className="font-display text-2xl tracking-tight">{t("navSettings")}</h1>
      <p className="mt-2 text-sm leading-relaxed text-[var(--muted-foreground)]">
        {t("settingsBody")}
      </p>
      {!ready ? (
        <p className="mt-8 text-sm text-[var(--muted-foreground)]" role="status">
          {t("settingsLoading")}
        </p>
      ) : null}
      {empty ? (
        <p className="mt-8 text-sm text-[var(--muted-foreground)]">{t("settingsEmpty")}</p>
      ) : null}
      {navSections.map((section) => {
        const entries = more.filter((item) => item.section === section);
        if (!entries.length) return null;
        return (
          <section className="mt-8" key={section}>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--muted-foreground)]">
              {t(navSectionLabels[section])}
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {entries.map((item) => {
                const Icon = item.icon;
                return (
                  <Link className={tile} href={item.href} key={item.href}>
                    <Icon
                      aria-hidden="true"
                      className="text-[var(--muted-foreground)] group-hover:text-[var(--primary)]"
                      size={18}
                      strokeWidth={1.7}
                    />
                    <span className="flex-1">{t(item.labelKey)}</span>
                    <ChevronRight
                      aria-hidden="true"
                      className="text-[var(--muted-foreground)]"
                      size={15}
                    />
                  </Link>
                );
              })}
            </div>
          </section>
        );
      })}
      {packLinks.length ? (
        <section className="mt-8">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--muted-foreground)]">
            {t("sectionPacks")}
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {packLinks.map((item) => (
              <Link className={tile} href={item.href} key={item.href}>
                <ShieldCheck
                  aria-hidden="true"
                  className="text-[var(--muted-foreground)] group-hover:text-[var(--primary)]"
                  size={18}
                  strokeWidth={1.7}
                />
                <span className="flex-1">{item.label}</span>
                <ChevronRight
                  aria-hidden="true"
                  className="text-[var(--muted-foreground)]"
                  size={15}
                />
              </Link>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
