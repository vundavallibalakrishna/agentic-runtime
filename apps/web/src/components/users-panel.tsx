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
    <table>
      <tbody>
        {users.map((user) => (
          <tr key={user.id}>
            <td>{user.displayName}</td>
            <td>{user.email}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
