import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

/**
 * The one frame for every signed-out page (sign in, password reset, workspace choice,
 * guest access): a centred card with the product mark, a title and a line of help.
 * `footer` sits under the card, for the link that leads to a neighbouring page.
 */
export function AuthCard({
  title,
  body,
  children,
  footer,
  wide = false,
}: {
  title: string;
  body?: string;
  children?: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const shell = useTranslations("shell");
  const product = shell("product");
  return (
    <main className="flex min-h-dvh items-center justify-center bg-[var(--background)] px-6 py-12">
      <div className={wide ? "w-full max-w-lg" : "w-full max-w-[25rem]"}>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-8 shadow-[var(--shadow)] sm:p-9">
          <div className="flex flex-col items-center text-center">
            <div
              aria-hidden
              className="flex size-11 items-center justify-center rounded-xl bg-[var(--primary)] font-display text-lg font-semibold text-[var(--primary-foreground)]"
            >
              {product.charAt(0)}
            </div>
            <p className="mt-4 text-sm font-medium tracking-tight text-[var(--muted-foreground)]">
              {product}
            </p>
            <h1 className="mt-2 font-display text-2xl leading-tight tracking-tight">{title}</h1>
            {body ? (
              <p className="mt-2 text-sm leading-relaxed text-[var(--muted-foreground)]">{body}</p>
            ) : null}
          </div>
          {children ? <div className="mt-7">{children}</div> : null}
        </div>
        {footer ? (
          <div className="mt-6 text-center text-sm text-[var(--muted-foreground)]">{footer}</div>
        ) : null}
      </div>
    </main>
  );
}

/** The link under an auth card. */
export function AuthFooterLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      className="font-medium text-[var(--foreground)] underline-offset-4 hover:underline"
      href={href}
    >
      {children}
    </a>
  );
}

/** A problem shown inside an auth card. */
export function AuthAlert({ children }: { children: ReactNode }) {
  return (
    <p
      className="rounded-lg border border-[var(--border)] bg-[var(--muted)] px-3 py-2 text-sm text-[var(--destructive)]"
      role="alert"
    >
      {children}
    </p>
  );
}
