"use client";

import { useState } from "react";

import { AuthAlert, AuthCard } from "@/components/auth-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

export default function GuestPortalPage() {
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [code, setCode] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function requestLink() {
    setError("");
    await api("/api/v1/auth/guest/request-link", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    setNotice("If that guest exists, a link is on its way.");
  }

  async function signIn() {
    setError("");
    try {
      await api("/api/v1/auth/guest/session", {
        method: "POST",
        body: JSON.stringify({ token, totp: code }),
      });
      setNotice("Signed in. Granted records stay on this page.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in failed");
    }
  }

  return (
    <AuthCard
      body="Guests can read only the records they were granted. Chat and tools stay closed."
      title="Guest access"
    >
      <div className="space-y-6">
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            void requestLink();
          }}
        >
          <div className="space-y-1.5">
            <label className="block text-sm font-medium" htmlFor="guest-email">
              Email
            </label>
            <Input
              id="guest-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>
          <Button className="h-10 w-full" type="submit">
            Email me a link
          </Button>
        </form>
        <form
          className="space-y-4 border-t border-[var(--border)] pt-6"
          onSubmit={(event) => {
            event.preventDefault();
            void signIn();
          }}
        >
          <div className="space-y-1.5">
            <label className="block text-sm font-medium" htmlFor="guest-token">
              Link token
            </label>
            <Input
              id="guest-token"
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm font-medium" htmlFor="guest-code">
              Authenticator code
            </label>
            <Input
              id="guest-code"
              inputMode="numeric"
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
          </div>
          <Button className="h-10 w-full" type="submit" variant="outline">
            Continue
          </Button>
        </form>
        {notice ? (
          <p className="rounded-lg bg-[var(--muted)] px-3 py-2 text-sm" role="status">
            {notice}
          </p>
        ) : null}
        {error ? <AuthAlert>{error}</AuthAlert> : null}
      </div>
    </AuthCard>
  );
}
