import { healthzHealthzGet } from "@ar/api-client";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { AppShell } from "@/components/app-shell";
import { ThemeToggle } from "@/components/theme-toggle";
import { Card } from "@/components/ui/card";

export default async function HomePage() {
  const t = await getTranslations("shell");
  return (
    <AppShell>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-medium tracking-tight">{t("product")}</h1>
        <ThemeToggle />
      </div>
      <Card>
        <p>{t("empty")}</p>
        <Link
          className="mt-4 inline-flex items-center justify-center rounded-lg bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)]"
          href="/agents/new"
          prefetch={false}
        >
          {t("createAgent")}
        </Link>
        <p className="sr-only">API {healthzHealthzGet.name}</p>
      </Card>
    </AppShell>
  );
}
