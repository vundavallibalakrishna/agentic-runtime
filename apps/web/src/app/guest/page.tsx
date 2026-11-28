"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { AuthAlert, AuthCard } from "@/components/auth-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";

export default function GuestPortalPage() {
  const t = useTranslations("guestAccess");
  const [mode, setMode] = useState("request");
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [code, setCode] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"request" | "signIn" | null>(null);

  async function requestLink() {
    if (busy || !email.trim()) return;
    setError("");
    setNotice("");
    setBusy("request");
    try {
      await api("/api/v1/auth/guest/request-link", {
        method: "POST",
        body: JSON.stringify({ email: email.trim() }),
      });
      setNotice(t("requested"));
    } catch {
      setError(t("requestError"));
    } finally {
      setBusy(null);
    }
  }

  async function signIn() {
    if (busy || !token.trim()) return;
    setError("");
    setNotice("");
    setBusy("signIn");
    try {
      await api("/api/v1/auth/guest/session", {
        method: "POST",
        body: JSON.stringify({ token: token.trim(), totp: code.trim() }),
      });
      setToken("");
      setCode("");
      setNotice(t("signedIn"));
    } catch {
      setError(t("signInError"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <AuthCard body={t("body")} title={t("title")}>
      <fieldset disabled={busy !== null} className="min-w-0 space-y-6">
        <legend className="sr-only">{t("title")}</legend>
        <Tabs
          value={mode}
          onValueChange={(value) => {
            if (busy) return;
            setMode(value);
            setError("");
            setNotice("");
          }}
        >
          <TabsList>
            <TabsTrigger value="request">{t("requestTab")}</TabsTrigger>
            <TabsTrigger value="signIn">{t("signInTab")}</TabsTrigger>
          </TabsList>
          <TabsContent value="request">
            <p className="mb-5 text-sm leading-relaxed text-[var(--muted-foreground)]">
              {t("requestHelp")}
            </p>
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void requestLink();
              }}
            >
              <div className="space-y-1.5">
                <label className="block text-sm font-medium" htmlFor="guest-email">
                  {t("email")}
                </label>
                <Input
                  id="guest-email"
                  autoComplete="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </div>
              <Button className="h-10 w-full" type="submit">
                {busy === "request" ? t("requesting") : t("request")}
              </Button>
            </form>
          </TabsContent>
          <TabsContent value="signIn">
            <p className="mb-5 text-sm leading-relaxed text-[var(--muted-foreground)]">
              {t("tokenHelp")}
            </p>
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void signIn();
              }}
            >
              <div className="space-y-1.5">
                <label className="block text-sm font-medium" htmlFor="guest-token">
                  {t("token")}
                </label>
                <Input
                  id="guest-token"
                  required
                  type="password"
                  autoComplete="off"
                  value={token}
                  onChange={(event) => setToken(event.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium" htmlFor="guest-code">
                  {t("code")}
                </label>
                <Input
                  id="guest-code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                />
              </div>
              <Button className="h-10 w-full" type="submit" variant="outline">
                {busy === "signIn" ? t("signingIn") : t("continue")}
              </Button>
            </form>
          </TabsContent>
        </Tabs>
        {notice ? (
          <p className="rounded-lg bg-[var(--muted)] px-3 py-2 text-sm" role="status">
            {notice}
          </p>
        ) : null}
        {error ? <AuthAlert>{error}</AuthAlert> : null}
      </fieldset>
    </AuthCard>
  );
}
