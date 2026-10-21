import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";

const seeded = [
  "admin@dev.local",
  "builder@dev.local",
  "member@dev.local",
  "approver@dev.local",
] as const;

const errors: Record<string, "errorTenant" | "errorUnknown" | "errorState" | "errorGeneric"> = {
  tenant_not_found: "errorTenant",
  unknown_user: "errorUnknown",
  invalid_state: "errorState",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const t = await getTranslations("auth");
  const shell = await getTranslations("shell");
  const params = await searchParams;
  const errorKey = params.error ? (errors[params.error] ?? "errorGeneric") : null;

  return (
    <main className="flex min-h-dvh items-center justify-center px-6 py-16">
      <div className="w-full max-w-[22rem]">
        <p className="text-sm font-medium tracking-tight">{shell("product")}</p>
        <h1 className="mt-10 font-serif text-[2.5rem] leading-none tracking-tight">{t("title")}</h1>
        <p className="mt-4 text-[15px] leading-relaxed text-[var(--muted-foreground)]">
          {t("body")}
        </p>
        {errorKey ? (
          <p
            className="mt-6 rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
            role="alert"
          >
            {t(errorKey)}
          </p>
        ) : null}
        <Button asChild className="mt-8 h-10 w-full">
          <a href="/api/v1/auth/login">{t("continue")}</a>
        </Button>
        <div className="my-8 h-px bg-[var(--border)]" />
        <h2 className="text-[13px] text-[var(--muted-foreground)]">{t("devHeading")}</h2>
        <div className="mt-2">
          {seeded.map((email) => (
            <form action="/api/v1/auth/dev-login" key={email} method="post">
              <input name="email" type="hidden" value={email} />
              <Button
                className="h-9 w-full justify-start px-2 font-normal"
                type="submit"
                variant="ghost"
              >
                {t("devLoginAs", { email })}
              </Button>
            </form>
          ))}
        </div>
        <p className="mt-4 text-xs leading-relaxed text-[var(--muted-foreground)]">
          {t("passwordHint")}
        </p>
      </div>
    </main>
  );
}
