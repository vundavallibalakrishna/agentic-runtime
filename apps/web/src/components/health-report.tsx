"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { DetailState } from "@/components/common/detail-state";

type Health = { status?: string };
type Component = { name?: string; status?: string; detail?: string };
type Meta = { version?: string; deploymentMode?: string; deployment_mode?: string };

export function HealthReport() {
  const t = useTranslations("platform");
  const [health, setHealth] = useState<Health | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [components, setComponents] = useState<Component[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    void refresh;
    setLoading(true);
    setFailed(false);
    void (async () => {
      try {
        const [healthResponse, metaResponse] = await Promise.all([
          fetch("/healthz", { credentials: "include" }),
          fetch("/api/v1/meta", { credentials: "include" }),
        ]);
        if (!healthResponse.ok || !metaResponse.ok) {
          throw new Error("down");
        }
        const healthBody = (await healthResponse.json()) as Health;
        const metaBody = (await metaResponse.json()) as Meta;
        if (!cancelled) {
          setHealth(healthBody);
          setMeta(metaBody);
        }
        const probes = await fetch("/api/v1/platform/health", { credentials: "include" });
        if (probes.ok && !cancelled) {
          const body = (await probes.json()) as { components?: Component[] };
          setComponents(body.components ?? []);
        }
      } catch {
        if (!cancelled) {
          setFailed(true);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  if (loading || failed) {
    return (
      <DetailState
        loading={loading}
        error={failed ? t("down") : ""}
        onRetry={() => setRefresh((value) => value + 1)}
      />
    );
  }
  const mode = meta?.deploymentMode ?? meta?.deployment_mode ?? "—";
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <article className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <p className="text-sm text-[var(--muted-foreground)]">{t("ok")}</p>
        <p className="mt-2 text-2xl font-medium tracking-tight">{health?.status ?? "down"}</p>
      </article>
      <article className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <p className="text-sm text-[var(--muted-foreground)]">{t("version")}</p>
        <p className="mt-2 text-2xl font-medium tracking-tight">{meta?.version ?? "—"}</p>
      </article>
      <article className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <p className="text-sm text-[var(--muted-foreground)]">{t("mode")}</p>
        <p className="mt-2 text-2xl font-medium tracking-tight">{mode}</p>
      </article>
      <article className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 sm:col-span-3">
        <p className="text-sm text-[var(--muted-foreground)]">{t("components")}</p>
        {components && components.length > 0 ? (
          <ul className="mt-3 space-y-2 text-sm">
            {components.map((item) => (
              <li className="flex items-center justify-between gap-3" key={item.name}>
                <span>{item.name}</span>
                <span className="text-[var(--muted-foreground)]">
                  {item.status}
                  {item.detail === "not configured" ? ` · ${t("notConfigured")}` : ""}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm">{t("componentEmpty")}</p>
        )}
      </article>
    </div>
  );
}
