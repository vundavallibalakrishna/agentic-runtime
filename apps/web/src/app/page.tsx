import { healthzHealthzGet } from "@ar/api-client";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/app-shell";
import { ThemeToggle } from "@/components/theme-toggle";
import { Card } from "@/components/ui/card";

export default async function HomePage() {
  const t = await getTranslations("shell");
  return (
    <AppShell>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("product")}</h1>
        <ThemeToggle />
      </div>
      <Card>
        <p>{t("empty")}</p>
        <p className="sr-only">API {healthzHealthzGet.name}</p>
      </Card>
    </AppShell>
  );
}
