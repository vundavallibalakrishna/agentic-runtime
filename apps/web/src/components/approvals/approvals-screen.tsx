"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus } from "@/components/common/detail-state";
import { EmptyState } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { confirmStepUp } from "@/lib/step-up";

type Row = Record<string, unknown>;

const MODE_KEY = "ar-settings-mode";

export function ApprovalsScreen() {
  const t = useTranslations("approvals");
  const [rows, setRows] = useState<Row[]>([]);
  const [standing, setStanding] = useState<Row[]>([]);
  const [scope, setScope] = useState("to_decide");
  const [risk, setRisk] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
    setRows([]);
    setPicked([]);
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ scope });
      if (risk) {
        params.set("riskClass", risk);
      }
      const page = await api<{ items: Row[] }>(`/api/v1/approvals?${params.toString()}`);
      setRows(page.items ?? []);
      if (advanced) {
        const grants = await api<{ items: Row[] }>("/api/v1/standing-approvals");
        setStanding(grants.items ?? []);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [advanced, risk, scope, t]);

  useEffect(() => {
    void load();
  }, [load]);

  function chooseMode(next: boolean) {
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }

  async function postDecision(row: Row, decision: "approve" | "reject") {
    if (row.stepUpRequired) await confirmStepUp();
    await api(`/api/v1/approvals/${String(row.id)}:decide`, {
      method: "POST",
      body: JSON.stringify({ decision, argsHash: String(row.argsHash ?? ""), comment }),
    });
  }
  async function decide(row: Row, decision: "approve" | "reject") {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await postDecision(row, decision);
      setComment("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }
  async function rejectSelected() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      for (const row of rows.filter(
        (row) => row.status === "pending" && picked.includes(String(row.id)),
      )) {
        await postDecision(row, "reject");
        setRows((current) =>
          current.map((item) => (item.id === row.id ? { ...item, status: "rejected" } : item)),
        );
        setPicked((current) => current.filter((id) => id !== row.id));
      }
      setComment("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }
  async function revoke(id: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/standing-approvals/${id}:revoke`, { method: "POST" });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <ActionStatus busy={busy} />
      <fieldset disabled={busy} className="min-w-0">
        <PageHeader
          title={t("title")}
          body={t("body")}
          actions={<SettingsMode advanced={advanced} onChange={chooseMode} />}
        />
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <Button asChild variant="outline">
            <a href="/reviews">{t("reviews")}</a>
          </Button>
          <Button asChild variant="ghost">
            <a href="/admin/policies">{t("policies")}</a>
          </Button>
        </div>
        <fieldset className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <legend className="sr-only">{t("scopeLabel")}</legend>
          <div className="flex gap-1 rounded-lg bg-[var(--muted)] p-1">
            {(
              [
                ["to_decide", t("toDecide")],
                ["requested", t("requested")],
                ["all", t("all")],
              ] as const
            ).map(([value, label]) => (
              <Button
                key={value}
                type="button"
                variant="ghost"
                aria-pressed={scope === value}
                className={
                  scope === value
                    ? "h-9 bg-[var(--card)] shadow-[var(--shadow-xs)]"
                    : "h-9 text-[var(--muted-foreground)]"
                }
                onClick={() => setScope(value)}
              >
                {label}
              </Button>
            ))}
          </div>
          <label className="sr-only" htmlFor="risk-filter">
            {t("risk")}
          </label>
          <select
            id="risk-filter"
            className="h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
            value={risk}
            onChange={(event) => setRisk(event.target.value)}
          >
            <option value="">{t("risk")}</option>
            <option value="W2">W2</option>
            <option value="W3">W3</option>
          </select>
        </fieldset>
        {error ? (
          <p
            className="mb-5 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-sm"
            role="alert"
          >
            {error}{" "}
            <button className="underline" type="button" onClick={() => void load()}>
              {t("retry")}
            </button>
          </p>
        ) : null}
        {loading ? (
          <div aria-busy="true" className="space-y-3">
            <span className="sr-only">{t("loading")}</span>
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : null}
        {!loading && !error && rows.length === 0 ? (
          <EmptyState title={t("empty")}>
            <p className="mb-4 max-w-sm text-sm text-[var(--muted-foreground)]">{t("emptyHelp")}</p>
            <Button variant="outline" onClick={() => void load()}>
              {t("refresh")}
            </Button>
          </EmptyState>
        ) : null}
        <ul className="space-y-3">
          {rows.map((row) => {
            const id = String(row.id);
            const preview = row.preview as { title?: string; summary?: string } | undefined;
            return (
              <li
                key={id}
                className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
              >
                <div className="flex items-start gap-3">
                  <input
                    aria-label={String(row.qualifiedName ?? id)}
                    disabled={row.status !== "pending"}
                    checked={picked.includes(id)}
                    type="checkbox"
                    onChange={(event) =>
                      setPicked((current) =>
                        event.target.checked
                          ? [...current, id]
                          : current.filter((item) => item !== id),
                      )
                    }
                  />
                  <div className="min-w-0 flex-1">
                    <a className="font-medium underline" href={`/approvals/${id}`}>
                      {String(row.qualifiedName ?? "")}
                    </a>
                    <p className="text-sm text-[var(--muted-foreground)]">
                      {String(row.riskClass ?? "")} · {String(row.status ?? "")}
                    </p>
                    <p className="mt-1">{preview?.title || preview?.summary || ""}</p>
                    {row.status === "pending" ? (
                      <div className="mt-3 flex gap-2">
                        <Button type="button" onClick={() => void decide(row, "approve")}>
                          {t("approve")}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => void decide(row, "reject")}
                        >
                          {t("reject")}
                        </Button>
                      </div>
                    ) : null}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
        {picked.length > 0 ? (
          <Button
            className="mt-4"
            type="button"
            variant="outline"
            onClick={() => void rejectSelected()}
          >
            {t("rejectSelected")}
          </Button>
        ) : null}
        {!loading && !error && rows.some((row) => row.status === "pending") ? (
          <label
            className="mt-6 block rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 text-sm"
            htmlFor="approval-comment"
          >
            {t("comment")}
            <textarea
              id="approval-comment"
              className="mt-1 h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
          </label>
        ) : null}
        {advanced && !loading && !error ? (
          <section className="mt-8 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
            <h2 className="text-lg font-medium">{t("standing")}</h2>
            {standing.length === 0 ? <p className="mt-2">{t("noStanding")}</p> : null}
            <ul className="mt-3 space-y-2">
              {standing.map((row) => (
                <li
                  key={String(row.id)}
                  className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] py-3"
                >
                  <div className="min-w-0 space-y-1 break-words text-sm">
                    <p className="font-medium">
                      {String((row.tool as Row | undefined)?.name || t("unavailableTool"))}
                    </p>
                    {row.expiresAt ? (
                      <p className="text-xs text-[var(--muted-foreground)]">
                        {t(
                          new Date(String(row.expiresAt)).getTime() <= Date.now()
                            ? "standingExpired"
                            : "standingExpires",
                          { date: new Date(String(row.expiresAt)).toLocaleString() },
                        )}
                      </p>
                    ) : null}
                    {(row.routine as Row | undefined)?.id ? (
                      <a
                        className="inline-block underline underline-offset-4"
                        href={`/routines/${String((row.routine as Row).id)}`}
                      >
                        {t("viewRoutine")}
                      </a>
                    ) : null}
                  </div>
                  {row.revokedAt ? (
                    <span className="text-xs text-[var(--muted-foreground)]">{t("revoked")}</span>
                  ) : (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void revoke(String(row.id))}
                    >
                      {t("revoke")}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </fieldset>
    </AppShell>
  );
}
