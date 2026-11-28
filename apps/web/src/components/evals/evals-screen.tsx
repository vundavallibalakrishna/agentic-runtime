"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { BackButton } from "@/components/common/detail-state";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

import { type EvalResult, EvalResults } from "./eval-results";

// A run is scored in the background, a case at a time per worker slot. A suite of a few
// hundred cases takes tens of minutes, so ask every three seconds while the page is open.
const RUN_POLL_MS = 3000;

type Suite = {
  id: string;
  name?: string;
  kind?: string;
  caseCount?: number;
  lastRun?: { id?: string; passRate?: number; status?: string } | null;
};

type Alias = { alias?: string; kind?: string };

type ImportReply = { imported?: number; errors?: { line?: number; msg?: string }[] };

type Feedback = {
  messageId?: string;
  conversationId?: string;
  rating?: string;
  comment?: string;
  agent?: { name?: string } | null;
};

export function EvalsScreen({ agentId, admin = false }: { agentId?: string; admin?: boolean }) {
  const t = useTranslations("evals");
  const [suites, setSuites] = useState<Suite[]>([]);
  const [feedback, setFeedback] = useState<Feedback[]>([]);
  const [results, setResults] = useState<EvalResult[]>([]);
  const [aliases, setAliases] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [name, setName] = useState("");
  const [expect, setExpect] = useState("");
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (agentId) {
      params.set("agent_id", agentId);
    }
    try {
      const page = await api<{ items: Suite[] }>(`/api/v1/eval-suites?${params.toString()}`);
      const rows = page.items ?? [];
      setSuites(
        agentId ? rows : rows.filter((row) => row.kind === "red_team" || row.kind === "functional"),
      );
      if (admin) {
        const inbox = await api<{ items: Feedback[] }>("/api/v1/feedback");
        setFeedback(inbox.items ?? []);
      }
      // Comparing models is optional: without permission to read them, it is not offered.
      api<{ items: Alias[] }>("/api/v1/model-aliases")
        .then((listed) =>
          setAliases(
            [
              ...new Set(
                (listed.items ?? [])
                  .filter((row) => (row.kind ?? "chat") === "chat" && row.alias)
                  .map((row) => row.alias as string),
              ),
            ].sort(),
          ),
        )
        .catch(() => setAliases([]));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [admin, agentId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function createSuite() {
    setBusy(true);
    setNotice("");
    try {
      const created = await api<Suite>("/api/v1/eval-suites", {
        method: "POST",
        body: JSON.stringify({
          name: name || "Workspace suite",
          kind: "functional",
          agentId: agentId ?? null,
          gate: { required: Boolean(agentId), minPassRate: 0.9 },
        }),
      });
      if (expect) {
        await api(`/api/v1/eval-suites/${created.id}/cases`, {
          method: "POST",
          body: JSON.stringify({
            name: "Contains",
            input: { messages: [expect] },
            assertions: [{ type: "contains", value: expect }],
          }),
        });
      }
      setNotice(t("saved"));
      setName("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function runFinished(runId: string): Promise<string> {
    for (;;) {
      const run = await api<{ status: string }>(`/api/v1/eval-runs/${runId}`);
      if (run.status !== "queued" && run.status !== "running") {
        return run.status;
      }
      await new Promise((resolve) => setTimeout(resolve, RUN_POLL_MS));
    }
  }

  async function showResults(runId: string) {
    const page = await api<{ items: EvalResult[] }>(`/api/v1/eval-runs/${runId}/results`);
    setResults(page.items ?? []);
  }

  async function importCases(suiteId: string, file: File) {
    setBusy(true);
    setActive(suiteId);
    setNotice("");
    try {
      const reply = await api<ImportReply>(`/api/v1/eval-suites/${suiteId}/cases:import`, {
        method: "POST",
        body: JSON.stringify({ content: await file.text() }),
      });
      const errors = reply.errors ?? [];
      setNotice(
        errors.length > 0
          ? t("importedWithErrors", {
              count: reply.imported ?? 0,
              errors: errors.length,
              first: `${errors[0]?.line ?? ""}: ${errors[0]?.msg ?? ""}`,
            })
          : t("imported", { count: reply.imported ?? 0 }),
      );
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function runSuite(suiteId: string) {
    setBusy(true);
    setActive(suiteId);
    setNotice("");
    try {
      const run = await api<{ id: string }>(`/api/v1/eval-suites/${suiteId}:run`, {
        method: "POST",
        body: JSON.stringify({
          agentVersionRef: "published",
          agentId,
          ...(model ? { modelAliasOverride: model } : {}),
        }),
      });
      setNotice(t("runStarted"));
      // A case calls the model, so the run is scored in the background.
      const status = await runFinished(run.id);
      setNotice("");
      await showResults(run.id);
      if (status !== "completed") {
        setError(t("runUnfinished"));
      }
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function addFeedback(item: Feedback, suiteId: string) {
    if (!item.conversationId || !item.messageId) {
      return;
    }
    setBusy(true);
    try {
      await api(`/api/v1/eval-suites/${suiteId}/cases:from-conversation`, {
        method: "POST",
        body: JSON.stringify({
          conversationId: item.conversationId,
          messageId: item.messageId,
        }),
      });
      setNotice(t("added"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  const title = admin ? t("adminTitle") : t("title");
  const body = admin ? t("adminBody") : t("body");

  return (
    <AppShell>
      <PageHeader
        body={body}
        title={title}
        actions={
          <BackButton href={agentId ? `/agents/${agentId}` : "/chat"}>{t("back")}</BackButton>
        }
      />
      {error ? (
        <p className="mb-3 text-sm text-[var(--destructive)]" role="alert">
          {error}{" "}
          <Button onClick={() => void load()} type="button" variant="outline">
            {t("retry")}
          </Button>
        </p>
      ) : null}
      {notice ? <p className="mb-3 text-sm text-[var(--muted-foreground)]">{notice}</p> : null}
      {loading ? <Skeleton className="h-40 w-full" /> : null}
      {!loading && suites.length === 0 ? <EmptyState title={t("empty")} /> : null}
      {!loading && suites.length > 0 && aliases.length > 0 ? (
        <label className="mb-3 block text-sm" htmlFor="eval-model">
          {t("model")}
          <select
            className="mt-1 block rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1"
            id="eval-model"
            onChange={(event) => setModel(event.target.value)}
            value={model}
          >
            <option value="">{t("agentModel")}</option>
            {aliases.map((alias) => (
              <option key={alias} value={alias}>
                {alias}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {!loading && suites.length > 0 ? (
        <ul className="row-list">
          {suites.map((suite) => (
            <li className="p-4" key={suite.id}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-medium">{suite.name}</h2>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    {suite.kind} · {t("cases")} {suite.caseCount ?? 0}
                    {suite.lastRun?.passRate != null
                      ? ` · ${Math.round(suite.lastRun.passRate * 100)}%`
                      : ""}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <label className="sr-only" htmlFor={`import-${suite.id}`}>
                    {t("importCases")}
                  </label>
                  <input
                    accept=".jsonl,.json,.yaml,.yml,application/json,text/plain"
                    className="sr-only"
                    disabled={busy}
                    id={`import-${suite.id}`}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      event.target.value = "";
                      if (file) {
                        void importCases(suite.id, file);
                      }
                    }}
                    type="file"
                  />
                  <Button
                    disabled={busy}
                    onClick={() => document.getElementById(`import-${suite.id}`)?.click()}
                    type="button"
                    variant="outline"
                  >
                    {t("importCases")}
                  </Button>
                  {suite.lastRun?.id ? (
                    <Button
                      disabled={busy}
                      onClick={() => {
                        const runId = suite.lastRun?.id;
                        if (runId) {
                          void showResults(runId).catch((caught: unknown) =>
                            setError(caught instanceof Error ? caught.message : t("error")),
                          );
                        }
                      }}
                      type="button"
                      variant="outline"
                    >
                      {t("lastResults")}
                    </Button>
                  ) : null}
                  <Button disabled={busy} onClick={() => void runSuite(suite.id)} type="button">
                    {busy && active === suite.id ? t("running") : t("run")}
                  </Button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
      <section className="mt-8 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-sm font-medium">{t("addCase")}</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-sm" htmlFor="suite-name">
            {t("name")}
            <Input
              className="mt-1"
              id="suite-name"
              onChange={(event) => setName(event.target.value)}
              value={name}
            />
          </label>
          <label className="text-sm" htmlFor="suite-expect">
            {t("expect")}
            <Input
              className="mt-1"
              id="suite-expect"
              onChange={(event) => setExpect(event.target.value)}
              value={expect}
            />
          </label>
        </div>
        <Button className="mt-3" disabled={busy} onClick={() => void createSuite()} type="button">
          {t("create")}
        </Button>
      </section>
      <section className="mt-8" aria-label={t("results")}>
        <h2 className="mb-3 text-sm font-medium">{t("results")}</h2>
        <EvalResults results={results} />
      </section>
      {admin ? (
        <section className="mt-8" aria-label={t("feedback")}>
          <h2 className="mb-3 text-sm font-medium">{t("feedback")}</h2>
          {feedback.length === 0 ? (
            <EmptyState title={t("noFeedback")} />
          ) : (
            <ul className="row-list">
              {feedback.map((item) => (
                <li className="p-4 text-sm" key={item.messageId}>
                  <p>
                    {item.agent?.name || "Agent"} · {item.rating}
                  </p>
                  {item.comment ? (
                    <p className="mt-1 text-[var(--muted-foreground)]">{item.comment}</p>
                  ) : null}
                  {suites[0] ? (
                    <Button
                      className="mt-3"
                      disabled={busy}
                      onClick={() => {
                        const suiteId = suites[0]?.id;
                        if (suiteId) {
                          void addFeedback(item, suiteId);
                        }
                      }}
                      type="button"
                      variant="outline"
                    >
                      {t("addFeedback")}
                    </Button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
      {agentId ? (
        <p className="mt-6 text-sm">
          <Link className="underline" href={`/agents/${agentId}`}>
            {t("back")}
          </Link>
        </p>
      ) : null}
    </AppShell>
  );
}
