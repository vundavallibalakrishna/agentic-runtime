"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";

function safeReturnTo(value: string | null): string {
  // Only allow a local path, never an absolute URL, to avoid an open redirect.
  if (value && value.startsWith("/") && !value.startsWith("//")) {
    return value;
  }
  return "/";
}

export default function LoginPage() {
  const t = useTranslations("auth");
  const shell = useTranslations("shell");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signIn() {
    setError(null);
    setBusy(true);
    // Read return_to from the URL at submit time (client only), so the page needs no
    // useSearchParams() and can be statically prerendered.
    const returnTo = safeReturnTo(new URLSearchParams(window.location.search).get("return_to"));
    try {
      await api("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      // Full navigation so the session cookie is seen by the proxy session gate.
      window.location.assign(returnTo);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 429) {
        setError(t("errorThrottled"));
      } else if (caught instanceof ApiError && caught.status === 401) {
        setError(t("errorCredentials"));
      } else {
        setError(t("errorGeneric"));
      }
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center px-6 py-16">
      <div className="w-full max-w-[22rem]">
        <p className="text-sm font-medium tracking-tight">{shell("product")}</p>
        <h1 className="mt-10 font-serif text-[2.5rem] leading-none tracking-tight">{t("title")}</h1>
        <p className="mt-4 text-[15px] leading-relaxed text-[var(--muted-foreground)]">
          {t("body")}
        </p>
        <form
          className="mt-8 space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            void signIn();
          }}
        >
          <div className="space-y-1.5">
            <label className="block text-sm font-medium" htmlFor="email">
              {t("emailLabel")}
            </label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm font-medium" htmlFor="password">
              {t("passwordLabel")}
            </label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>
          {error ? (
            <p
              className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-[var(--destructive)]"
              role="alert"
            >
              {error}
            </p>
          ) : null}
          <Button type="submit" className="h-10 w-full" disabled={busy}>
            {busy ? t("signingIn") : t("submit")}
          </Button>
        </form>
      </div>
    </main>
  );
}
