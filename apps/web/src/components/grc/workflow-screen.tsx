"use client";

import Link from "next/link";
import { notFound } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/common/management-layout";
import { GrcNav } from "@/components/grc/grc-nav";
import { WorkflowForms } from "@/components/grc/workflow-forms";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";

const workflowSections = [
  "questionnaires",
  "vendors",
  "policies",
  "risks",
  "regulatory",
  "incidents",
  "exceptions",
  "ethics",
] as const;

export type WorkflowSection = (typeof workflowSections)[number] | "overview";

type Row = { id: string; title: string; meta: string };
type Job = { id: string };
type PolicyVersion = { id: string; state?: string; version?: number };

const links: Record<(typeof workflowSections)[number], string> = {
  questionnaires: "/grc/workflows/questionnaires",
  vendors: "/grc/workflows/vendors",
  policies: "/grc/workflows/policies",
  risks: "/grc/workflows/risks",
  regulatory: "/grc/workflows/regulatory",
  incidents: "/grc/workflows/incidents",
  exceptions: "/grc/workflows/exceptions",
  ethics: "/grc/workflows/ethics",
};

export function WorkflowScreen({ section }: { section: WorkflowSection }) {
  const t = useTranslations("grc");
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [jobId, setJobId] = useState("");
  const [versionId, setVersionId] = useState("");

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
        const [answers, vendors, policies, risks, changes, incidents, exceptions, ethics] =
          await Promise.all([
            api<{ items?: unknown[] }>("/api/v1/ext/grc/answer-library"),
            api<{ items?: unknown[] }>("/api/v1/ext/grc/vendors"),
            api<{ items?: unknown[] }>("/api/v1/ext/grc/policies"),
            api<{ items?: unknown[] }>("/api/v1/ext/grc/risks"),
            api<{ items?: unknown[] }>("/api/v1/ext/grc/regulatory-changes"),
            api<{ items?: unknown[] }>("/api/v1/ext/grc/incidents"),
            api<{ items?: unknown[] }>("/api/v1/ext/grc/exceptions"),
            api<{ items?: unknown[] }>("/api/v1/ext/grc/ethics-cases"),
          ]);
        setCounts({
          questionnaires: answers.items?.length ?? 0,
          vendors: vendors.items?.length ?? 0,
          policies: policies.items?.length ?? 0,
          risks: risks.items?.length ?? 0,
          regulatory: changes.items?.length ?? 0,
          incidents: incidents.items?.length ?? 0,
          exceptions: exceptions.items?.length ?? 0,
          ethics: ethics.items?.length ?? 0,
        });
        return;
      }
      const loaded = await loadSection(section);
      setRows(loaded.rows);
      setJobId(loaded.jobId);
      setVersionId(loaded.versionId);
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

  async function exportAnswers() {
    setNotice("");
    setError("");
    try {
      await api(`/api/v1/ext/grc/questionnaires/${jobId}:export`, { method: "POST" });
      setNotice(t("exported"));
    } catch (caught) {
      setError(explain(caught, t("reviewRequired"), t("error")));
    }
  }

  async function publishPolicy() {
    setNotice("");
    setError("");
    try {
      await api(`/api/v1/ext/grc/policy-versions/${versionId}:publish`, { method: "POST" });
      setNotice(t("published"));
      await load();
    } catch (caught) {
      setError(explain(caught, t("reviewRequired"), t("error")));
    }
  }

  if (!loading && missing) {
    notFound();
    return null;
  }

  return (
    <AppShell>
      <PageHeader title={t("workflowsTitle")} body={t("workflowsBody")} />
      <GrcNav section="workflows" />
      <nav aria-label={t("workflowsTitle")} className="mb-6 flex flex-wrap gap-2">
        <Link
          className={cn(
            "rounded-lg px-3 py-2 text-sm",
            section === "overview"
              ? "bg-[var(--nav-active)] font-semibold"
              : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]",
          )}
          href="/grc/workflows"
        >
          {t("overview")}
        </Link>
        {workflowSections.map((id) => (
          <Link
            className={cn(
              "rounded-lg px-3 py-2 text-sm",
              section === id
                ? "bg-[var(--nav-active)] font-semibold"
                : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]",
            )}
            href={links[id]}
            key={id}
          >
            {t(id)}
          </Link>
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
          {workflowSections.map((id) => (
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
          <WorkflowForms onChanged={load} onNotice={setNotice} rows={rows} section={section} />
          {rows.length === 0 ? <EmptyState title={t("emptyWorkflow")} /> : null}
          {rows.length === 0 ? null : (
            <ul className="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--card)]">
              {rows.map((row) => (
                <li className="px-4 py-3" key={row.id}>
                  <p className="font-medium">{row.title}</p>
                  <p className="text-sm text-[var(--muted-foreground)]">{row.meta}</p>
                </li>
              ))}
            </ul>
          )}
          {section === "questionnaires" && jobId ? (
            <Button onClick={() => void exportAnswers()} type="button">
              {t("exportAnswers")}
            </Button>
          ) : null}
          {section === "policies" && versionId ? (
            <Button onClick={() => void publishPolicy()} type="button" variant="outline">
              {t("publishPolicy")}
            </Button>
          ) : null}
        </div>
      )}
    </AppShell>
  );
}

function explain(caught: unknown, review: string, fallback: string) {
  if (caught instanceof ApiError && caught.message === "review_required") {
    return review;
  }
  return caught instanceof Error ? caught.message : fallback;
}

async function loadSection(section: Exclude<WorkflowSection, "overview">) {
  if (section === "questionnaires") {
    const page = await api<{
      items?: { id: string; question?: string; status?: string }[];
      jobs?: Job[];
    }>("/api/v1/ext/grc/answer-library");
    return {
      rows: (page.items ?? []).map((item) => ({
        id: item.id,
        title: item.question || item.id,
        meta: item.status || "",
      })),
      jobId: page.jobs?.[0]?.id ?? "",
      versionId: "",
    };
  }
  if (section === "vendors") {
    const page = await api<{ items?: { id: string; name?: string; tier?: string | null }[] }>(
      "/api/v1/ext/grc/vendors",
    );
    return {
      rows: (page.items ?? []).map((item) => ({
        id: item.id,
        title: item.name || item.id,
        meta: item.tier || "unscored",
      })),
      jobId: "",
      versionId: "",
    };
  }
  if (section === "policies") {
    const page = await api<{ items?: { id: string; title?: string; key?: string }[] }>(
      "/api/v1/ext/grc/policies",
    );
    const first = page.items?.[0];
    let versionId = "";
    let state = "";
    if (first) {
      const detail = await api<{ versions?: PolicyVersion[] }>(
        `/api/v1/ext/grc/policies/${first.id}`,
      );
      const draft = (detail.versions ?? []).find((item) => item.state === "draft");
      versionId = draft?.id ?? "";
      state = draft?.state || (detail.versions ?? [])[0]?.state || "";
    }
    return {
      rows: (page.items ?? []).map((item) => ({
        id: item.id,
        title: item.title || item.key || item.id,
        meta: item.id === first?.id ? state : item.key || "",
      })),
      jobId: "",
      versionId,
    };
  }
  if (section === "risks") {
    const page = await api<{
      items?: { id: string; title?: string; status?: string; assessments?: { score?: number }[] }[];
    }>("/api/v1/ext/grc/risks");
    return {
      rows: (page.items ?? []).map((item) => ({
        id: item.id,
        title: item.title || item.id,
        meta: `${item.status || "open"} · ${item.assessments?.at(-1)?.score ?? ""}`,
      })),
      jobId: "",
      versionId: "",
    };
  }
  if (section === "regulatory") {
    const [changes, feeds, obligations] = await Promise.all([
      api<{ items?: { id: string; title?: string; status?: string }[] }>(
        "/api/v1/ext/grc/regulatory-changes",
      ),
      api<{ items?: { id: string; regulator?: string; url?: string }[] }>(
        "/api/v1/ext/grc/regulator-feeds",
      ),
      api<{ items?: { id: string; citation?: string; statement?: string }[] }>(
        "/api/v1/ext/grc/obligations",
      ),
    ]);
    return {
      rows: [
        ...(feeds.items ?? []).map((item) => ({
          id: item.id,
          title: item.regulator || item.id,
          meta: item.url || "",
        })),
        ...(obligations.items ?? []).map((item) => ({
          id: item.id,
          title: item.citation || item.id,
          meta: item.statement || "",
        })),
        ...(changes.items ?? []).map((item) => ({
          id: item.id,
          title: item.title || item.id,
          meta: item.status || "",
        })),
      ],
      jobId: "",
      versionId: "",
    };
  }
  if (section === "incidents") {
    const page = await api<{
      items?: {
        id: string;
        title?: string;
        status?: string;
        clocks?: { regime?: string; durationSeconds?: number }[];
      }[];
    }>("/api/v1/ext/grc/incidents");
    return {
      rows: (page.items ?? []).map((item) => {
        const clock = item.clocks?.[0];
        const hours = clock?.durationSeconds ? Math.round(clock.durationSeconds / 3600) : 0;
        const meta = clock
          ? `${item.status || "open"} · ${clock.regime} ${hours}h`
          : item.status || "";
        return { id: item.id, title: item.title || item.id, meta };
      }),
      jobId: "",
      versionId: "",
    };
  }
  if (section === "exceptions") {
    const page = await api<{
      items?: { id: string; kind?: string; status?: string; rationale?: string }[];
    }>("/api/v1/ext/grc/exceptions");
    return {
      rows: (page.items ?? []).map((item) => ({
        id: item.id,
        title: item.rationale || item.kind || item.id,
        meta: `${item.kind || ""} · ${item.status || ""}`,
      })),
      jobId: "",
      versionId: "",
    };
  }
  const page = await api<{ items?: { id: string; title?: string; status?: string }[] }>(
    "/api/v1/ext/grc/ethics-cases",
  );
  return {
    rows: (page.items ?? []).map((item) => ({
      id: item.id,
      title: item.title || item.id,
      meta: item.status || "restricted",
    })),
    jobId: "",
    versionId: "",
  };
}
