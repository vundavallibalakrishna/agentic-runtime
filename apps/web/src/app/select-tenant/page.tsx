import { getTranslations } from "next-intl/server";

import { AuthCard } from "@/components/auth-card";
import { Button } from "@/components/ui/button";

export default async function SelectTenantPage() {
  const t = await getTranslations("select");
  return (
    <AuthCard body={t("body")} title={t("title")}>
      <Button asChild className="h-10 w-full">
        <a href="/login">{t("continue")}</a>
      </Button>
    </AuthCard>
  );
}
