"use client";

import { useTranslations } from "next-intl";

export type UserRow = {
  id: string;
  email: string;
  displayName: string;
};

export function UsersPanel({
  status,
  users,
}: {
  status: "loading" | "empty" | "error" | "ready";
  users: UserRow[];
}) {
  const t = useTranslations("admin");
  if (status === "loading") {
    return <p>{t("loading")}</p>;
  }
  if (status === "error") {
    return <p role="alert">{t("error")}</p>;
  }
  if (status === "empty" || users.length === 0) {
    return <p>{t("empty")}</p>;
  }
  return (
    <table className="w-full text-left text-sm">
      <caption className="sr-only">{t("usersTitle")}</caption>
      <thead className="text-[var(--muted-foreground)]">
        <tr>
          <th className="p-3 font-medium">{t("usersTitle")}</th>
          <th className="p-3 font-medium">Email</th>
        </tr>
      </thead>
      <tbody>
        {users.map((user) => (
          <tr className="border-t border-[var(--border)]" key={user.id}>
            <td className="p-3">{user.displayName}</td>
            <td className="p-3">{user.email}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
