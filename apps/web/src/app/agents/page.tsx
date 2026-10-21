import { getTranslations } from "next-intl/server";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { UiGallery } from "@/components/ui-gallery";

export default async function AgentsPage() {
  const t = await getTranslations("agents");
  return (
    <AppShell>
      <PageHeader body={t("body")} title={t("title")} />
      <details className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <summary className="cursor-pointer text-sm font-medium">{t("catalogue")}</summary>
        <div className="mt-4">
          <UiGallery />
        </div>
      </details>
    </AppShell>
  );
}
