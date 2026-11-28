"use client";

import * as Dialog from "@radix-ui/react-dialog";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  Bot,
  Check,
  ChevronDown,
  Layers2,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Settings,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
} from "react";

import { CommandPalette, type PaletteCommand } from "@/components/command-palette";
import { type NavItem, navSectionLabels, navSections, primaryNav } from "@/components/nav";
import { useTheme } from "@/components/theme-provider";
import { Button } from "@/components/ui/button";
import { ApiError, api, isRateLimited, type Session } from "@/lib/api";
import { clearCachedSession, loadSession } from "@/lib/session";
import { cn } from "@/lib/utils";

const SIDEBAR_KEY = "ar-sidebar";
let rememberedSession: Session | null = null;
const SETTINGS_HREF = "/settings";

type ShellNav = {
  /** The screens this person may open, signed-in permissions and tenant features applied. */
  items: NavItem[];
  /** Links that installed packs add. */
  packLinks: { href: string; label: string }[];
  ready: boolean;
};

const ShellNavContext = createContext<ShellNav>({ items: [], packLinks: [], ready: false });

/** What the signed-in person may open. Read by the Settings screen, which lists it. */
export function useShellNav(): ShellNav {
  return useContext(ShellNavContext);
}
// One look for every row in the dark navigation column.
const navRow = "group flex min-h-10 items-center gap-3 rounded-md px-3 py-2 text-[13px]";
const navRowIdle =
  "text-[var(--sidebar-foreground)] hover:bg-[var(--sidebar-hover)] hover:text-[var(--sidebar-strong)]";
const navRowActive = "bg-[var(--nav-active)] font-semibold text-[var(--nav-active-foreground)]";
const navHeading =
  "mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--sidebar-muted)]";

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
  // "failed" is any answer to the session check other than a session or "not signed in".
  // The page is then replaced by an error with a retry: a failed check is not a sign-in.
  const [check, setCheck] = useState<"unknown" | "signed-in" | "failed" | "limited">("unknown");
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [packLinks, setPackLinks] = useState<{ href: string; label: string }[]>([]);

  useLayoutEffect(() => {
    if (rememberedSession) setSession(rememberedSession);
  }, []);

  const checkSession = useCallback(() => {
    let cancelled = false;
    void loadSession()
      .then((body) => {
        rememberedSession = body;
        if (cancelled || typeof window === "undefined") return;
        setSession(body);
        setCheck("signed-in");
      })
      .catch((error: unknown) => {
        if (cancelled || typeof window === "undefined") return;
        if (error instanceof ApiError && error.status === 401) {
          rememberedSession = null;
          clearCachedSession();
          setSession(null);
          replaceRoute("/login");
          return;
        }
        // A rate limit is a pause. The cookie is still a session, so this is not a sign-out.
        if (isRateLimited(error)) {
          setCheck("limited");
          return;
        }
        rememberedSession = null;
        setSession(null);
        setCheck("failed");
      });
    return () => {
      cancelled = true;
    };
  }, [replaceRoute]);

  useEffect(() => {
    setCollapsed(window.localStorage.getItem(SIDEBAR_KEY) === "collapsed");
    return checkSession();
  }, [checkSession]);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    void api<{
      items?: { enabled?: boolean; nav?: { href?: string; label?: string }[] }[];
      data?: { enabled?: boolean; nav?: { href?: string; label?: string }[] }[];
    }>("/api/v1/tenant/packs")
      .then((body) => {
        if (cancelled) return;
        const links: { href: string; label: string }[] = [];
        for (const row of body.items ?? body.data ?? []) {
          if (!row.enabled) continue;
          for (const item of row.nav ?? []) {
            if (item.href && item.label) links.push({ href: item.href, label: item.label });
          }
        }
        if (typeof window === "undefined") return;
        setPackLinks(links);
      })
      .catch(() => {
        if (!cancelled && typeof window !== "undefined") setPackLinks([]);
      });
    return () => {
      cancelled = true;
    };
  }, [session]);

  const items = useMemo(
    () =>
      primaryNav.filter(
        (item) =>
          session?.permissions?.includes(item.permission) &&
          (!item.feature || session?.features?.[item.feature] === true),
      ),
    [session],
  );
  const current = items.find((item) => path === item.href || path.startsWith(`${item.href}/`));
  const homeItems = useMemo(() => items.filter((item) => item.home), [items]);
  const shellNav = useMemo(
    () => ({ items, packLinks, ready: check === "signed-in" }),
    [check, items, packLinks],
  );

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
      ...packLinks.map((item) => ({
        id: item.href,
        label: item.label,
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
    [choice, items, packLinks, router, session, setChoice, t],
  );

  async function signOut() {
    rememberedSession = null;
    clearCachedSession();
    try {
      await api("/api/v1/auth/logout", { method: "POST", body: "{}" });
    } finally {
      window.location.assign("/login");
    }
  }

  const brand = (
    <Link className="flex min-w-0 shrink-0 items-center gap-2.5" href="/chat">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-[var(--primary)] text-[var(--primary-foreground)]">
        <Layers2 size={18} aria-hidden="true" strokeWidth={1.8} />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold">{t("product")}</span>
        {session?.tenant?.name ? (
          <span className="block truncate text-xs text-[var(--muted-foreground)]">
            {session.tenant.name}
          </span>
        ) : null}
      </span>
    </Link>
  );

  const packCurrent = packLinks.find(
    (item) => path === item.href || path.startsWith(`${item.href}/`),
  );
  const inSettings =
    path === SETTINGS_HREF ||
    path.startsWith(`${SETTINGS_HREF}/`) ||
    Boolean(packCurrent) ||
    Boolean(current && !current.home);
  const moreItems = items.filter((item) => !item.home);

  // The top bar holds what a person came for: a chat and the agents. Everything else is
  // under Settings, which brings its own side column.
  const topLink = "flex h-9 items-center gap-2 rounded-md px-3 text-[13px]";
  const topLinkIdle =
    "text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]";
  const topLinkActive = "bg-[var(--muted)] font-semibold text-[var(--foreground)]";
  const homeLinks = (vertical: boolean) => (
    <>
      {homeItems.map((item) => {
        const Icon = item.icon;
        const active = path === item.href || path.startsWith(`${item.href}/`);
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={
              vertical
                ? cn(navRow, active ? navRowActive : navRowIdle)
                : cn(topLink, active ? topLinkActive : topLinkIdle)
            }
            href={item.href}
            key={item.href}
            onClick={() => setMobileOpen(false)}
          >
            <Icon aria-hidden="true" size={16} strokeWidth={1.7} />
            {t(item.labelKey)}
          </Link>
        );
      })}
      <Link
        aria-current={inSettings ? "page" : undefined}
        className={
          vertical
            ? cn(navRow, path === SETTINGS_HREF ? navRowActive : navRowIdle)
            : cn(topLink, inSettings ? topLinkActive : topLinkIdle)
        }
        href={SETTINGS_HREF}
        onClick={() => setMobileOpen(false)}
      >
        <Settings aria-hidden="true" size={16} strokeWidth={1.7} />
        {t("navSettings")}
      </Link>
    </>
  );

  const settingsRow = (href: string, label: string, icon: ReactNode) => {
    const active = path === href || path.startsWith(`${href}/`);
    return (
      <Link
        aria-current={active ? "page" : undefined}
        className={cn(
          navRow,
          active ? navRowActive : navRowIdle,
          collapsed && "lg:justify-center lg:px-2",
        )}
        href={href}
        key={href}
        onClick={() => setMobileOpen(false)}
        title={label}
      >
        {icon}
        <span className={cn("flex-1", collapsed && "lg:sr-only")}>{label}</span>
      </Link>
    );
  };
  const settingsNav = (
    <div className="space-y-5">
      {navSections.map((section) => {
        const entries = moreItems.filter((item) => item.section === section);
        if (!entries.length) return null;
        return (
          <div key={section}>
            <p className={cn(navHeading, collapsed && "lg:sr-only")}>
              {t(navSectionLabels[section])}
            </p>
            <div className="space-y-0.5">
              {entries.map((item) => {
                const Icon = item.icon;
                return settingsRow(
                  item.href,
                  t(item.labelKey),
                  <Icon aria-hidden="true" size={17} strokeWidth={1.7} />,
                );
              })}
            </div>
          </div>
        );
      })}
      {packLinks.length ? (
        <div>
          <p className={cn(navHeading, collapsed && "lg:sr-only")}>{t("sectionPacks")}</p>
          <div className="space-y-0.5">
            {packLinks.map((item) =>
              settingsRow(
                item.href,
                item.label,
                <ShieldCheck aria-hidden="true" size={17} strokeWidth={1.7} />,
              ),
            )}
          </div>
        </div>
      ) : null}
    </div>
  );

  const blocked = check === "failed" || check === "limited";
  return (
    <div className="flex h-dvh flex-col bg-[var(--background)] text-[var(--foreground)]">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-[var(--card)] focus:p-3"
      >
        {t("skipToContent")}
      </a>
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-4 md:px-5">
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
            <Dialog.Content className="console-sidebar fixed inset-y-0 left-0 z-50 flex w-[min(20rem,85vw)] flex-col overflow-y-auto bg-[var(--sidebar)] p-4 text-[var(--sidebar-foreground)] shadow-[var(--shadow)]">
              <Dialog.Title className="sr-only">{t("sidebar")}</Dialog.Title>
              <Dialog.Description className="sr-only">{t("primaryNavigation")}</Dialog.Description>
              <div className="mb-4 flex items-center justify-end">
                <Dialog.Close
                  aria-label={t("closeMenu")}
                  className="rounded-md p-2 hover:bg-[var(--sidebar-hover)]"
                >
                  <X size={18} />
                </Dialog.Close>
              </div>
              <div className="mb-5 space-y-0.5">{homeLinks(true)}</div>
              {settingsNav}
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
        {brand}
        <nav
          aria-label={t("primaryNavigation")}
          className="ml-3 hidden min-w-0 items-center gap-1 lg:flex"
        >
          {homeLinks(false)}
        </nav>
        <div className="min-w-0 flex-1" />
        {session?.permissions?.includes("chat:use") ? (
          <Button
            aria-label={`${t("newChat")} ⌘⇧O`}
            className="hidden h-9 gap-1.5 px-3 text-[13px] sm:inline-flex"
            onClick={newChat}
            type="button"
            variant="outline"
          >
            <Plus size={15} aria-hidden="true" />
            {t("newChat")}
          </Button>
        ) : null}
        {session?.permissions?.includes("agents:create") ? (
          <Button asChild className="hidden h-9 gap-1.5 px-3 text-[13px] md:inline-flex">
            <Link href="/agents/new">
              <Bot size={15} aria-hidden="true" />
              {t("createAgent")}
            </Link>
          </Button>
        ) : null}
        <CommandPalette commands={commands} />
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              className="flex shrink-0 items-center gap-2 rounded-lg p-1.5 hover:bg-[var(--muted)]"
              type="button"
            >
              <span
                aria-hidden="true"
                className="flex size-8 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--muted)] text-xs font-semibold"
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
      <div className="flex min-h-0 flex-1">
        {inSettings ? (
          <aside
            aria-label={t("navSettings")}
            className={cn(
              "console-sidebar hidden shrink-0 flex-col border-r border-[var(--sidebar-border)] bg-[var(--sidebar)] px-3 py-4 text-[var(--sidebar-foreground)] lg:flex",
              collapsed ? "w-[68px]" : "w-[232px]",
            )}
          >
            <nav aria-label={t("navSettings")} className="min-h-0 flex-1 overflow-y-auto">
              {settingsNav}
            </nav>
            <button
              aria-label={collapsed ? t("expand") : t("collapse")}
              className="mt-3 flex min-h-10 items-center gap-2 rounded-md px-3 py-2 text-xs text-[var(--sidebar-muted)] hover:bg-[var(--sidebar-hover)] hover:text-[var(--sidebar-strong)]"
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
        ) : null}
        <main
          id="main-content"
          tabIndex={-1}
          className={cn(
            "relative min-h-0 min-w-0 flex-1",
            flush ? "overflow-hidden" : "overflow-auto",
          )}
        >
          {blocked ? (
            <div className="mx-auto w-full max-w-xl p-5 md:p-10">
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
                <div role="alert">
                  <h1 className="font-display text-2xl tracking-tight">
                    {check === "limited" ? t("rateLimitTitle") : t("sessionProblemTitle")}
                  </h1>
                  <p className="mt-3 text-[15px] leading-relaxed text-[var(--muted-foreground)]">
                    {check === "limited" ? t("rateLimitBody") : t("sessionProblemBody")}
                  </p>
                </div>
                <div className="mt-6 flex flex-wrap gap-2">
                  <Button onClick={() => checkSession()}>{t("sessionRetry")}</Button>
                  {check === "failed" ? (
                    <Button asChild variant="outline">
                      <a href="/login">{t("sessionSignIn")}</a>
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>
          ) : (
            <ShellNavContext.Provider value={shellNav}>
              {flush ? (
                children
              ) : (
                <div className="mx-auto w-full max-w-7xl p-5 md:p-8">{children}</div>
              )}
            </ShellNavContext.Provider>
          )}
        </main>
      </div>
    </div>
  );
}
