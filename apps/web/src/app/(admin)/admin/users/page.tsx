import { getTranslations } from "next-intl/server";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { PermissionGate } from "@/components/permission-gate";
import { UsersDirectory } from "@/components/users-directory";

export default async function UsersPage() {
  const admin = await getTranslations("admin");
  return (
    <AppShell>
      <PageHeader body={admin("seedNote")} title={admin("usersTitle")} />
      <PermissionGate allowed>
        <UsersDirectory />
      </PermissionGate>
    </AppShell>
  );
}
