"use client";

import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, DetailState, ErrorMessage } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { RecordList } from "@/components/common/record-list";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Meter } from "@/components/usage/meter";
import { ApiError, api, type DisplayError } from "@/lib/api";
import { formatCost, formatCount, formatDateTime } from "@/lib/format";
import { loadSession } from "@/lib/session";

type MineQuota = {
  id: string;
  metric: string;
  period: string;
  limit: number;
  used: number;
  resetsAt?: string;
};
type Mine = {
  currency?: string;
  from?: string;
  to?: string;
  totals: { quantity: number; costMicros: number };
  quotas: MineQuota[];
};
type Identity = {
  id: string;
  integrationId: string;
  externalUserId: string;
  userId: string;
  matchMethod?: string | null;
  verifiedAt?: string | null;
};
type Issue = { kind: "link" | "unlink"; id?: string; accepted: boolean; error: DisplayError };
const identityFields = ["id", "integrationId", "externalUserId", "matchMethod"];
const quotaFields = ["id", "metric", "period"];
const method = (row: Record<string, unknown>) =>
  typeof row.matchMethod === "string" ? row.matchMethod : "";
const period = (row: Record<string, unknown>) => (typeof row.period === "string" ? row.period : "");
const text = (value: unknown): value is string =>
  typeof value === "string" && Boolean(value.trim());
function identityValid(row: Identity, owner: string): boolean {
  return Boolean(
    row &&
      [row.id, row.integrationId, row.externalUserId].every(text) &&
      row.userId === owner &&
      (row.matchMethod == null || typeof row.matchMethod === "string") &&
      (row.verifiedAt == null || typeof row.verifiedAt === "string"),
  );
}
function usageValid(mine: Mine): boolean {
  return Boolean(
    mine &&
      Number.isFinite(mine.totals?.quantity) &&
      Number.isFinite(mine.totals?.costMicros) &&
      (mine.currency === undefined || typeof mine.currency === "string") &&
      Array.isArray(mine.quotas) &&
      mine.quotas.every(
        (row) =>
          row &&
          [row.id, row.metric, row.period].every(text) &&
          Number.isFinite(row.limit) &&
          row.limit >= 0 &&
          Number.isFinite(row.used) &&
          row.used >= 0 &&
          (row.resetsAt === undefined || typeof row.resetsAt === "string"),
      ),
  );
}

export function ProfileScreen() {
  const t = useTranslations("profile");
  return (
    <AppShell>
      <PageHeader body={t("body")} title={t("title")} />
      <div className="grid items-start gap-6 xl:grid-cols-2">
        <LinkedAccounts />
        <PersonalUsage />
      </div>
    </AppShell>
  );
}

function LinkedAccounts() {
  const t = useTranslations("profile");
  const [rows, setRows] = useState<Identity[] | null>(null);
  const [canLink, setCanLink] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<DisplayError>("");
  const [issue, setIssue] = useState<Issue | null>(null);
  const [phase, setPhase] = useState<{ kind: "link" | "unlink"; id?: string } | null>(null);
  const [notice, setNotice] = useState("");
  const [token, setToken] = useState("");
  const readRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const owner = useRef("");
  const feedback = useRef<HTMLDivElement>(null);
  const busy = loading || phase !== null;
  const held = busy || Boolean(loadError) || issue !== null;
  const read = useCallback(
    async (signal: AbortSignal) => {
      try {
        const session = await loadSession();
        if (signal.aborted) return null;
        const allowed = (session.permissions ?? []).includes("chat:use");
        setCanLink(allowed);
        if (!allowed) {
          owner.current = "";
          setRows(null);
          return null;
        }
        if (!text(session.user?.id)) throw new Error(t("linksMetadataError"));
        owner.current = session.user.id;
        const page = await api<{ items: Identity[] }>("/api/v1/me/channel-identities", { signal });
        if (signal.aborted) return null;
        if (
          !Array.isArray(page?.items) ||
          page.items.some((row) => !identityValid(row, owner.current))
        )
          throw new Error(t("linksMetadataError"));
        return page.items;
      } catch (caught) {
        if (
          !signal.aborted &&
          caught instanceof ApiError &&
          [401, 403, 404].includes(caught.status)
        ) {
          setRows(null);
          setCanLink(false);
        }
        throw caught;
      }
    },
    [t],
  );

  const load = useCallback(
    async (pending?: Issue | null) => {
      if (actionRequest.current || readRequest.current) return;
      const request = new AbortController();
      readRequest.current = request;
      setLoading(true);
      setLoadError("");
      try {
        const items = await read(request.signal);
        if (request.signal.aborted) return;
        setRows(items);
        if (items && pending) {
          const reflected =
            Boolean(pending.id) &&
            (pending.kind === "link"
              ? items.some((row) => row.id === pending.id)
              : !items.some((row) => row.id === pending.id));
          setNotice(
            t(
              pending.accepted && reflected
                ? pending.kind === "link"
                  ? "linked"
                  : "unlinked"
                : "linksRefreshed",
            ),
          );
        }
        setIssue(null);
      } catch (caught) {
        if (!request.signal.aborted) {
          setLoadError(caught instanceof Error ? caught : t("error"));
          if (caught instanceof ApiError && [401, 403, 404].includes(caught.status)) {
            setRows(null);
            setCanLink(false);
          }
        }
      } finally {
        if (readRequest.current === request) {
          readRequest.current = null;
          setLoading(false);
        }
      }
    },
    [read, t],
  );

  useEffect(() => {
    const url = new URL(window.location.href);
    const link = url.searchParams.get("link");
    if (link) {
      setToken(link);
      url.searchParams.delete("link");
      window.history.replaceState(
        window.history.state,
        "",
        `${url.pathname}${url.search}${url.hash}`,
      );
    }
    void load();
    return () => {
      readRequest.current?.abort();
      readRequest.current = null;
      actionRequest.current?.abort();
      actionRequest.current = null;
    };
  }, [load]);
  useEffect(() => {
    if (issue) feedback.current?.focus();
  }, [issue]);

  async function change(kind: "link" | "unlink", id?: string) {
    if (
      actionRequest.current ||
      readRequest.current ||
      !canLink ||
      loadError ||
      issue ||
      rows === null ||
      (kind === "link" && !token.trim()) ||
      (kind === "unlink" && !rows.some((row) => row.id === id))
    )
      return;
    const request = new AbortController();
    actionRequest.current = request;
    setPhase({ kind, id });
    setNotice("");
    let accepted = false;
    let target = id;
    try {
      if (kind === "link") {
        const result = await api<Identity>("/api/v1/me/channel-identities:link", {
          method: "POST",
          signal: request.signal,
          body: JSON.stringify({ token: token.trim() }),
        });
        if (request.signal.aborted) return;
        if (!identityValid(result, owner.current)) throw new Error(t("linkUnconfirmed"));
        target = result.id;
        accepted = true;
        setToken("");
        setNotice(t("linkRecorded"));
      } else {
        await api(`/api/v1/me/channel-identities/${encodeURIComponent(id ?? "")}`, {
          method: "DELETE",
          signal: request.signal,
        });
        if (request.signal.aborted) return;
        accepted = true;
      }
      const items = await read(request.signal);
      if (request.signal.aborted) return;
      if (items === null) throw new Error(t("checkUnconfirmed"));
      setRows(items);
      if (
        kind === "link"
          ? !items.some((row) => row.id === target)
          : items.some((row) => row.id === target)
      )
        throw new Error(t(kind === "link" ? "linkUnconfirmed" : "unlinkUnconfirmed"));
      setNotice(t(kind === "link" ? "linked" : "unlinked"));
    } catch (caught) {
      if (!request.signal.aborted)
        setIssue({
          kind,
          id: target,
          accepted,
          error: caught instanceof Error ? caught : t("error"),
        });
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setPhase(null);
      }
    }
  }

  const methodLabel = (value: string) =>
    t.has(`methods.${value}`) ? t(`methods.${value}`) : value;
  return (
    <section className="detail-panel min-w-0" aria-labelledby="profile-links">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold" id="profile-links">
          {t("linksTitle")}
        </h2>
        <Button
          type="button"
          variant="outline"
          disabled={busy}
          aria-label={t("refreshLinks")}
          onClick={() => void load(issue)}
        >
          <RefreshCw size={16} aria-hidden="true" />
        </Button>
      </div>
      <DetailState
        loading={loading}
        error={loadError}
        onRetry={busy ? undefined : () => void load(issue)}
      />
      {canLink === false ? (
        <p className="text-sm text-[var(--muted-foreground)]">{t("linkPermission")}</p>
      ) : null}
      {canLink && rows !== null ? (
        <form
          className="mb-6 grid gap-3"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            void change("link");
          }}
        >
          <label className="grid gap-1 text-sm" htmlFor="link-code">
            {t("code")}
            <Input
              type="password"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              required
              aria-describedby="link-code-help"
              id="link-code"
              disabled={held}
              onChange={(event) => {
                setToken(event.target.value);
                setNotice("");
              }}
              value={token}
            />
          </label>
          <p id="link-code-help" className="text-xs leading-relaxed text-[var(--muted-foreground)]">
            {t("codeHelp")}
          </p>
          <Button className="justify-self-start" disabled={held || !token.trim()} type="submit">
            {t(phase?.kind === "link" ? "linking" : "link")}
          </Button>
        </form>
      ) : null}
      {issue ? (
        <div
          ref={feedback}
          tabIndex={-1}
          role="alert"
          className="mb-4 space-y-2 break-words text-sm"
        >
          <p>{t("recovery")}</p>
          <ErrorMessage error={issue.error} />
        </div>
      ) : null}
      <ActionStatus
        busy={phase !== null}
        busyLabel={t(phase?.kind === "unlink" ? "unlinking" : "linking")}
        notice={notice}
      />
      {canLink && rows !== null ? (
        <RecordList
          rows={rows}
          fields={identityFields}
          getStatus={method}
          label={t("savedLinks")}
          emptyMessage={t("empty")}
          labels={{
            search: t("searchLinks"),
            status: t("method"),
            allStatuses: t("allMethods"),
            clear: t("clear"),
            noMatches: t("noLinkMatches"),
            statusValue: methodLabel,
          }}
        >
          {(item) => {
            const row = item as Identity;
            return (
              <li className="p-4" key={row.id}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-all text-sm font-medium">{row.externalUserId}</p>
                    <p className="mt-1 break-words text-xs text-[var(--muted-foreground)]">
                      {row.matchMethod ? methodLabel(row.matchMethod) : t("methodUnknown")}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={held}
                    aria-label={t("unlinkNamed", {
                      name: `${row.externalUserId} (${row.integrationId})`,
                    })}
                    onClick={() => void change("unlink", row.id)}
                  >
                    {t(phase?.kind === "unlink" && phase.id === row.id ? "unlinking" : "unlink")}
                  </Button>
                </div>
                <details className="mt-3 text-xs">
                  <summary className="cursor-pointer text-[var(--muted-foreground)]">
                    {t("connectionDetails")}
                  </summary>
                  <Facts
                    className="mt-3"
                    items={[
                      { label: t("integration"), value: row.integrationId },
                      { label: t("reference"), value: row.id },
                      {
                        label: t("verified"),
                        value: row.verifiedAt ? formatDateTime(row.verifiedAt) : t("unavailable"),
                      },
                    ]}
                  />
                </details>
              </li>
            );
          }}
        </RecordList>
      ) : null}
    </section>
  );
}

function PersonalUsage() {
  const t = useTranslations("profile");
  const quotas = useTranslations("quotas");
  const [usage, setUsage] = useState<Mine | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<DisplayError>("");
  const request = useRef<AbortController | null>(null);
  const load = useCallback(async () => {
    if (request.current) return;
    const active = new AbortController();
    request.current = active;
    setLoading(true);
    setError("");
    try {
      const mine = await api<Mine>("/api/v1/me/usage", { signal: active.signal });
      if (active.signal.aborted) return;
      if (!usageValid(mine)) throw new Error(t("usageMetadataError"));
      setUsage(mine);
    } catch (caught) {
      if (!active.signal.aborted) {
        setError(caught instanceof Error ? caught : t("usageError"));
        if (caught instanceof ApiError && [401, 403, 404].includes(caught.status)) setUsage(null);
      }
    } finally {
      if (request.current === active) {
        request.current = null;
        setLoading(false);
      }
    }
  }, [t]);
  useEffect(() => {
    void load();
    return () => {
      request.current?.abort();
      request.current = null;
    };
  }, [load]);
  const metricLabel = (value: string) =>
    value === "cost_micros"
      ? t("spend")
      : quotas.has(`metrics.${value}`)
        ? quotas(`metrics.${value}`)
        : value;
  const periodLabel = (value: string) =>
    value === "day" || value === "month" ? quotas(value) : value;
  const amount = (row: MineQuota, value: number) =>
    row.metric === "cost_micros" ? formatCost(value, usage?.currency) : formatCount(value);
  return (
    <section className="detail-panel min-w-0" aria-labelledby="profile-usage">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold" id="profile-usage">
          {t("usageTitle")}
        </h2>
        <Button
          type="button"
          variant="outline"
          disabled={loading}
          aria-label={t("refreshUsage")}
          onClick={() => void load()}
        >
          <RefreshCw size={16} aria-hidden="true" />
        </Button>
      </div>
      <p className="mb-4 text-sm text-[var(--muted-foreground)]">{t("usageBody")}</p>
      <DetailState
        loading={loading}
        error={error}
        onRetry={loading ? undefined : () => void load()}
      />
      {usage ? (
        <>
          <Facts
            className="mb-5"
            items={[
              { label: t("quantity"), value: formatCount(usage.totals.quantity) },
              {
                label: usage.currency?.trim() ? t("spend") : t("spendWithoutCurrency"),
                value: formatCost(usage.totals.costMicros, usage.currency),
              },
            ]}
          />
          <h3 className="mb-3 text-sm font-medium">{t("myLimits")}</h3>
          <RecordList
            rows={usage.quotas}
            fields={quotaFields}
            getStatus={period}
            label={t("myLimits")}
            emptyMessage={t("noLimits")}
            labels={{
              search: t("searchLimits"),
              status: quotas("period"),
              allStatuses: quotas("allPeriods"),
              clear: t("clear"),
              noMatches: t("noLimitMatches"),
              statusValue: periodLabel,
            }}
          >
            {(item) => {
              const row = item as MineQuota;
              return (
                <li className="space-y-2 p-4" key={row.id}>
                  <p className="break-words text-sm font-medium">{metricLabel(row.metric)}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {periodLabel(row.period)} ·{" "}
                    {t("limitValues", {
                      used: amount(row, row.used),
                      limit: amount(row, row.limit),
                    })}
                  </p>
                  <Meter
                    used={row.used}
                    limit={row.limit}
                    label={t("quotaMeter", {
                      metric: metricLabel(row.metric),
                      period: periodLabel(row.period),
                      used: amount(row, row.used),
                      limit: amount(row, row.limit),
                    })}
                  />
                  {row.resetsAt ? (
                    <p className="break-words text-xs text-[var(--muted-foreground)]">
                      {t("resets", { at: formatDateTime(row.resetsAt) })}
                    </p>
                  ) : null}
                </li>
              );
            }}
          </RecordList>
        </>
      ) : null}
    </section>
  );
}
