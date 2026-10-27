"use client";

import * as Dialog from "@radix-ui/react-dialog";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  ArrowUpRight,
  Check,
  ChevronDown,
  ChevronRight,
  Layers2,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  UserRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { type ReactNode, useEffect, useLayoutEffect, useMemo, useState } from "react";

import { CommandPalette, type PaletteCommand } from "@/components/command-palette";
import { primaryNav } from "@/components/nav";
import { useTheme } from "@/components/theme-provider";
import { ApiError, api, type Session } from "@/lib/api";
import { cn } from "@/lib/utils";

const SIDEBAR_KEY = "ar-sidebar";
let rememberedSession: Session | null = null;
const sections = ["workspace", "resources", "manage"] as const;
const sectionLabels = {
  workspace: "sectionWorkspace",
  resources: "sectionResources",
  manage: "sectionManage",
} as const;

export function AppShell({
  children,
  flush = false,
}: {
  children: ReactNode;
  flush?: boolean;
  extraLinks?: { href: string; label: string }[];
}) {
  const t = useTranslations("shell");
  const router = useRouter();
  const replaceRoute = router.replace;
  const path = usePathname();
  const { choice, setChoice } = useTheme();
  const [session, setSession] = useState<Session | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useLayoutEffect(() => {
    if (rememberedSession) setSession(rememberedSession);
  }, []);

  useEffect(() => {
    setCollapsed(window.localStorage.getItem(SIDEBAR_KEY) === "collapsed");
    let cancelled = false;
    void api<Session>("/api/v1/auth/session")
      .then((body) => {
        rememberedSession = body;
        if (!cancelled) setSession(body);
      })
      .catch((error: unknown) => {
        rememberedSession = null;
        if (!cancelled) {
          setSession(null);
          if (error instanceof ApiError && error.status === 401) replaceRoute("/login");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [replaceRoute]);

  const items = useMemo(
    () => primaryNav.filter((item) => session?.permissions?.includes(item.permission)),
    [session],
  );
  const current = items.find((item) => path === item.href || path.startsWith(`${item.href}/`));

  function newChat() {
    window.dispatchEvent(new Event("ar-new-chat"));
    if (!window.location.pathname.startsWith("/chat")) router.push("/chat");
    setMobileOpen(false);
  }

  const commands = useMemo<PaletteCommand[]>(
    () => [
      ...(session?.permissions?.includes("chat:use")
        ? [
            {
              id: "new-chat",
              label: t("newChat"),
              hint: "⌘⇧O",
              run: () => {
                window.dispatchEvent(new Event("ar-new-chat"));
                if (!window.location.pathname.startsWith("/chat")) router.push("/chat");
              },
            },
          ]
        : []),
      ...items.map((item) => ({
        id: item.href,
        label: t(item.labelKey),
        hint: item.soon ? t("soon") : undefined,
        run: () => router.push(item.href),
      })),
      {
        id: "theme",
        label: t("theme"),
        run: () => {
          const order = ["system", "light", "dark"] as const;
          setChoice(order[(order.indexOf(choice) + 1) % order.length] ?? "system");
        },
      },
    ],
    [choice, items, router, session, setChoice, t],
  );

  async function signOut() {
    rememberedSession = null;
    try {
      await api("/api/v1/auth/logout", { method: "POST", body: "{}" });
    } finally {
      window.location.assign("/login");
    }
  }

  const brand = (
    <Link className="flex min-w-0 items-center gap-2.5" href="/chat" aria-label={t("product")}>
      <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-[var(--primary)] text-[var(--primary-foreground)]">
        <Layers2 size={20} aria-hidden="true" strokeWidth={1.6} />
      </span>
      <span className={cn("text-[15px] font-semibold tracking-tight", collapsed && "lg:sr-only")}>
        {t("product")}
      </span>
    </Link>
  );

  const nav = (
    <nav
      aria-label={t("primaryNavigation")}
      className="min-h-0 flex-1 space-y-5 overflow-y-auto px-1 py-2"
    >
      {sections.map((section) => {
        const entries = items.filter((item) => item.section === section);
        if (!entries.length) return null;
        return (
          <div key={section}>
            <p
              className={cn(
                "mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--muted-foreground)]",
                collapsed && "lg:sr-only",
              )}
            >
              {t(sectionLabels[section])}
            </p>
            <div className="space-y-0.5">
              {entries.map((item) => {
                const Icon = item.icon;
                const active = path === item.href || path.startsWith(`${item.href}/`);
                return (
                  <Link
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "group flex min-h-9 items-center gap-3 rounded-lg px-3 py-2 text-[13px]",
                      active
                        ? "bg-[var(--nav-active)] font-semibold text-[var(--foreground)] shadow-[var(--shadow-xs)]"
                        : "text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]",
                      collapsed && "lg:justify-center lg:px-2",
                    )}
                    href={item.href}
                    key={item.href}
                    onClick={() => setMobileOpen(false)}
                    title={t(item.labelKey)}
                  >
                    <Icon aria-hidden="true" size={17} strokeWidth={1.7} />
                    <span className={cn("flex-1", collapsed && "lg:sr-only")}>
                      {t(item.labelKey)}
                    </span>
                    {active ? (
                      <span
                        aria-hidden="true"
                        className={cn(
                          "size-1.5 rounded-full bg-[var(--foreground)]",
                          collapsed && "lg:hidden",
                        )}
                      />
                    ) : null}
                    {item.soon ? (
                      <span className={cn("text-[10px]", collapsed && "lg:hidden")}>
                        {t("soon")}
                      </span>
                    ) : null}
                  </Link>
                );
              })}
            </div>
          </div>
        );
      })}
    </nav>
  );

  return (
    <div className="flex h-dvh bg-[var(--background)] text-[var(--foreground)]">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-[var(--card)] focus:p-3"
      >
        {t("skipToContent")}
      </a>
      <aside
        aria-label={t("sidebar")}
        className={cn(
          "hidden shrink-0 flex-col border-r border-[var(--border)] bg-[var(--sidebar)] px-3 py-5 lg:flex",
          collapsed ? "w-[72px]" : "w-60",
        )}
      >
        <div className="mb-5 px-1">{brand}</div>
        {session?.permissions?.includes("chat:use") ? (
          <button
            aria-label={`${t("newChat")} ⌘⇧O`}
            className={cn(
              "mb-5 flex h-10 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-[13px] font-medium shadow-[var(--shadow-xs)] hover:bg-[var(--muted)]",
              collapsed && "justify-center px-0",
            )}
            onClick={newChat}
            type="button"
          >
            <Plus size={16} aria-hidden="true" />
            <span className={cn(collapsed && "sr-only")}>{t("newChat")}</span>
            <kbd
              className={cn(
                "ml-auto text-[10px] text-[var(--muted-foreground)]",
                collapsed && "hidden",
              )}
            >
              ⌘⇧O
            </kbd>
          </button>
        ) : null}
        {nav}
        {session?.permissions?.includes("agents:create") && !collapsed ? (
          <Link
            href="/agents/new"
            className="mt-3 flex items-center justify-between rounded-lg border border-[var(--border)] px-3 py-3 text-xs font-medium hover:bg-[var(--card)]"
          >
            {t("createAgent")}
            <ArrowUpRight size={15} aria-hidden="true" />
          </Link>
        ) : null}
        <button
          aria-label={collapsed ? t("expand") : t("collapse")}
          className="mt-3 flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
          onClick={() =>
            setCollapsed((value) => {
              window.localStorage.setItem(SIDEBAR_KEY, value ? "expanded" : "collapsed");
              return !value;
            })
          }
          type="button"
        >
          {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          <span className={cn(collapsed && "sr-only")}>{t("collapse")}</span>
        </button>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-4 md:px-6">
          <Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}>
            <Dialog.Trigger asChild>
              <button
                aria-label={t("openMenu")}
                className="rounded-lg p-2 hover:bg-[var(--muted)] lg:hidden"
                type="button"
              >
                <Menu size={18} />
              </button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-40 bg-[var(--scrim)]" />
              <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-[min(20rem,85vw)] flex-col bg-[var(--sidebar)] p-4 shadow-[var(--shadow)]">
                <Dialog.Title className="sr-only">{t("sidebar")}</Dialog.Title>
                <Dialog.Description className="sr-only">
                  {t("primaryNavigation")}
                </Dialog.Description>
                <div className="mb-6 flex items-center justify-between">
                  {brand}
                  <Dialog.Close
                    aria-label={t("closeMenu")}
                    className="rounded-lg p-2 hover:bg-[var(--muted)]"
                  >
                    <X size={18} />
                  </Dialog.Close>
                </div>
                {nav}
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
          <div className="flex min-w-0 flex-1 items-center gap-2 text-xs md:text-[13px]">
            <span className="truncate text-[var(--muted-foreground)]">
              {session?.tenant?.name ?? t("workspace")}
            </span>
            {current ? (
              <>
                <ChevronRight
                  size={12}
                  className="shrink-0 text-[var(--muted-foreground)]"
                  aria-hidden="true"
                />
                <span className="truncate font-medium">{t(current.labelKey)}</span>
              </>
            ) : null}
          </div>
          <CommandPalette commands={commands} />
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button
                className="flex shrink-0 items-center gap-2 rounded-lg p-1.5 hover:bg-[var(--muted)]"
                type="button"
              >
                <span
                  aria-hidden="true"
                  className="flex size-8 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--sidebar)] text-xs font-semibold"
                >
                  <UserRound size={16} aria-hidden="true" />
                </span>
                <span className="sr-only text-left xl:not-sr-only xl:block">
                  <span className="block text-xs font-medium">
                    {session?.user?.displayName ?? t("account")}
                  </span>
                  <span className="block text-[11px] text-[var(--muted-foreground)]">
                    {session?.user?.email}
                  </span>
                </span>
                <ChevronDown size={12} aria-hidden="true" />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="end"
                sideOffset={8}
                className="z-50 min-w-56 rounded-xl border border-[var(--border)] bg-[var(--card)] p-1.5 shadow-[var(--shadow)]"
              >
                <DropdownMenu.Label className="border-b border-[var(--border)] px-2 py-2 text-xs text-[var(--muted-foreground)]">
                  {session?.user?.email ?? t("account")}
                </DropdownMenu.Label>
                <DropdownMenu.Label className="px-2 pb-1 pt-3 text-[10px] uppercase tracking-widest text-[var(--muted-foreground)]">
                  {t("theme")}
                </DropdownMenu.Label>
                {(["system", "light", "dark"] as const).map((option) => (
                  <DropdownMenu.Item
                    key={option}
                    onSelect={() => setChoice(option)}
                    className="flex cursor-pointer items-center justify-between rounded-md px-2 py-2 text-sm outline-none focus:bg-[var(--muted)]"
                  >
                    {t(option)}
                    {choice === option ? <Check size={14} aria-hidden="true" /> : null}
                  </DropdownMenu.Item>
                ))}
                <DropdownMenu.Separator className="my-1 h-px bg-[var(--border)]" />
                <DropdownMenu.Item asChild>
                  <Link
                    href="/settings/profile"
                    className="block rounded-md px-2 py-2 text-sm outline-none focus:bg-[var(--muted)]"
                  >
                    {t("profile")}
                  </Link>
                </DropdownMenu.Item>
                <DropdownMenu.Item
                  onSelect={() => void signOut()}
                  className="cursor-pointer rounded-md px-2 py-2 text-sm outline-none focus:bg-[var(--muted)]"
                >
                  {t("signOut")}
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </header>
        <main
          id="main-content"
          tabIndex={-1}
          className={cn("min-h-0 flex-1", flush ? "overflow-hidden" : "overflow-auto")}
        >
          {flush ? (
            children
          ) : (
            <div className="mx-auto w-full max-w-6xl p-5 md:p-10">{children}</div>
          )}
        </main>
      </div>
    </div>
  );
}
