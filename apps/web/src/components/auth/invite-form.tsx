"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { AuthCard, AuthFooterLink } from "@/components/auth-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Invitation = { email: string; tenantName: string };

/** Accept a mailed invitation: choose a name and a password, and the account is made. */
export function InviteForm({ token }: { token: string }) {
  const t = useTranslations("auth");
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [refused, setRefused] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    let current = true;
    api<Invitation>("/api/v1/auth/invitation", {
      method: "POST",
      body: JSON.stringify({ token }),
    })
      .then((found) => {
        if (current) setInvitation(found);
      })
      .catch((caught: unknown) => {
        if (current) setRefused(caught instanceof Error ? caught.message : t("inviteFailed"));
      });
    return () => {
      current = false;
    };
  }, [token, t]);

  async function submit() {
    if (password !== again) {
      setError(t("resetMismatch"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api("/api/v1/auth/invitation/accept", {
        method: "POST",
        body: JSON.stringify({ token, displayName: name, password }),
      });
      setDone(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("inviteFailed"));
    } finally {
      setBusy(false);
    }
  }

  const footer = <AuthFooterLink href="/login">{t("title")}</AuthFooterLink>;
  const body = invitation?.tenantName
    ? t("inviteBodyFor", { tenant: invitation.tenantName })
    : t("inviteBody");
  if (!token || refused) {
    return (
      <AuthCard body={t("inviteBody")} footer={footer} title={t("inviteTitle")}>
        <p className="rounded-lg bg-[var(--muted)] px-3 py-2 text-center text-sm" role="alert">
          {refused || t("inviteNoToken")}
        </p>
      </AuthCard>
    );
  }
  if (done) {
    return (
      <AuthCard body={body} footer={footer} title={t("inviteTitle")}>
        <p className="rounded-lg bg-[var(--muted)] px-3 py-2 text-center text-sm" role="status">
          {t("inviteDone")}
        </p>
      </AuthCard>
    );
  }
  if (!invitation) {
    return (
      <AuthCard body={t("inviteBody")} footer={footer} title={t("inviteTitle")}>
        <div aria-busy="true" className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      </AuthCard>
    );
  }
  return (
    <AuthCard body={body} footer={footer} title={t("inviteTitle")}>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <div className="space-y-1.5">
          <label className="block text-sm font-medium" htmlFor="invite-email">
            {t("emailLabel")}
          </label>
          <Input autoComplete="username" id="invite-email" readOnly value={invitation.email} />
        </div>
        <div className="space-y-1.5">
          <label className="block text-sm font-medium" htmlFor="invite-name">
            {t("inviteName")}
          </label>
          <Input
            autoComplete="name"
            id="invite-name"
            onChange={(event) => setName(event.target.value)}
            required
            value={name}
          />
        </div>
        <div className="space-y-1.5">
          <label className="block text-sm font-medium" htmlFor="invite-password">
            {t("invitePassword")}
          </label>
          <Input
            autoComplete="new-password"
            id="invite-password"
            minLength={8}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </div>
        <div className="space-y-1.5">
          <label className="block text-sm font-medium" htmlFor="invite-password-again">
            {t("invitePasswordAgain")}
          </label>
          <Input
            autoComplete="new-password"
            id="invite-password-again"
            minLength={8}
            onChange={(event) => setAgain(event.target.value)}
            required
            type="password"
            value={again}
          />
        </div>
        {error ? (
          <p className="text-sm text-[var(--destructive)]" role="alert">
            {error}
          </p>
        ) : null}
        <Button className="h-10 w-full" disabled={busy} type="submit">
          {t("inviteSubmit")}
        </Button>
      </form>
    </AuthCard>
  );
}
