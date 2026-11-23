"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { AuthCard, AuthFooterLink } from "@/components/auth-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

/** Choose a new password with the token a reset mail carried. */
export function ResetPasswordForm({ token }: { token: string }) {
  const t = useTranslations("auth");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (password !== again) {
      setError(t("resetMismatch"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api("/api/v1/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({ token, password }),
      });
      setDone(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("resetFailed"));
    } finally {
      setBusy(false);
    }
  }

  const footer = <AuthFooterLink href="/login">{t("title")}</AuthFooterLink>;
  if (!token) {
    return (
      <AuthCard body={t("resetBody")} footer={footer} title={t("resetTitle")}>
        <p className="rounded-lg bg-[var(--muted)] px-3 py-2 text-center text-sm" role="alert">
          {t("resetNoToken")}{" "}
          <AuthFooterLink href="/forgot-password">{t("resetAskAgain")}</AuthFooterLink>
        </p>
      </AuthCard>
    );
  }
  return (
    <AuthCard body={t("resetBody")} footer={footer} title={t("resetTitle")}>
      {done ? (
        <p className="rounded-lg bg-[var(--muted)] px-3 py-2 text-center text-sm" role="status">
          {t("resetDone")}
        </p>
      ) : (
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <div className="space-y-1.5">
            <label className="block text-sm font-medium" htmlFor="new-password">
              {t("resetNew")}
            </label>
            <Input
              autoComplete="new-password"
              id="new-password"
              minLength={8}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm font-medium" htmlFor="new-password-again">
              {t("resetAgain")}
            </label>
            <Input
              autoComplete="new-password"
              id="new-password-again"
              minLength={8}
              onChange={(event) => setAgain(event.target.value)}
              required
              type="password"
              value={again}
            />
          </div>
          {error ? (
            <p className="text-sm text-[var(--destructive)]" role="alert">
              {error} <AuthFooterLink href="/forgot-password">{t("resetAskAgain")}</AuthFooterLink>
            </p>
          ) : null}
          <Button className="h-10 w-full" disabled={busy} type="submit">
            {t("resetSubmit")}
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
