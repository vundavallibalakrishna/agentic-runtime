"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

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
  const [method, setMethod] = useState("password");
  const [loginUrl, setLoginUrl] = useState("/api/v1/auth/oidc/start");
  const [tenants, setTenants] = useState<{ id: string; name: string }[]>([]);
  const [tenantId, setTenantId] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("error") === "mfa") {
      setError(t("errorMfa"));
    }
    void fetch("/api/v1/meta")
      .then((response) => response.json())
      .then((body: { auth?: { method?: string; loginUrl?: string } }) => {
        if (body.auth?.method === "oidc") {
          setMethod("oidc");
        }
        if (body.auth?.loginUrl) {
          setLoginUrl(body.auth.loginUrl);
        }
      })
      .catch(() => undefined);
  }, [t]);

  async function signIn() {
    setError(null);
    setBusy(true);
    // Read return_to from the URL at submit time (client only), so the page needs no
    // useSearchParams() and can be statically prerendered.
    const returnTo = safeReturnTo(new URLSearchParams(window.location.search).get("return_to"));
    try {
      const signed = await api<{
        ok?: boolean;
        chooseTenant?: boolean;
        tenants?: { id: string; name: string }[];
      }>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password, tenantId: tenantId || undefined }),
      });
      if (signed.chooseTenant && signed.tenants && signed.tenants.length > 1 && !tenantId) {
        setTenants(signed.tenants);
        setBusy(false);
        return;
      }
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
          {method === "oidc" ? t("oidcBody") : t("body")}
        </p>
        {error && method === "oidc" ? (
          <p
            className="mt-8 rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-[var(--destructive)]"
            role="alert"
          >
            {error}
          </p>
        ) : null}
        {method === "oidc" ? (
          <a
            className="mt-8 flex h-10 w-full items-center justify-center rounded-lg bg-[var(--primary)] text-sm font-medium text-[var(--primary-foreground)]"
            href={loginUrl}
          >
            {t("continueIdp")}
          </a>
        ) : null}
        {method === "password" ? (
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
            {tenants.length > 1 ? (
              <div className="space-y-1.5">
                <label className="block text-sm font-medium" htmlFor="tenant">
                  {t("tenantLabel")}
                </label>
                <select
                  className="block h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
                  id="tenant"
                  onChange={(event) => setTenantId(event.target.value)}
                  value={tenantId}
                >
                  <option value="">{t("chooseTenant")}</option>
                  {tenants.map((tenant) => (
                    <option key={tenant.id} value={tenant.id}>
                      {tenant.name}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
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
            <p className="text-sm">
              <a className="underline" href="/forgot-password">
                {t("forgot")}
              </a>
            </p>
          </form>
        ) : null}
      </div>
    </main>
  );
}
