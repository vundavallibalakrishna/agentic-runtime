import { getTranslations } from "next-intl/server";

import { AppShell } from "@/components/app-shell";
import { PermissionGate } from "@/components/permission-gate";
import { UsersPanel } from "@/components/users-panel";

export default async function UsersPage() {
  const shell = await getTranslations("shell");
  const admin = await getTranslations("admin");
  return (
    <AppShell extraLinks={[{ href: "/admin/users", label: shell("navUsers") }]}>
      <h1 className="mb-4 text-2xl font-semibold">{admin("usersTitle")}</h1>
      <PermissionGate allowed>
        <UsersPanel status="empty" users={[]} />
      </PermissionGate>
    </AppShell>
  );
}
