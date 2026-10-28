"use client";

import Link from "next/link";
import { notFound } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/common/management-layout";
import { AuditForms } from "@/components/grc/audit-forms";
import { GrcNav } from "@/components/grc/grc-nav";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";

const sections = [
  "requests",
  "reviews",
  "reports",
  "inspections",
  "privacy",
  "resilience",
] as const;

export type AuditSection = (typeof sections)[number] | "overview";

type Row = { id: string; title: string; meta: string; conflict?: boolean };

const links: Record<(typeof sections)[number], string> = {
  requests: "/grc/audit/requests",
  reviews: "/grc/audit/reviews",
  reports: "/grc/audit/reports",
  inspections: "/grc/audit/inspections",
  privacy: "/grc/audit/privacy",
  resilience: "/grc/audit/resilience",
};

const templateKeys = ["soa", "soc2_binder", "cscrf", "dpdp_breach", "board_pack"] as const;

export function AuditScreen({ section }: { section: AuditSection }) {
  const t = useTranslations("grc");
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [draftId, setDraftId] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const packs = await api<{ items?: { packId?: string; enabled?: boolean }[] }>(
        "/api/v1/tenant/packs",
      );
      const enabled = (packs.items ?? []).some((row) => row.packId === "grc" && row.enabled);
      if (!enabled) {
        setMissing(true);
        return;
      }
      setMissing(false);
      if (section === "overview") {
        const [requests, campaigns, templates, inspections, dsar, tests] = await Promise.all([
          api<{ items?: unknown[] }>("/api/v1/ext/grc/pbc-requests"),
          api<{ items?: unknown[] }>("/api/v1/ext/grc/campaigns?kind=access_review"),
          api<{ items?: unknown[] }>("/api/v1/ext/grc/report-templates"),
          api<{ items?: unknown[] }>("/api/v1/ext/grc/inspections"),
          api<{ items?: unknown[] }>("/api/v1/ext/grc/dsar-requests"),
          api<{ items?: unknown[] }>("/api/v1/ext/grc/resilience-tests"),
        ]);
        setCounts({
          requests: requests.items?.length ?? 0,
          reviews: campaigns.items?.length ?? 0,
          reports: templates.items?.length ?? 0,
          inspections: inspections.items?.length ?? 0,
          privacy: dsar.items?.length ?? 0,
          resilience: tests.items?.length ?? 0,
        });
        return;
      }
      const loaded = await loadSection(section);
      setRows(loaded.rows);
      setDraftId(loaded.draftId);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 404) {
        setMissing(true);
        return;
      }
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [section, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function startCampaign() {
    setNotice("");
    setError("");
    try {
      await api(`/api/v1/ext/grc/campaigns/${draftId}:start`, { method: "POST" });
      setNotice(t("campaignStarted"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  async function renderReport(template: (typeof templateKeys)[number]) {
    setNotice("");
    setError("");
    try {
      const body = await api<{ binderId?: string; status?: string }>(
        "/api/v1/ext/grc/reports:render",
        {
          method: "POST",
          body: JSON.stringify({ template, params: {} }),
        },
      );
      if (template === "board_pack" && body.status === "pending_review") {
        setNotice(t("reviewRequired"));
        return;
      }
      setNotice(t("reportReady", { id: body.binderId ?? "", status: body.status ?? "" }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  if (!loading && missing) {
    notFound();
    return null;
  }

  const emptyKey =
    section === "overview" ? "emptyRequests" : (`empty${capitalize(section)}` as const);

  return (
    <AppShell>
      <PageHeader title={t("auditTitle")} body={t("auditBody")} />
      <GrcNav section="audit" />
      <nav aria-label={t("auditTitle")} className="mb-6 flex flex-wrap gap-2">
        <SectionLink active={section === "overview"} href="/grc/audit" label={t("overview")} />
        {sections.map((id) => (
          <SectionLink active={section === id} href={links[id]} key={id} label={t(id)} />
        ))}
      </nav>
      {notice ? (
        <p className="mb-4 text-sm" role="status">
          {notice}
        </p>
      ) : null}
      {loading ? (
        <div aria-busy="true" className="space-y-3" role="status">
          <span className="sr-only">{t("loading")}</span>
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : error ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : section === "overview" ? (
        <ul className="grid gap-3 sm:grid-cols-2">
          {sections.map((id) => (
            <li key={id}>
              <Link
                className="block rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-4 hover:bg-[var(--muted)]"
                href={links[id]}
              >
                <p className="font-medium">{t(id)}</p>
                <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t(`${id}Hint`)}</p>
                <p className="mt-3 text-sm">{t("count", { count: counts[id] ?? 0 })}</p>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className="space-y-4">
          <AuditForms
            onChanged={load}
            onNotice={setNotice}
            onRender={renderReport}
            rows={rows}
            section={section}
          />
          {rows.length === 0 ? <EmptyState title={t(emptyKey)} /> : null}
          {rows.length === 0 ? null : (
            <ul className="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--card)]">
              {rows.map((row) => (
                <li className="px-4 py-3" key={row.id}>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium">
                      {section === "reports"
                        ? t(row.id as (typeof templateKeys)[number])
                        : row.title}
                    </p>
                    {row.conflict ? (
                      <span className="rounded-full border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--destructive)]">
                        {t("conflict")}
                      </span>
                    ) : null}
                  </div>
                  {row.meta ? (
                    <p className="text-sm text-[var(--muted-foreground)]">{row.meta}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {section === "reviews" && draftId ? (
            <Button onClick={() => void startCampaign()} type="button">
              {t("startCampaign")}
            </Button>
          ) : null}
        </div>
      )}
    </AppShell>
  );
}

function SectionLink({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      className={cn(
        "rounded-lg px-3 py-2 text-sm",
        active
          ? "bg-[var(--nav-active)] font-semibold"
          : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]",
      )}
      href={href}
    >
      {label}
    </Link>
  );
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

async function loadSection(section: Exclude<AuditSection, "overview">) {
  if (section === "requests") {
    const page = await api<{ items?: { id: string; title?: string; status?: string }[] }>(
      "/api/v1/ext/grc/pbc-requests",
    );
    return {
      draftId: "",
      rows: (page.items ?? []).map((item) => ({
        id: item.id,
        title: item.title || item.id,
        meta: item.status || "open",
      })),
    };
  }
  if (section === "reviews") {
    const [campaigns, rules, entitlements, items] = await Promise.all([
      api<{ items?: { id: string; title?: string; status?: string }[] }>(
        "/api/v1/ext/grc/campaigns?kind=access_review",
      ),
      api<{
        items?: { id: string; name?: string; entitlementA?: string; entitlementB?: string }[];
      }>("/api/v1/ext/grc/sod-rules"),
      api<{ items?: { id: string; subject?: string; entitlement?: string }[] }>(
        "/api/v1/ext/grc/entitlements",
      ),
      api<{ items?: { id: string; subject?: string; status?: string; sodConflicts?: string[] }[] }>(
        "/api/v1/ext/grc/campaign-items",
      ),
    ]);
    const draft = (campaigns.items ?? []).find((item) => item.status === "draft");
    const rows: Row[] = [
      ...(campaigns.items ?? []).map((item) => ({
        id: item.id,
        title: item.title || item.id,
        meta: item.status || "draft",
      })),
      ...(rules.items ?? []).map((item) => ({
        id: item.id,
        title: item.name || item.id,
        meta: `${item.entitlementA || ""} · ${item.entitlementB || ""}`,
      })),
      ...(entitlements.items ?? []).map((item) => ({
        id: item.id,
        title: item.subject || item.id,
        meta: item.entitlement || "",
      })),
      ...(items.items ?? [])
        .filter((item) => (item.sodConflicts ?? []).length > 0)
        .map((item) => ({
          id: `${item.id}-conflict`,
          title: item.subject || item.id,
          meta: (item.sodConflicts ?? []).join(", "),
          conflict: true,
        })),
    ];
    return { draftId: draft?.id ?? "", rows };
  }
  if (section === "reports") {
    const page = await api<{ items?: { key?: string }[] }>("/api/v1/ext/grc/report-templates");
    return {
      draftId: "",
      rows: (page.items ?? []).map((item) => ({
        id: item.key || "template",
        title: item.key || "template",
        meta: "",
      })),
    };
  }
  if (section === "inspections") {
    const page = await api<{
      items?: { id: string; regulator?: string; status?: string; binderId?: string }[];
    }>("/api/v1/ext/grc/inspections");
    return {
      draftId: "",
      rows: (page.items ?? []).map((item) => ({
        id: item.id,
        title: item.regulator || item.id,
        meta: item.status || "announced",
      })),
    };
  }
  if (section === "privacy") {
    const [requests, consent] = await Promise.all([
      api<{ items?: { id: string; requestType?: string; status?: string }[] }>(
        "/api/v1/ext/grc/dsar-requests",
      ),
      api<{ items?: { id: string; subjectRef?: string; purpose?: string; state?: string }[] }>(
        "/api/v1/ext/grc/consent-records",
      ),
    ]);
    return {
      draftId: "",
      rows: [
        ...(requests.items ?? []).map((item) => ({
          id: item.id,
          title: item.requestType || item.id,
          meta: item.status || "open",
        })),
        ...(consent.items ?? []).map((item) => ({
          id: item.id,
          title: item.subjectRef || item.id,
          meta: `${item.purpose || ""} · ${item.state || ""}`,
        })),
      ],
    };
  }
  const [tests, assets] = await Promise.all([
    api<{ items?: { id: string; kind?: string; outcome?: string }[] }>(
      "/api/v1/ext/grc/resilience-tests",
    ),
    api<{ items?: { id: string; name?: string; kind?: string; tier?: string | null }[] }>(
      "/api/v1/ext/grc/assets",
    ),
  ]);
  return {
    draftId: "",
    rows: [
      ...(tests.items ?? []).map((item) => ({
        id: item.id,
        title: item.kind || item.id,
        meta: item.outcome || "",
      })),
      ...(assets.items ?? [])
        .filter((item) => item.kind === "model")
        .map((item) => ({
          id: item.id,
          title: item.name || item.id,
          meta: item.tier || "model",
        })),
    ],
  };
}
