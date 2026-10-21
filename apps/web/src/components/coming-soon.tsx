import { getTranslations } from "next-intl/server";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";

export async function ComingSoon({ title }: { title: string }) {
  const t = await getTranslations("soon");
  return (
    <AppShell>
      <PageHeader body={t("body")} title={title} />
      <Button asChild variant="outline">
        <a href="/chat">{t("back")}</a>
      </Button>
    </AppShell>
  );
}
