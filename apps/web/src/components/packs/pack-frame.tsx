"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { ApiError, api } from "@/lib/api";

type PackRow = {
  packId?: string;
  pack_id?: string;
  enabled?: boolean;
  nav?: { href?: string; label?: string }[];
};

export function PackFrame({ packId }: { packId: string }) {
  const [label, setLabel] = useState(packId);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void api<{ items?: PackRow[]; data?: PackRow[] }>("/api/v1/tenant/packs")
      .then((body) => {
        if (cancelled) return;
        const rows = body.items ?? body.data ?? [];
        const row = rows.find((item) => (item.packId ?? item.pack_id) === packId);
        setEnabled(Boolean(row?.enabled));
        const nav = row?.nav?.find((item) => item.label);
        if (nav?.label) setLabel(nav.label);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setError(caught instanceof ApiError ? caught.message : "This pack could not be loaded.");
        setEnabled(false);
      });
    return () => {
      cancelled = true;
    };
  }, [packId]);

  return (
    <AppShell>
      <PageHeader title={label} body="A pack adds its own tools and pages for this workspace." />
      {error ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      {enabled === null && !error ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading</p>
      ) : null}
      {enabled === false && !error ? (
        <EmptyState title="This pack is not enabled">
          An administrator can enable it for the workspace.
        </EmptyState>
      ) : null}
      {enabled === true ? (
        <EmptyState title="Pack enabled">
          Its tools are available to agents in this workspace.
        </EmptyState>
      ) : null}
    </AppShell>
  );
}
