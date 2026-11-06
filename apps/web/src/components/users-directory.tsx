"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { TableScroll } from "@/components/ui/table";
import { type UserRow, UsersPanel } from "@/components/users-panel";
import { api } from "@/lib/api";

export function UsersDirectory() {
  const t = useTranslations("admin");
  const [status, setStatus] = useState<"loading" | "empty" | "error" | "ready">("loading");
  const [users, setUsers] = useState<UserRow[]>([]);

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
        setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <TableScroll
      className="rounded-xl border border-[var(--border)] bg-[var(--card)]"
      label={t("usersTitle")}
    >
      <UsersPanel status={status} users={users} />
    </TableScroll>
  );
}
