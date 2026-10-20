"use client";

import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

export function PermissionGate({ allowed, children }: { allowed: boolean; children: ReactNode }) {
  const t = useTranslations("admin");
  if (!allowed) {
    return <p role="alert">{t("forbidden")}</p>;
  }
  return children;
}
