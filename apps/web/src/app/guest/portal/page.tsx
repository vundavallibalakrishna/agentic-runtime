"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";

import { AuthCard } from "@/components/auth-card";
import { Button } from "@/components/ui/button";

export default function GuestRecordsPage() {
  const t = useTranslations("guestAccess");
  return (
    <AuthCard title={t("contentUnavailable")} body={t("contentAddressHelp")}>
      <div className="space-y-5">
        <p className="text-sm leading-relaxed text-[var(--muted-foreground)]">
          {t("contentHostHelp")}
        </p>
        <Button asChild className="h-10 w-full" variant="outline">
          <Link href="/guest">{t("backToAccess")}</Link>
        </Button>
      </div>
    </AuthCard>
  );
}
