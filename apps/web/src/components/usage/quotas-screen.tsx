"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Meter } from "@/components/usage/meter";
import { api } from "@/lib/api";

type Scope = { id?: string; name?: string } | null;
type Quota = {
  id: string;
  scopeType?: string;
  scope?: Scope;
  metric: string;
  period: string;
  limitValue: number;
  action?: string;
  warnAtPct?: number;
  used?: number;
  implicit?: boolean;
};

const MODE_KEY = "ar-settings-mode";
const field =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)]";

export function QuotasScreen() {
  const t = useTranslations("quotas");
  const [rows, setRows] = useState<Quota[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [metric, setMetric] = useState("model_tokens");
  const [period, setPeriod] = useState("day");
  const [scope, setScope] = useState("user");
  const [limit, setLimit] = useState("10000");
  const [action, setAction] = useState("block");
  const [warn, setWarn] = useState("80");
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api<{ items: Quota[] }>("/api/v1/quotas");
      setRows(page.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
    void load();
  }, [load]);

  function toggleMode() {
    const next = !advanced;
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }

  async function save() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("/api/v1/quotas", {
        method: "POST",
        body: JSON.stringify({
          scopeType: scope,
          metric,
          period,
          limitValue: Number(limit),
          action,
          warnAtPct: Number(warn),
        }),
      });
      setNotice(t("saved"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setError("");
    setNotice("");
    try {
      await api(`/api/v1/quotas/${id}`, { method: "DELETE" });
      setNotice(t("removed"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  return (
    <AppShell>
      <PageHeader body={t("body")} title={t("title")} />
      <div className="mb-4">
        <Button onClick={toggleMode} type="button" variant="outline">
          {advanced ? t("simple") : t("advanced")}
        </Button>
      </div>
      {error ? (
        <p className="mb-3 text-sm text-[var(--destructive)]" role="alert">
          {error}{" "}
          <Button onClick={() => void load()} type="button" variant="outline">
            {t("retry")}
          </Button>
        </p>
      ) : null}
      {notice ? <p className="mb-3 text-sm text-[var(--muted-foreground)]">{notice}</p> : null}
      <form
        className="mb-6 grid gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label className="text-sm" htmlFor="quota-metric">
          {t("metric")}
          <select
            className={`mt-1 ${field}`}
            id="quota-metric"
            onChange={(event) => setMetric(event.target.value)}
            value={metric}
          >
            <option value="model_tokens">model_tokens</option>
            <option value="runs">runs</option>
            <option value="tool_calls">tool_calls</option>
            <option value="sandbox_cpu_seconds">sandbox_cpu_seconds</option>
            <option value="cost_micros">cost_micros</option>
          </select>
        </label>
        <label className="text-sm" htmlFor="quota-period">
          {t("period")}
          <select
            className={`mt-1 ${field}`}
            id="quota-period"
            onChange={(event) => setPeriod(event.target.value)}
            value={period}
          >
            <option value="day">{t("day")}</option>
            <option value="month">{t("month")}</option>
          </select>
        </label>
        <label className="text-sm" htmlFor="quota-scope">
          {t("scope")}
          <select
            className={`mt-1 ${field}`}
            id="quota-scope"
            onChange={(event) => setScope(event.target.value)}
            value={scope}
          >
            <option value="user">{t("user")}</option>
            <option value="tenant">{t("tenant")}</option>
            <option value="team">{t("team")}</option>
            <option value="agent">{t("agent")}</option>
          </select>
        </label>
        <label className="text-sm" htmlFor="quota-limit">
          {t("limit")}
          <Input
            className="mt-1"
            id="quota-limit"
            min={0}
            onChange={(event) => setLimit(event.target.value)}
            type="number"
            value={limit}
          />
        </label>
        {advanced ? (
          <>
            <label className="text-sm" htmlFor="quota-action">
              {t("action")}
              <select
                className={`mt-1 ${field}`}
                id="quota-action"
                onChange={(event) => setAction(event.target.value)}
                value={action}
              >
                <option value="block">{t("block")}</option>
                <option value="warn">{t("warnOnly")}</option>
              </select>
            </label>
            <label className="text-sm" htmlFor="quota-warn">
              {t("warn")}
              <Input
                className="mt-1"
                id="quota-warn"
                max={100}
                min={1}
                onChange={(event) => setWarn(event.target.value)}
                type="number"
                value={warn}
              />
            </label>
          </>
        ) : null}
        <div className="sm:col-span-2">
          <Button disabled={busy || limit === ""} type="submit">
            {t("save")}
          </Button>
        </div>
      </form>
      {loading ? <Skeleton className="h-24 w-full" /> : null}
      {!loading && rows.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
      ) : null}
      <ul className="space-y-3">
        {rows.map((row) => (
          <li
            className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
            key={row.id}
          >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-medium">
                  {row.metric} · {row.period}
                </h2>
                <p className="text-sm text-[var(--muted-foreground)]">
                  {row.scope?.name || row.scopeType}
                  {row.implicit ? ` · ${t("plan")}` : ""}
                </p>
              </div>
              <p className="text-sm">
                {t("used")} {(row.used ?? 0).toLocaleString()} / {row.limitValue.toLocaleString()}
              </p>
            </div>
            <Meter limit={row.limitValue} used={row.used ?? 0} />
            {row.implicit ? null : (
              <Button
                className="mt-3"
                onClick={() => void remove(row.id)}
                type="button"
                variant="outline"
              >
                {t("remove")}
              </Button>
            )}
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
