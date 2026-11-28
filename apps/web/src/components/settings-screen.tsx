"use client";

import { ChevronRight, Search, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { AppShell, useShellNav } from "@/components/app-shell";
import { navSectionLabels, navSections } from "@/components/nav";

const tile =
  "group flex min-h-16 items-center gap-3 border-b border-[var(--border)] px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-[var(--muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--ring)]";

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
  const [query, setQuery] = useState("");
  const more = items.filter((item) => !item.home);
  const matches = (label: string, help: string) =>
    `${label} ${help}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
  const empty = ready && more.length === 0 && packLinks.length === 0;

  return (
    <div className="mx-auto w-full max-w-4xl">
      <h1 className="font-display text-2xl tracking-tight">{t("navSettings")}</h1>
      <p className="mt-2 text-sm leading-relaxed text-[var(--muted-foreground)]">
        {t("settingsBody")}
      </p>
      {ready && !empty ? (
        <label className="relative mt-6 block max-w-md">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-3 text-[var(--muted-foreground)]"
            size={17}
          />
          <span className="sr-only">{t("findSetting")}</span>
          <input
            className="h-11 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] pl-10 pr-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("findSetting")}
            type="search"
            value={query}
          />
        </label>
      ) : null}
      {!ready ? (
        <p className="mt-8 text-sm text-[var(--muted-foreground)]" role="status">
          {t("settingsLoading")}
        </p>
      ) : null}
      {empty ? (
        <p className="mt-8 text-sm text-[var(--muted-foreground)]">{t("settingsEmpty")}</p>
      ) : null}
      {ready &&
      query.trim() &&
      !more.some((item) => matches(t(item.labelKey), t(`settingHelp.${item.labelKey}`))) &&
      !packLinks.some((item) => matches(item.label, "")) ? (
        <p className="mt-8 text-sm text-[var(--muted-foreground)]">{t("noSettingMatches")}</p>
      ) : null}
      {navSections.map((section) => {
        const entries = more.filter(
          (item) =>
            item.section === section &&
            matches(t(item.labelKey), t(`settingHelp.${item.labelKey}`)),
        );
        if (!entries.length) return null;
        return (
          <section className="mt-8" key={section}>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--muted-foreground)]">
              {t(navSectionLabels[section])}
            </h2>
            <div className="grid overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] sm:grid-cols-2">
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
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">{t(item.labelKey)}</span>
                      <span className="mt-0.5 block text-xs leading-relaxed text-[var(--muted-foreground)]">
                        {t(`settingHelp.${item.labelKey}`)}
                      </span>
                    </span>
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
      {packLinks.some((item) => matches(item.label, "")) ? (
        <section className="mt-8">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--muted-foreground)]">
            {t("sectionPacks")}
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {packLinks
              .filter((item) => matches(item.label, ""))
              .map((item) => (
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
