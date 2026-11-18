"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { AuthCard, AuthFooterLink } from "@/components/auth-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const t = useTranslations("auth");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await api("/api/v1/auth/password-reset", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setSent(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      body={t("forgotBody")}
      footer={<AuthFooterLink href="/login">{t("title")}</AuthFooterLink>}
      title={t("forgotTitle")}
    >
      {sent ? (
        <p className="rounded-lg bg-[var(--muted)] px-3 py-2 text-center text-sm" role="status">
          {t("forgotSent")}
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
            <label className="block text-sm font-medium" htmlFor="reset-email">
              {t("emailLabel")}
            </label>
            <Input
              autoComplete="username"
              id="reset-email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </div>
          <Button className="h-10 w-full" disabled={busy} type="submit">
            {t("forgotSubmit")}
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
