"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export type UserRow = {
  id: string;
  email: string;
  displayName: string;
  status?: string;
};

const STATUS_LABEL: Record<string, "statusActive" | "statusSuspended" | "statusInvited"> = {
  active: "statusActive",
  suspended: "statusSuspended",
  invited: "statusInvited",
};

/**
 * The people of the workspace. With `onStatus`, each person other than the viewer has
 * Suspend or Let back in; suspending asks first, because it signs the person out at once.
 */
export function UsersPanel({
  status,
  users,
  selfId,
  onStatus,
  onRetry,
}: {
  status: "loading" | "empty" | "error" | "ready";
  users: UserRow[];
  selfId?: string;
  onStatus?: (user: UserRow, next: "active" | "suspended") => Promise<void>;
  onRetry?: () => void;
}) {
  const t = useTranslations("admin");
  const [asking, setAsking] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  if (status === "loading") {
    return (
      <div className="p-3">
        <span className="sr-only">{t("loading")}</span>
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }
  if (status === "error") {
    return (
      <p className="p-3 text-sm text-[var(--destructive)]" role="alert">
        {t("error")}{" "}
        {onRetry ? (
          <Button onClick={onRetry} type="button" variant="outline">
            {t("retry")}
          </Button>
        ) : null}
      </p>
    );
  }
  if (status === "empty" || users.length === 0) {
    return <p className="p-3 text-sm text-[var(--muted-foreground)]">{t("empty")}</p>;
  }

  async function change(user: UserRow, next: "active" | "suspended") {
    if (!onStatus) return;
    setBusy(user.id);
    setError("");
    try {
      await onStatus(user, next);
      setAsking("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("changeError"));
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
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{t("usersTitle")}</caption>
        <thead className="text-[var(--muted-foreground)]">
          <tr>
            <th className="p-3 font-medium">{t("name")}</th>
            <th className="p-3 font-medium">{t("email")}</th>
            <th className="p-3 font-medium">{t("status")}</th>
            {onStatus ? <th className="p-3 text-right font-medium">{t("actions")}</th> : null}
          </tr>
        </thead>
        <tbody>
          {users.map((user) => {
            const word = user.status ?? "active";
            const label = STATUS_LABEL[word];
            const self = user.id === selfId;
            return (
              <tr className="border-t border-[var(--border)]" key={user.id}>
                <td className="p-3">
                  {user.displayName}
                  {self ? (
                    <span className="ml-2 text-[var(--muted-foreground)]">({t("you")})</span>
                  ) : null}
                </td>
                <td className="p-3">{user.email}</td>
                <td className="p-3">
                  <Badge tone={statusTone(word)}>{label ? t(label) : word}</Badge>
                </td>
                {onStatus ? (
                  <td className="p-3 text-right">
                    {self ? null : word === "suspended" ? (
                      <Button
                        aria-label={t("reactivateNamed", { name: user.displayName })}
                        disabled={busy === user.id}
                        onClick={() => void change(user, "active")}
                        type="button"
                        variant="outline"
                      >
                        {t("reactivate")}
                      </Button>
                    ) : asking === user.id ? (
                      <span className="inline-flex flex-wrap items-center justify-end gap-2">
                        <span className="max-w-sm text-left text-[var(--muted-foreground)]">
                          {t("suspendAsk", { name: user.displayName })}
                        </span>
                        <Button
                          disabled={busy === user.id}
                          onClick={() => void change(user, "suspended")}
                          type="button"
                        >
                          {t("suspendConfirm")}
                        </Button>
                        <Button onClick={() => setAsking("")} type="button" variant="outline">
                          {t("cancel")}
                        </Button>
                      </span>
                    ) : (
                      <Button
                        aria-label={t("suspendNamed", { name: user.displayName })}
                        onClick={() => setAsking(user.id)}
                        type="button"
                        variant="outline"
                      >
                        {t("suspend")}
                      </Button>
                    )}
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
