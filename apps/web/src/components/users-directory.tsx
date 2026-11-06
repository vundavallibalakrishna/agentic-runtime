"use client";

import { useEffect, useState } from "react";

import { type UserRow, UsersPanel } from "@/components/users-panel";
import { api } from "@/lib/api";

export function UsersDirectory() {
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
    <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <UsersPanel status={status} users={users} />
    </div>
  );
}
