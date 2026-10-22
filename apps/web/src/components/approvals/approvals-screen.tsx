"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

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

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
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

  async function decide(row: Row, decision: "approve" | "reject") {
    setError("");
    try {
      await api(`/api/v1/approvals/${String(row.id)}:decide`, {
        method: "POST",
        body: JSON.stringify({
          decision,
          argsHash: String(row.argsHash ?? ""),
          comment,
        }),
      });
      setComment("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  async function rejectSelected() {
    const chosen = rows.filter((row) => picked.includes(String(row.id)));
    for (const row of chosen) {
      await decide(row, "reject");
    }
    setPicked([]);
  }

  async function revoke(id: string) {
    await api(`/api/v1/standing-approvals/${id}:revoke`, { method: "POST" });
    await load();
  }

  return (
    <AppShell>
      <PageHeader title={t("title")} body={t("body")} />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <fieldset className="flex gap-2">
          <legend className="sr-only">{t("modeLabel")}</legend>
          <Button
            type="button"
            variant={advanced ? "outline" : "default"}
            onClick={() => chooseMode(false)}
          >
            {t("simple")}
          </Button>
          <Button
            type="button"
            variant={advanced ? "default" : "outline"}
            onClick={() => chooseMode(true)}
          >
            {t("advanced")}
          </Button>
        </fieldset>
        <a className="underline" href="/admin/policies">
          {t("policies")}
        </a>
        <a className="underline" href="/reviews">
          {t("reviews")}
        </a>
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
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
            variant={scope === value ? "default" : "outline"}
            onClick={() => setScope(value)}
          >
            {label}
          </Button>
        ))}
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
      </div>
      {error ? (
        <p className="mb-4 text-sm" role="alert">
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
      {!loading && rows.length === 0 ? <p>{t("empty")}</p> : null}
      <ul className="space-y-3">
        {rows.map((row) => {
          const id = String(row.id);
          const preview = row.preview as { title?: string; summary?: string } | undefined;
          return (
            <li key={id} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <div className="flex items-start gap-3">
                <input
                  aria-label={String(row.qualifiedName ?? id)}
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
      <label className="mt-4 block text-sm" htmlFor="approval-comment">
        {t("comment")}
        <textarea
          id="approval-comment"
          className="mt-1 h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
      </label>
      {advanced ? (
        <section className="mt-8">
          <h2 className="text-lg font-medium">{t("standing")}</h2>
          {standing.length === 0 ? <p className="mt-2">{t("noStanding")}</p> : null}
          <ul className="mt-3 space-y-2">
            {standing.map((row) => (
              <li key={String(row.id)} className="flex items-center justify-between gap-3">
                <span>{String((row.tool as Row | undefined)?.name ?? row.id)}</span>
                {row.revokedAt ? null : (
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
    </AppShell>
  );
}
