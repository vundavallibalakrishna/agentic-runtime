import { getTranslations } from "next-intl/server";

import { ComingSoon } from "@/components/coming-soon";

export default async function KnowledgePage() {
  const t = await getTranslations("shell");
  return <ComingSoon title={t("navKnowledge")} />;
}
