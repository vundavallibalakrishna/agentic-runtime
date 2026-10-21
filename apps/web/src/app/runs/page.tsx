import { getTranslations } from "next-intl/server";

import { ComingSoon } from "@/components/coming-soon";

export default async function RunsPage() {
  const t = await getTranslations("shell");
  return <ComingSoon title={t("navRuns")} />;
}
