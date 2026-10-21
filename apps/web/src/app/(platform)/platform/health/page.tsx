import { getTranslations } from "next-intl/server";

import { AppShell } from "@/components/app-shell";
import { HealthReport } from "@/components/health-report";
import { PageHeader } from "@/components/page-header";

export default async function PlatformHealthPage() {
  const t = await getTranslations("platform");
  return (
    <AppShell>
      <PageHeader body={t("healthBody")} title={t("healthTitle")} />
      <HealthReport />
    </AppShell>
  );
}
