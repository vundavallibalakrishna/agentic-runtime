"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { type UserRow, UsersPanel } from "@/components/users-panel";
import { api } from "@/lib/api";

const seeded: UserRow[] = [
  { id: "admin", email: "admin@dev.local", displayName: "Dev Admin" },
  { id: "builder", email: "builder@dev.local", displayName: "Dev Builder" },
  { id: "member", email: "member@dev.local", displayName: "Dev Member" },
  { id: "approver", email: "approver@dev.local", displayName: "Dev Approver" },
];

export function UsersDirectory() {
  const t = useTranslations("admin");
  const [status, setStatus] = useState<"loading" | "empty" | "error" | "ready">("loading");
  const [users, setUsers] = useState<UserRow[]>([]);
  const [seededView, setSeededView] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const body = await api<{ items?: UserRow[] } | UserRow[]>("/api/v1/users");
        const rows = Array.isArray(body) ? body : (body.items ?? []);
        const mapped = rows.map((row) => {
          const extra = row as UserRow & { display_name?: string };
          return {
            id: String(row.id),
            email: row.email,
            displayName: extra.displayName || extra.display_name || row.email,
          };
        });
        if (cancelled) {
          return;
        }
        setUsers(mapped);
        setStatus(mapped.length === 0 ? "empty" : "ready");
      } catch {
        if (cancelled) {
          return;
        }
        setUsers(seeded);
        setSeededView(true);
        setStatus("ready");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      {seededView ? (
        <p className="mb-3 text-sm text-[var(--muted-foreground)]">{t("seedNote")}</p>
      ) : null}
      <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <UsersPanel status={status} users={users} />
      </div>
    </div>
  );
}
