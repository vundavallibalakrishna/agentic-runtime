import { getTranslations } from "next-intl/server";

import { AppShell } from "@/components/app-shell";
import { BackButton } from "@/components/common/detail-state";
import { HealthReport } from "@/components/health-report";
import { PageHeader } from "@/components/page-header";

export default async function PlatformHealthPage() {
  const t = await getTranslations("platform");
  return (
    <AppShell>
      <PageHeader
        body={t("healthBody")}
        title={t("healthTitle")}
        actions={<BackButton href="/chat">{t("back")}</BackButton>}
      />
      <HealthReport />
    </AppShell>
  );
}
