"use client";

import { notFound } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/common/management-layout";
import { GrcNav } from "@/components/grc/grc-nav";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api } from "@/lib/api";

type Control = { id: string; key?: string; title?: string };
type ControlTest = {
  id: string;
  key?: string;
  procedure?: string;
  schedule?: string;
  freshnessDays?: number;
  controlId?: string;
};
type TestResult = { id: string; testId?: string; outcome?: string; summary?: string };
type Finding = {
  id: string;
  title?: string;
  severity?: string;
  status?: string;
  controlId?: string;
};
type Evidence = { id: string; sourceSystem?: string };
type PackRow = { packId?: string; enabled?: boolean };

const CONNECTORS = [
  { slug: "grc_aws", title: "AWS", note: "Config, IAM, CloudTrail, Security Hub", writes: false },
  { slug: "grc_azure", title: "Azure", note: "Policy, Entra ID, Defender", writes: false },
  { slug: "grc_gcp", title: "Google Cloud", note: "Security Command Center, IAM", writes: false },
  { slug: "grc_okta", title: "Okta", note: "Users, factors, admin roles", writes: false },
  { slug: "grc_entra", title: "Entra ID", note: "Users, sign-in methods, roles", writes: false },
  { slug: "grc_google", title: "Google Workspace", note: "Users, MFA, admin roles", writes: false },
  { slug: "grc_github", title: "GitHub", note: "Branch protection, pull reviews", writes: false },
  { slug: "grc_gitlab", title: "GitLab", note: "Protected branches, approvals", writes: false },
  {
    slug: "grc_jira",
    title: "Jira",
    note: "Search issues. Creates wait for approval.",
    writes: true,
  },
  {
    slug: "grc_servicenow",
    title: "ServiceNow",
    note: "Read records. Creates wait for approval.",
    writes: true,
  },
] as const;

export function MonitoringScreen({ section }: { section: "tests" | "findings" | "connectors" }) {
  const t = useTranslations("grc");
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [controls, setControls] = useState<Control[]>([]);
  const [tests, setTests] = useState<ControlTest[]>([]);
  const [results, setResults] = useState<TestResult[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [selectedTest, setSelectedTest] = useState("");
  const [selectedFinding, setSelectedFinding] = useState("");
  const [evidenceId, setEvidenceId] = useState("");
  const [keyName, setKeyName] = useState("");
  const [procedure, setProcedure] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const packs = await api<{ items?: PackRow[] }>("/api/v1/tenant/packs");
      const enabled = (packs.items ?? []).some((row) => row.packId === "grc" && row.enabled);
      if (!enabled) {
        setMissing(true);
        return;
      }
      setMissing(false);
      const [controlPage, testPage, resultPage, findingPage, evidencePage] = await Promise.all([
        api<{ items: Control[] }>("/api/v1/ext/grc/controls"),
        api<{ items: ControlTest[] }>("/api/v1/ext/grc/control-tests"),
        api<{ items: TestResult[] }>("/api/v1/ext/grc/test-results"),
        api<{ items: Finding[] }>("/api/v1/ext/grc/findings"),
        api<{ items: Evidence[] }>("/api/v1/evidence").catch(() => ({ items: [] as Evidence[] })),
      ]);
      setControls(controlPage.items ?? []);
      setTests(testPage.items ?? []);
      setResults(resultPage.items ?? []);
      setFindings(findingPage.items ?? []);
      setEvidence(evidencePage.items ?? []);
      setSelectedTest((current) => current || testPage.items?.[0]?.id || "");
      setSelectedFinding((current) => current || findingPage.items?.[0]?.id || "");
      setEvidenceId((current) => current || evidencePage.items?.[0]?.id || "");
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 404) {
        setMissing(true);
        return;
      }
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function runSelected() {
    if (!selectedTest) return;
    setBusy(true);
    setNotice("");
    setError("");
    try {
      const body = await api<{ outcome?: string }>(
        `/api/v1/ext/grc/control-tests/${selectedTest}:run`,
        { method: "POST" },
      );
      setNotice(body.outcome === "fail" ? t("recordedFail") : t("recordedPass"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function addTest() {
    const controlId = controls[0]?.id;
    if (!controlId || !keyName.trim() || !procedure.trim()) {
      setError(t("testFields"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api("/api/v1/ext/grc/control-tests", {
        method: "POST",
        body: JSON.stringify({
          controlId,
          key: keyName.trim(),
          procedure: procedure.trim(),
          schedule: "0 6 * * *",
          freshnessDays: 30,
        }),
      });
      setKeyName("");
      setProcedure("");
      setNotice(t("testAdded"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function closeFinding() {
    if (!selectedFinding) return;
    setBusy(true);
    setNotice("");
    setError("");
    try {
      await api(`/api/v1/ext/grc/findings/${selectedFinding}:close`, {
        method: "POST",
        body: JSON.stringify({ evidenceItemId: evidenceId }),
      });
      setNotice(t("findingClosed"));
      await load();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : t("error");
      setError(message === "closure_evidence_required" ? t("closureRequired") : message);
    } finally {
      setBusy(false);
    }
  }

  if (!loading && missing) {
    notFound();
    return null;
  }

  const latest = new Map<string, TestResult>();
  for (const result of results) {
    if (result.testId) latest.set(result.testId, result);
  }
  const finding = findings.find((item) => item.id === selectedFinding) ?? findings[0];
  const currentTest = tests.find((item) => item.id === selectedTest) ?? tests[0];

  return (
    <AppShell>
      <PageHeader title={t("title")} body={t("monitorBody")} />
      <GrcNav section={section} />
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
      ) : error && tests.length === 0 && findings.length === 0 && section !== "connectors" ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : section === "tests" ? (
        <TestsPane
          busy={busy}
          controls={controls}
          current={currentTest}
          keyName={keyName}
          latest={latest}
          onAdd={() => void addTest()}
          onKey={setKeyName}
          onProcedure={setProcedure}
          onRun={() => void runSelected()}
          onSelect={setSelectedTest}
          procedure={procedure}
          tests={tests}
        />
      ) : section === "findings" ? (
        <FindingsPane
          busy={busy}
          error={error}
          evidence={evidence}
          evidenceId={evidenceId}
          finding={finding}
          findings={findings}
          onClose={() => void closeFinding()}
          onEvidence={setEvidenceId}
          onSelect={setSelectedFinding}
        />
      ) : (
        <ConnectorPane evidence={evidence} />
      )}
    </AppShell>
  );
}

function TestsPane({
  tests,
  current,
  latest,
  controls,
  keyName,
  procedure,
  busy,
  onSelect,
  onRun,
  onAdd,
  onKey,
  onProcedure,
}: {
  tests: ControlTest[];
  current?: ControlTest;
  latest: Map<string, TestResult>;
  controls: Control[];
  keyName: string;
  procedure: string;
  busy: boolean;
  onSelect: (id: string) => void;
  onRun: () => void;
  onAdd: () => void;
  onKey: (value: string) => void;
  onProcedure: (value: string) => void;
}) {
  const t = useTranslations("grc");
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      {tests.length === 0 ? (
        <EmptyState title={t("emptyTests")} />
      ) : (
        <ul className="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--card)]">
          {tests.map((item) => {
            const outcome = latest.get(item.id)?.outcome;
            return (
              <li key={item.id}>
                <button
                  className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--muted)]"
                  onClick={() => onSelect(item.id)}
                  type="button"
                >
                  <span>
                    <span className="block font-medium">{item.key}</span>
                    <span className="text-sm text-[var(--muted-foreground)]">{item.schedule}</span>
                  </span>
                  <span
                    className={
                      outcome === "fail"
                        ? "text-sm text-[var(--destructive)]"
                        : "text-sm text-[var(--muted-foreground)]"
                    }
                  >
                    {outcome
                      ? t(outcome === "fail" ? "fail" : outcome === "pass" ? "pass" : "testError")
                      : t("notRun")}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <div className="space-y-4">
        {current ? (
          <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
            <h2 className="text-base font-semibold">{current.key}</h2>
            <p className="mt-2 text-sm text-[var(--muted-foreground)]">{current.procedure}</p>
            <Button className="mt-4" disabled={busy} onClick={onRun} type="button">
              {t("runTest")}
            </Button>
          </section>
        ) : null}
        <form
          className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
          onSubmit={(event) => {
            event.preventDefault();
            onAdd();
          }}
        >
          <h2 className="text-base font-semibold">{t("newTest")}</h2>
          <p className="text-sm text-[var(--muted-foreground)]">
            {controls[0]?.title ?? t("emptyControls")}
          </p>
          <label className="block text-sm" htmlFor="grc-test-key">
            {t("testKey")}
          </label>
          <Input
            id="grc-test-key"
            value={keyName}
            onChange={(event) => onKey(event.target.value)}
          />
          <label className="block text-sm" htmlFor="grc-test-procedure">
            {t("procedure")}
          </label>
          <Input
            id="grc-test-procedure"
            value={procedure}
            onChange={(event) => onProcedure(event.target.value)}
          />
          <Button disabled={busy} type="submit">
            {t("addTest")}
          </Button>
        </form>
      </div>
    </div>
  );
}

function FindingsPane({
  findings,
  finding,
  evidence,
  evidenceId,
  error,
  busy,
  onSelect,
  onEvidence,
  onClose,
}: {
  findings: Finding[];
  finding?: Finding;
  evidence: Evidence[];
  evidenceId: string;
  error: string;
  busy: boolean;
  onSelect: (id: string) => void;
  onEvidence: (id: string) => void;
  onClose: () => void;
}) {
  const t = useTranslations("grc");
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      {findings.length === 0 ? (
        <EmptyState title={t("emptyFindings")} />
      ) : (
        <ul className="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--card)]">
          {findings.map((item) => (
            <li key={item.id}>
              <button
                className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--muted)]"
                onClick={() => onSelect(item.id)}
                type="button"
              >
                <span>
                  <span className="block font-medium">{item.title}</span>
                  <span className="text-sm text-[var(--muted-foreground)]">{item.severity}</span>
                </span>
                <span className="text-sm text-[var(--muted-foreground)]">
                  {item.status === "closed" ? t("closed") : t("openFinding")}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {finding ? (
        <form
          className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
          onSubmit={(event) => {
            event.preventDefault();
            onClose();
          }}
        >
          <h2 className="text-base font-semibold">{finding.title}</h2>
          <p className="text-sm text-[var(--muted-foreground)]">{t("closureHint")}</p>
          {error ? (
            <p className="text-sm text-[var(--destructive)]" role="alert">
              {error}
            </p>
          ) : null}
          <label className="block text-sm" htmlFor="grc-close-evidence">
            {t("evidenceItem")}
          </label>
          <select
            className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
            id="grc-close-evidence"
            onChange={(event) => onEvidence(event.target.value)}
            value={evidenceId}
          >
            <option value="">{t("chooseEvidence")}</option>
            {evidence.map((item) => (
              <option key={item.id} value={item.id}>
                {item.sourceSystem ?? item.id}
              </option>
            ))}
          </select>
          <Button disabled={busy || finding.status === "closed"} type="submit">
            {t("closeFinding")}
          </Button>
        </form>
      ) : null}
    </div>
  );
}

function ConnectorPane({ evidence }: { evidence: Evidence[] }) {
  const t = useTranslations("grc");
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {CONNECTORS.map((item) => {
        const count = evidence.filter((row) => row.sourceSystem === item.slug).length;
        return (
          <li
            className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
            key={item.slug}
          >
            <h2 className="text-base font-semibold">{item.title}</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">{item.note}</p>
            <p className="mt-3 text-sm">
              {item.writes ? t("writesNeedApproval") : t("readOnly")}
              {" · "}
              {count === 0 ? t("noCapture") : t("captured", { count })}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
