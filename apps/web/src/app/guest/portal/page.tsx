"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AuthAlert, AuthCard } from "@/components/auth-card";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";

type SharedRow = { id: string; title?: string; status?: string };

export default function GuestRecordsPage() {
  const [rows, setRows] = useState<SharedRow[] | null>(null);
  const [signedOut, setSignedOut] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void api<{ items?: SharedRow[]; data?: SharedRow[] }>("/api/v1/tenant/packs")
      .then((page) => setRows(page.items ?? page.data ?? []))
      .catch((caught: unknown) => {
        if (caught instanceof ApiError && (caught.status === 401 || caught.status === 403)) {
          setSignedOut(true);
          setRows([]);
          return;
        }
        setError(caught instanceof Error ? caught.message : "The room could not be opened.");
      });
  }, []);

  return (
    <AuthCard
      body="Items shared with this guest. A download carries your name."
      title="Shared records"
      wide
    >
      <div className="space-y-4">
        {error ? <AuthAlert>{error}</AuthAlert> : null}
        {rows === null && !error ? (
          <p className="text-center text-sm text-[var(--muted-foreground)]" role="status">
            Loading the shared records.
          </p>
        ) : null}
        {signedOut ? (
          <Button asChild className="h-10 w-full">
            <Link href="/guest">Request a guest link</Link>
          </Button>
        ) : null}
        {rows && rows.length === 0 && !signedOut ? (
          <p className="text-center text-sm text-[var(--muted-foreground)]">
            Nothing has been shared with this guest yet.
          </p>
        ) : null}
        {rows && rows.length > 0 ? (
          <ul className="divide-y divide-[var(--border)] rounded-lg border border-[var(--border)]">
            {rows.map((row) => (
              <li className="px-4 py-3" key={row.id}>
                <p className="font-medium">{row.title || row.id}</p>
                <p className="text-sm text-[var(--muted-foreground)]">{row.status || "open"}</p>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </AuthCard>
  );
}
