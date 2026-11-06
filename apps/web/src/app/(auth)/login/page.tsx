import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";

type ErrorKey =
  | "errorTenant"
  | "errorState"
  | "errorTenantSuspended"
  | "errorUserSuspended"
  | "errorGeneric";

const errors: Record<string, ErrorKey> = {
  tenant_not_found: "errorTenant",
  invalid_state: "errorState",
  tenant_suspended: "errorTenantSuspended",
  user_suspended: "errorUserSuspended",
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
      </div>
    </main>
  );
}
