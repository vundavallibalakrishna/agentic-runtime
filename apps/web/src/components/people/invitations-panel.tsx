"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Role = { key: string; name: string };
type Invitation = {
  id: string;
  email: string;
  roleKeys?: string[];
  expiresAt?: string;
  acceptedAt?: string | null;
  status?: string;
};
type Sent = Invitation & { token?: string; mail?: { result?: string; reason?: string } };

/** The addresses typed into the form: separated by commas, spaces or new lines. */
export function addressesOf(text: string): string[] {
  const found = text
    .split(/[\s,;]+/)
    .map((item) => item.trim().toLowerCase())
    .filter((item) => item.includes("@"));
  return [...new Set(found)];
}

/** Invite people to the workspace, and see who has not accepted yet. */
export function InvitationsPanel() {
  const t = useTranslations("people");
  const [roles, setRoles] = useState<Role[]>([]);
  const [role, setRole] = useState("member");
  const [pending, setPending] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState<Sent[]>([]);
  // Inviting needs users:manage. Someone who may only read the list is not shown the form.
  const [allowed, setAllowed] = useState(true);

  const load = useCallback(async () => {
    setLoadError("");
    try {
      const session = await api<{ permissions?: string[] }>("/api/v1/auth/session");
      if (!session.permissions?.includes("users:manage")) {
        setAllowed(false);
        return;
      }
      const [roleList, invitations] = await Promise.all([
        api<{ items?: Role[] }>("/api/v1/roles"),
        api<{ items?: Invitation[] }>("/api/v1/invitations"),
      ]);
      setRoles(roleList.items ?? []);
      setPending((invitations.items ?? []).filter((row) => row.status === "pending"));
    } catch (caught) {
      setLoadError(caught instanceof Error ? caught.message : t("loadError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const emails = addressesOf(text);

  async function invite() {
    setBusy(true);
    setError("");
    setSent([]);
    try {
      const made = await api<Sent[]>("/api/v1/invitations", {
        method: "POST",
        body: JSON.stringify({ emails, roleKeys: [role] }),
      });
      setSent(made);
      setText("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("inviteError"));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/invitations/${id}`, { method: "DELETE" });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("revokeError"));
    } finally {
      setBusy(false);
    }
  }

  if (!allowed) return null;
  return (
    <section className="mt-8 space-y-6" aria-labelledby="invite-title">
      <fieldset className="detail-panel min-w-0" disabled={busy}>
        <h2 className="panel-title" id="invite-title">
          {t("inviteTitle")}
        </h2>
        <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("inviteBody")}</p>
        <label className="mt-4 block text-sm" htmlFor="invite-emails">
          {t("emails")}
        </label>
        <textarea
          className="mt-1 min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
          id="invite-emails"
          onChange={(event) => setText(event.target.value)}
          placeholder={t("emailsPlaceholder")}
          value={text}
        />
        <label className="mt-3 block text-sm" htmlFor="invite-role">
          {t("role")}
        </label>
        <select
          className="mt-1 max-w-md rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 text-sm"
          id="invite-role"
          onChange={(event) => setRole(event.target.value)}
          value={role}
        >
          {(roles.length > 0 ? roles : [{ key: role, name: role }]).map((item) => (
            <option key={item.key} value={item.key}>
              {item.name}
            </option>
          ))}
        </select>
        <div className="mt-4">
          <Button
            disabled={busy || emails.length === 0}
            onClick={() => void invite()}
            type="button"
          >
            {t("invite", { count: emails.length })}
          </Button>
        </div>
        {error ? (
          <p className="mt-3 text-sm text-[var(--destructive)]" role="alert">
            {error}
          </p>
        ) : null}
        {sent.length > 0 ? (
          <ul className="mt-4 space-y-2 text-sm" aria-label={t("sentTitle")}>
            {sent.map((row) => {
              const mailed = row.mail?.result === "sent";
              return (
                <li key={row.id}>
                  <span className="font-medium">{row.email}</span>{" "}
                  <Badge tone={mailed ? "success" : "warning"}>
                    {mailed ? t("mailSent") : t("mailNotSent")}
                  </Badge>
                  {mailed || !row.token ? null : (
                    <span className="mt-1 block text-[var(--muted-foreground)]">
                      {row.mail?.reason} {t("passLink")}{" "}
                      <span className="break-all font-mono text-xs">
                        {`${window.location.origin}/invite?token=${row.token}`}
                      </span>
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        ) : null}
      </fieldset>

      <div>
        <h2 className="panel-title mb-3">{t("pendingTitle")}</h2>
        {loading ? <Skeleton className="h-12 w-full" /> : null}
        {loadError ? (
          <p className="text-sm text-[var(--destructive)]" role="alert">
            {loadError}{" "}
            <Button onClick={() => void load()} type="button" variant="outline">
              {t("retry")}
            </Button>
          </p>
        ) : null}
        {!loading && !loadError && pending.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("pendingEmpty")}</p>
        ) : null}
        <ul className="row-list">
          {pending.map((row) => (
            <li
              className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-sm"
              key={row.id}
            >
              <span className="font-medium">{row.email}</span>
              <span className="text-[var(--muted-foreground)]">
                {(row.roleKeys ?? []).join(", ")}
              </span>
              {row.expiresAt ? (
                <span className="tabular-nums text-[var(--muted-foreground)]">
                  {t("expires", { when: new Date(row.expiresAt).toLocaleDateString() })}
                </span>
              ) : null}
              <Button
                className="ml-auto"
                disabled={busy}
                onClick={() => void revoke(row.id)}
                type="button"
                variant="outline"
              >
                {t("revoke")}
              </Button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
