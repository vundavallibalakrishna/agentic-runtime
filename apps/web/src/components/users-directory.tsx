"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { TableScroll } from "@/components/ui/table";
import { type UserRow, UsersPanel } from "@/components/users-panel";
import { api } from "@/lib/api";

type Session = { user?: { id?: string }; permissions?: string[] };

export function UsersDirectory() {
  const t = useTranslations("admin");
  const [status, setStatus] = useState<"loading" | "empty" | "error" | "ready">("loading");
  const [users, setUsers] = useState<UserRow[]>([]);
  const [session, setSession] = useState<Session>({});

  const load = useCallback(async () => {
    try {
      const [body, who] = await Promise.all([
        api<{ items?: UserRow[] }>("/api/v1/users"),
        api<Session>("/api/v1/auth/session"),
      ]);
      const rows = (body.items ?? []).map((row) => ({
        id: String(row.id),
        email: row.email,
        displayName: row.displayName || row.email,
        status: row.status,
      }));
      setSession(who);
      setUsers(rows);
      setStatus(rows.length === 0 ? "empty" : "ready");
    } catch {
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Suspending needs users:manage. Someone who may only read the list sees no actions.
  const manage = session.permissions?.includes("users:manage") ?? false;

  async function change(user: UserRow, next: "active" | "suspended") {
    await api(`/api/v1/users/${user.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: next }),
    });
    await load();
  }

  return (
    <TableScroll
      className="rounded-xl border border-[var(--border)] bg-[var(--card)]"
      label={t("usersTitle")}
    >
      <UsersPanel
        onRetry={() => {
          setStatus("loading");
          void load();
        }}
        onStatus={manage ? change : undefined}
        selfId={session.user?.id}
        status={status}
        users={users}
      />
    </TableScroll>
  );
}
