import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";

export default async function SelectTenantPage() {
  const t = await getTranslations("select");
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center p-6">
      <h1 className="font-serif text-3xl tracking-tight">{t("title")}</h1>
      <p className="mt-2 text-[var(--muted-foreground)]">{t("body")}</p>
      <Button asChild className="mt-6">
        <a href="/api/v1/auth/login?tenant=dev">{t("continue")}</a>
      </Button>
    </main>
  );
}
