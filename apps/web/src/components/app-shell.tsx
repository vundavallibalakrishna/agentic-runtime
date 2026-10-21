"use client";

import { Menu, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { CommandPalette, type PaletteCommand } from "@/components/command-palette";
import { primaryNav } from "@/components/nav";
import { useTheme } from "@/components/theme-provider";
import { Button } from "@/components/ui/button";
import { api, type Session } from "@/lib/api";
import { cn } from "@/lib/utils";

const SIDEBAR_KEY = "ar-sidebar";

export function AppShell({
  children,
  flush = false,
}: {
  children: ReactNode;
  flush?: boolean;
  extraLinks?: { href: string; label: string }[];
}) {
  const t = useTranslations("shell");
  const { choice, setChoice } = useTheme();
  const [session, setSession] = useState<Session | null>(null);
  const [path, setPath] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setPath(window.location.pathname);
    setCollapsed(window.localStorage.getItem(SIDEBAR_KEY) === "collapsed");
    let cancelled = false;
    void (async () => {
      try {
        const body = await api<Session>("/api/v1/auth/session");
        if (!cancelled) {
          setSession(body);
        }
      } catch {
        if (!cancelled) {
          setSession(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const permissions = session?.permissions ?? [];
  const items = primaryNav.filter(
    (item) => permissions.length === 0 || permissions.includes(item.permission),
  );

  const commands = useMemo<PaletteCommand[]>(() => {
    const pages = items.map((item) => ({
      id: item.href,
      label: t(item.labelKey),
      hint: item.soon ? t("soon") : undefined,
      run: () => {
        window.location.assign(item.href);
      },
    }));
    return [
      {
        id: "new-chat",
        label: t("newChat"),
        hint: "⌘⇧O",
        run: () => {
          window.dispatchEvent(new Event("ar-new-chat"));
          if (!window.location.pathname.startsWith("/chat")) {
            window.location.assign("/chat");
          }
        },
      },
      ...pages,
      {
        id: "theme",
        label: t("theme"),
        run: () => {
          const order = ["system", "light", "dark"] as const;
          const next = order[(order.indexOf(choice) + 1) % order.length] ?? "system";
          setChoice(next);
        },
      },
    ];
  }, [choice, items, setChoice, t]);

  function toggleCollapsed() {
    setCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(SIDEBAR_KEY, next ? "collapsed" : "expanded");
      return next;
    });
  }

  async function signOut() {
    try {
      await api("/api/v1/auth/logout", { method: "POST", body: "{}" });
    } catch {
      window.location.assign("/login");
      return;
    }
    window.location.assign("/login");
  }

  const nav = (
    <nav aria-label="Primary" className="flex flex-1 flex-col gap-1">
      {items.map((item) => {
        const Icon = item.icon;
        const active = path === item.href || path.startsWith(`${item.href}/`);
        return (
          <a
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px] text-[var(--foreground)]",
              active ? "bg-[var(--muted)]" : "hover:bg-[var(--muted)]",
              collapsed && "lg:justify-center",
            )}
            href={item.href}
            key={item.href}
            onClick={() => setMobileOpen(false)}
            title={t(item.labelKey)}
          >
            <Icon aria-hidden="true" size={16} />
            <span className={cn(collapsed && "lg:sr-only")}>{t(item.labelKey)}</span>
            {item.soon ? (
              <span
                className={cn(
                  "ml-auto text-[11px] text-[var(--muted-foreground)]",
                  collapsed && "lg:hidden",
                )}
              >
                {t("soon")}
              </span>
            ) : null}
          </a>
        );
      })}
    </nav>
  );

  return (
    <div className="flex h-dvh bg-[var(--background)] text-[var(--foreground)]">
      <aside
        aria-label={t("sidebar")}
        className={cn(
          "hidden shrink-0 flex-col border-r border-[var(--border)] bg-[var(--sidebar)] px-3 py-4 lg:flex",
          collapsed ? "w-14" : "w-56",
        )}
      >
        <a className="mb-6 flex items-center px-2" href="/chat">
          <span className={cn("text-sm font-medium tracking-tight", collapsed && "sr-only")}>
            {t("product")}
          </span>
          <span aria-hidden="true" className={cn("text-sm font-medium", !collapsed && "hidden")}>
            A
          </span>
        </a>
        <p
          className={cn("mb-3 px-2 text-xs text-[var(--muted-foreground)]", collapsed && "sr-only")}
        >
          {session?.tenant?.name ?? t("workspace")}
        </p>
        {nav}
        <button
          aria-label={collapsed ? t("expand") : t("collapse")}
          className="mt-3 inline-flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
          onClick={toggleCollapsed}
          type="button"
        >
          {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          <span className={cn(collapsed && "sr-only")}>{t("collapse")}</span>
        </button>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 items-center gap-3 border-b border-[var(--border)] px-3 md:px-4">
          <button
            aria-label={t("openMenu")}
            className="inline-flex rounded-lg p-2 hover:bg-[var(--muted)] lg:hidden"
            onClick={() => setMobileOpen(true)}
            type="button"
          >
            <Menu size={18} />
          </button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] text-[var(--muted-foreground)]">
              {session?.user?.email ?? session?.tenant?.name ?? t("signedOut")}
            </p>
          </div>
          <CommandPalette commands={commands} />
          <div className="relative">
            <button
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              className="rounded-md px-2 py-1.5 text-[13px] hover:bg-[var(--muted)]"
              onClick={() => setMenuOpen((value) => !value)}
              type="button"
            >
              {session?.user?.displayName ?? t("account")}
            </button>
            {menuOpen ? (
              <div
                className="absolute right-0 z-20 mt-2 w-52 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--card)] p-1 shadow-[var(--shadow)]"
                role="menu"
              >
                <p className="px-2 py-1 text-xs text-[var(--muted-foreground)]">{t("theme")}</p>
                {(["system", "light", "dark"] as const).map((option) => (
                  <button
                    className={cn(
                      "block w-full rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-[var(--muted)]",
                      choice === option && "font-medium",
                    )}
                    key={option}
                    onClick={() => {
                      setChoice(option);
                      setMenuOpen(false);
                    }}
                    role="menuitem"
                    type="button"
                  >
                    {t(option)}
                  </button>
                ))}
                <button
                  className="mt-1 block w-full rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-[var(--muted)]"
                  onClick={() => void signOut()}
                  role="menuitem"
                  type="button"
                >
                  {t("signOut")}
                </button>
              </div>
            ) : null}
          </div>
        </header>
        <main className={cn("min-h-0 flex-1", flush ? "overflow-hidden" : "overflow-auto")}>
          {flush ? children : <div className="mx-auto w-full max-w-6xl p-4 md:p-8">{children}</div>}
        </main>
      </div>
      {mobileOpen ? (
        <div className="fixed inset-0 z-30 lg:hidden">
          <button
            aria-label={t("closeMenu")}
            className="absolute inset-0 bg-[var(--scrim)]"
            onClick={() => setMobileOpen(false)}
            type="button"
          />
          <div className="absolute inset-y-0 left-0 flex w-72 flex-col bg-[var(--sidebar)] p-4 shadow-[var(--shadow)]">
            <p className="text-sm font-medium tracking-tight">{t("product")}</p>
            <div className="mt-4 flex min-h-0 flex-1 flex-col">{nav}</div>
            <Button onClick={() => setMobileOpen(false)} type="button" variant="outline">
              {t("closeMenu")}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
