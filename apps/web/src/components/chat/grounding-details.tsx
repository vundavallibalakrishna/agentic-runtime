"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { DetailState } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TableScroll } from "@/components/ui/table";
import { ApiError, api } from "@/lib/api";
import { formatCount, formatDataValue } from "@/lib/format";

type Report = Record<string, unknown> & { claims: Record<string, unknown>[] };
function isReport(value: unknown): value is Report {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const claims = (value as Record<string, unknown>).claims;
  return (
    Array.isArray(claims) &&
    claims.every(
      (claim) =>
        claim &&
        typeof claim === "object" &&
        !Array.isArray(claim) &&
        typeof claim.text === "string" &&
        typeof claim.status === "string",
    )
  );
}
export function GroundingDetails({
  conversationId,
  messageId,
}: {
  conversationId: string;
  messageId: string;
}) {
  const t = useTranslations("chat");
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [unavailable, setUnavailable] = useState(false);
  const [attempt, setAttempt] = useState(0);
  // biome-ignore lint/correctness/useExhaustiveDependencies: an explicit retry starts a new read
  useEffect(() => {
    const controller = new AbortController();
    let alive = true;
    setLoading(true);
    setError("");
    setUnavailable(false);
    setReport(null);
    void api<unknown>(
      `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}/grounding`,
      { signal: controller.signal },
    )
      .then((value) => {
        if (!alive || controller.signal.aborted) return;
        if (!isReport(value)) throw new Error(t("whyInvalid"));
        setReport(value);
      })
      .catch((caught) => {
        if (!alive || controller.signal.aborted) return;
        if (caught instanceof ApiError && caught.status === 404) setUnavailable(true);
        else setError(caught instanceof Error ? caught.message : t("whyError"));
      })
      .finally(() => {
        if (alive && !controller.signal.aborted) setLoading(false);
      });
    return () => {
      alive = false;
      controller.abort();
    };
  }, [conversationId, messageId, attempt, t]);
  const retry = () => setAttempt((value) => value + 1);
  return (
    <div className="mt-4 space-y-4">
      <p className="text-sm text-[var(--muted-foreground)]">{t("whyHelp")}</p>
      <DetailState
        loading={loading}
        error={error ? `${t("whyError")} ${error}` : ""}
        onRetry={retry}
      />
      {unavailable ? (
        <div className="space-y-3">
          <p role="status" className="text-sm">
            {t("whyUnavailable")}
          </p>
          <Button type="button" variant="outline" onClick={retry}>
            {t("retry")}
          </Button>
        </div>
      ) : null}
      {report ? <ReportClaims report={report} /> : null}
    </div>
  );
}
function ReportClaims({ report }: { report: Report }) {
  const t = useTranslations("chat");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const matching = useMemo(
    () =>
      report.claims.flatMap((claim, offset) =>
        (!status || claim.status === status) &&
        formatDataValue(claim).toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())
          ? [{ claim, offset }]
          : [],
      ),
    [report, query, status],
  );
  const pagination = usePagedRows(matching, `${query}:${status}`);
  const statuses = [
    ...new Set(
      report.claims.flatMap((claim) => (typeof claim.status === "string" ? [claim.status] : [])),
    ),
  ].sort();
  const mode = typeof report.mode === "string" ? report.mode : "";
  const label = (value: string) =>
    t.has(`groundingStatuses.${value}`) ? t(`groundingStatuses.${value}`) : value;
  return (
    <div className="space-y-4">
      <Facts
        items={[
          {
            label: t("groundingMode"),
            value: mode
              ? t.has(`groundingModes.${mode}`)
                ? t(`groundingModes.${mode}`)
                : mode
              : null,
          },
          { label: t("groundingClaims"), value: formatCount(report.claims.length) },
        ]}
      />
      {mode === "off" ? (
        <p className="text-sm text-[var(--muted-foreground)]">{t("groundingOff")}</p>
      ) : null}
      {!report.claims.length ? (
        <p className="text-sm">{t("whyNoClaims")}</p>
      ) : (
        <>
          <Input
            type="search"
            aria-label={t("claimSearch")}
            placeholder={t("claimSearch")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <label className="flex flex-wrap items-center gap-2 text-sm">
            {t("groundingStatus")}
            <select
              className="h-9 max-w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="">{t("allClaimStatuses")}</option>
              {statuses.map((value) => (
                <option key={value} value={value}>
                  {label(value)}
                </option>
              ))}
            </select>
          </label>
          {!matching.length ? (
            <p role="status" className="text-sm">
              {t("noClaimMatches")}
            </p>
          ) : null}
          <ol className="divide-y divide-[var(--border)]">
            {pagination.rows.map(({ claim, offset }) => (
              <Claim key={offset} claim={claim} number={offset + 1} />
            ))}
          </ol>
          <ListPagination {...pagination} label={t("groundingClaims")} />
        </>
      )}
    </div>
  );
}
function Claim({ claim, number }: { claim: Record<string, unknown>; number: number }) {
  const t = useTranslations("chat");
  const [open, setOpen] = useState(false);
  const text = typeof claim.text === "string" ? claim.text : "";
  const status = typeof claim.status === "string" ? claim.status : "";
  return (
    <li className="py-3 text-sm">
      <details open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary className="cursor-pointer whitespace-pre-wrap break-words">
          {t("claimNumber", { number })}
          {status ? (
            <>
              {" "}
              ·{" "}
              <Badge tone={statusTone(status)}>
                {t.has(`groundingStatuses.${status}`) ? t(`groundingStatuses.${status}`) : status}
              </Badge>
            </>
          ) : null}
          {text ? ` · ${text.slice(0, 240)}${text.length > 240 ? "…" : ""}` : ""}
        </summary>
        {open ? (
          <TableScroll
            label={t("claimDetails")}
            className="mt-3 max-h-80 rounded-lg bg-[var(--muted)] p-3"
          >
            <pre className="whitespace-pre-wrap break-words text-xs">{formatDataValue(claim)}</pre>
          </TableScroll>
        ) : null}
      </details>
    </li>
  );
}
