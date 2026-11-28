"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { BackButton, DetailState } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { ApiError, api } from "@/lib/api";

type PackRow = {
  packId?: string;
  pack_id?: string;
  version?: string;
  enabled?: boolean;
  nav?: { href?: string; label?: string }[];
};
type PackState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; pack: PackRow | null };

export function PackFrame({ packId }: { packId: string }) {
  const [attempt, setAttempt] = useState(0);
  return (
    <PackDetails
      key={`${packId}-${attempt}`}
      packId={packId}
      onRetry={() => setAttempt((value) => value + 1)}
    />
  );
}

function PackDetails({ packId, onRetry }: { packId: string; onRetry: () => void }) {
  const t = useTranslations("packs");
  const [state, setState] = useState<PackState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });
    void api<{ items?: PackRow[]; data?: PackRow[] }>("/api/v1/tenant/packs", {
      signal: controller.signal,
    })
      .then((body) => {
        if (controller.signal.aborted) return;
        const pack = (body.items ?? body.data ?? []).find(
          (item) => (item.packId ?? item.pack_id) === packId,
        );
        setState({ status: "ready", pack: pack ?? null });
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          status: "error",
          message: caught instanceof ApiError ? caught.message : t("loadError"),
        });
      });
    return () => controller.abort();
  }, [packId, t]);

  const pack = state.status === "ready" ? state.pack : null;
  const label = pack?.nav?.find((item) => item.label)?.label ?? t("title");

  return (
    <AppShell>
      <PageHeader
        title={label}
        body={t("description")}
        actions={<BackButton href="/chat">{t("back")}</BackButton>}
      />
      <div className="max-w-3xl">
        <DetailState
          loading={state.status === "loading"}
          error={state.status === "error" ? state.message : ""}
          onRetry={onRetry}
        />
        {state.status === "ready" && !pack ? (
          <EmptyState title={t("missing")}>{t("missingHelp")}</EmptyState>
        ) : null}
        {pack ? (
          <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
            <Facts
              items={[
                { label: t("id"), value: pack.packId ?? pack.pack_id },
                { label: t("version"), value: pack.version },
                {
                  label: t("status"),
                  value: (
                    <Badge tone={pack.enabled ? "success" : "neutral"}>
                      {t(pack.enabled ? "enabled" : "disabledStatus")}
                    </Badge>
                  ),
                },
              ]}
            />
            <p className="mt-5 border-t border-[var(--border)] pt-4 text-sm leading-relaxed text-[var(--muted-foreground)]">
              {t(pack.enabled ? "accessHelp" : "disabledHelp")}
            </p>
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}
