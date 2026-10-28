"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";

type RequestRow = { id: string; title?: string; status?: string };

export default function AuditorPortalPage() {
  const [rows, setRows] = useState<RequestRow[] | null>(null);
  const [signedOut, setSignedOut] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void api<{ items?: RequestRow[] }>("/api/v1/ext/grc/pbc-requests")
      .then((page) => setRows(page.items ?? []))
      .catch((caught: unknown) => {
        if (caught instanceof ApiError && (caught.status === 401 || caught.status === 403)) {
          setSignedOut(true);
          return;
        }
        setError(caught instanceof Error ? caught.message : "The room could not be opened.");
      });
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Auditor room</h1>
      <p className="mt-2 text-[15px] leading-relaxed text-[var(--muted-foreground)]">
        Requests shared with you. A download carries your name.
      </p>
      {error ? (
        <p className="mt-6 text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      {signedOut ? (
        <Button asChild className="mt-8 w-fit">
          <Link href="/guest">Request a guest link</Link>
        </Button>
      ) : null}
      {rows && rows.length === 0 ? (
        <p className="mt-8 text-sm text-[var(--muted-foreground)]">
          Nothing has been shared with this guest yet.
        </p>
      ) : null}
      {rows && rows.length > 0 ? (
        <ul className="mt-8 divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--card)]">
          {rows.map((row) => (
            <li className="px-4 py-3" key={row.id}>
              <p className="font-medium">{row.title || row.id}</p>
              <p className="text-sm text-[var(--muted-foreground)]">{row.status || "open"}</p>
            </li>
          ))}
        </ul>
      ) : null}
    </main>
  );
}
