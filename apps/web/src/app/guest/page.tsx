"use client";

import { useState } from "react";

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
      body: JSON.stringify({ email, tenantSlug: "dev" }),
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
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-6">
      <h1 className="text-3xl font-semibold tracking-tight">Guest access</h1>
      <p className="text-sm text-[var(--muted-foreground)]">
        Guests can read only the records they were granted. Chat and tools stay closed.
      </p>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          void requestLink();
        }}
      >
        <label className="block text-sm" htmlFor="guest-email">
          Email
        </label>
        <Input
          id="guest-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <Button type="submit">Email me a link</Button>
      </form>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          void signIn();
        }}
      >
        <label className="block text-sm" htmlFor="guest-token">
          Link token
        </label>
        <Input id="guest-token" value={token} onChange={(event) => setToken(event.target.value)} />
        <label className="block text-sm" htmlFor="guest-code">
          Authenticator code
        </label>
        <Input
          id="guest-code"
          inputMode="numeric"
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
        <Button type="submit" variant="outline">
          Continue
        </Button>
      </form>
      {notice ? <p className="text-sm">{notice}</p> : null}
      {error ? <p className="text-sm text-[var(--destructive)]">{error}</p> : null}
    </main>
  );
}
