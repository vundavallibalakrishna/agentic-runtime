"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime } from "@/lib/format";

export type UserRow = {
  id: string;
  email: string;
  displayName: string;
  status: string;
  lastLoginAt: string | null;
};

export type UserStatusChange = (user: UserRow, next: "active" | "suspended") => Promise<void>;

const STATUS_LABEL: Record<string, "statusActive" | "statusSuspended" | "statusInvited"> = {
  active: "statusActive",
  suspended: "statusSuspended",
  invited: "statusInvited",
};

/** The words for an account status; a status the product has no label for shows as returned. */
export function useStatusLabel(): (status: string) => string {
  const t = useTranslations("admin");
  return (status) => {
    const label = STATUS_LABEL[status];
    return label ? t(label) : status;
  };
}

/**
 * Presentation of the current page; directory reads, states and filters stay with its caller.
 * With `onStatus`, each person other than the viewer has Suspend or Let back in; suspending
 * asks first, because it signs the person out at once.
 */
export function UsersPanel({
  users,
  selfId,
  onStatus,
}: {
  users: UserRow[];
  selfId?: string;
  onStatus?: UserStatusChange;
}) {
  const t = useTranslations("directory");
  const admin = useTranslations("admin");
  const statusLabel = useStatusLabel();
  const locale = useLocale();
  const [asking, setAsking] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function change(user: UserRow, next: "active" | "suspended") {
    if (!onStatus) return;
    setBusy(user.id);
    setError("");
    try {
      await onStatus(user, next);
      setAsking("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : admin("changeError"));
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      {error ? (
        <p className="p-3 text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      <Table className="min-w-[640px] text-left">
        <caption className="sr-only">{t("table")}</caption>
        <TableHeader>
          <TableRow>
            <TableHead scope="col">{t("person")}</TableHead>
            <TableHead scope="col">{t("email")}</TableHead>
            <TableHead scope="col">{t("status")}</TableHead>
            <TableHead scope="col">{t("lastSignIn")}</TableHead>
            {onStatus ? (
              <TableHead className="text-right" scope="col">
                {admin("actions")}
              </TableHead>
            ) : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((user) => {
            const name = user.displayName.trim() || user.email;
            const self = user.id === selfId;
            return (
              <TableRow key={user.id}>
                <TableCell className="max-w-xs break-words font-medium">
                  {name}
                  {self ? (
                    <span className="ml-2 font-normal text-[var(--muted-foreground)]">
                      ({admin("you")})
                    </span>
                  ) : null}
                </TableCell>
                <TableCell className="max-w-xs break-all">{user.email}</TableCell>
                <TableCell>
                  <Badge tone={statusTone(user.status)}>{statusLabel(user.status)}</Badge>
                </TableCell>
                <TableCell className="min-w-36 max-w-xs">
                  {user.lastLoginAt ? (
                    <time dateTime={user.lastLoginAt}>
                      {formatDateTime(user.lastLoginAt, locale)}
                    </time>
                  ) : (
                    <span className="text-[var(--muted-foreground)]">{t("noSignIn")}</span>
                  )}
                </TableCell>
                {onStatus ? (
                  <TableCell className="text-right">
                    {self ? null : user.status === "suspended" ? (
                      <Button
                        aria-label={admin("reactivateNamed", { name })}
                        disabled={busy === user.id}
                        onClick={() => void change(user, "active")}
                        type="button"
                        variant="outline"
                      >
                        {admin("reactivate")}
                      </Button>
                    ) : asking === user.id ? (
                      <span className="inline-flex flex-wrap items-center justify-end gap-2">
                        <span className="max-w-sm text-left text-[var(--muted-foreground)]">
                          {admin("suspendAsk", { name })}
                        </span>
                        <Button
                          disabled={busy === user.id}
                          onClick={() => void change(user, "suspended")}
                          type="button"
                        >
                          {admin("suspendConfirm")}
                        </Button>
                        <Button onClick={() => setAsking("")} type="button" variant="outline">
                          {admin("cancel")}
                        </Button>
                      </span>
                    ) : (
                      <Button
                        aria-label={admin("suspendNamed", { name })}
                        onClick={() => setAsking(user.id)}
                        type="button"
                        variant="outline"
                      >
                        {admin("suspend")}
                      </Button>
                    )}
                  </TableCell>
                ) : null}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </>
  );
}
