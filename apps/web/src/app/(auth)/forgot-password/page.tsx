"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

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
    <main className="flex min-h-dvh items-center justify-center px-6 py-16">
      <div className="w-full max-w-[22rem]">
        <h1 className="font-serif text-4xl tracking-tight">{t("forgotTitle")}</h1>
        <p className="mt-4 text-[15px] text-[var(--muted-foreground)]">{t("forgotBody")}</p>
        {sent ? (
          <p className="mt-6 text-sm" role="status">
            {t("forgotSent")}
          </p>
        ) : (
          <form
            className="mt-8 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            <label className="block text-sm font-medium" htmlFor="reset-email">
              {t("emailLabel")}
              <Input
                className="mt-1"
                id="reset-email"
                onChange={(event) => setEmail(event.target.value)}
                required
                type="email"
                value={email}
              />
            </label>
            <Button className="h-10 w-full" disabled={busy} type="submit">
              {t("forgotSubmit")}
            </Button>
          </form>
        )}
        <p className="mt-6 text-sm">
          <a className="underline" href="/login">
            {t("title")}
          </a>
        </p>
      </div>
    </main>
  );
}
