"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { ReferencePicker } from "@/components/common/reference-picker";
import { ScheduleFields } from "@/components/common/schedule-fields";
import { PageHeader } from "@/components/page-header";
import {
  type DeliveryChoice,
  DeliveryFields,
  deliveryTargets,
  NO_DELIVERY,
} from "@/components/routines/delivery-fields";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { isAvailableAgent } from "@/lib/agent-availability";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

type Routine = {
  id: string;
  name: string;
  description?: string;
  status?: string;
  triggerType?: string;
  triggerSummary?: string;
  nextRunAt?: string | null;
  consecutiveFailures?: number;
};

type Agent = { id: string; name: string; slug?: string; status?: string; disabled?: boolean };
type Preview = { valid: boolean; description: string; next: string[] };

export function RoutinesScreen() {
  const t = useTranslations("routines");
  const locale = useLocale();
  const availability = useTranslations("agentAvailability");
  const router = useRouter();
  const [rows, setRows] = useState<Routine[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [catalogueReady, setCatalogueReady] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [cron, setCron] = useState("0 9 * * 1");
  const [timezone, setTimezone] = useState("UTC");
  const [agentId, setAgentId] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [delivery, setDelivery] = useState<DeliveryChoice>(NO_DELIVERY);

  const filtered = rows.filter(
    (row) =>
      (!status || row.status === status) &&
      [row.name, row.description, row.triggerSummary, row.id].some((value) =>
        value?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
      ),
  );
  const pagination = usePagedRows(filtered, `${query}::${status}`);
  const statuses = [
    ...new Set(rows.map((row) => row.status).filter((value): value is string => Boolean(value))),
  ].sort();

  const load = useCallback(async () => {
    setLoading(true);
    setCatalogueReady(false);
    setError("");
    try {
      const [page, agentPage] = await Promise.all([
        api<{ items: Routine[] }>("/api/v1/routines"),
        api<{ items: Agent[] }>("/api/v1/agents"),
      ]);
      setRows(page.items ?? []);
      const list = (agentPage.items ?? []).filter(isAvailableAgent);
      setAgents(list);
      setAgentId((current) =>
        current ? (list.some((agent) => agent.id === current) ? current : "") : list[0]?.id || "",
      );
      setCatalogueReady(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function showPreview() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const found = await api<Preview>("/api/v1/routines:preview-schedule", {
        method: "POST",
        body: JSON.stringify({ cron, timezone }),
      });
      setPreview(found);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function createRoutine() {
    if (
      busy ||
      !catalogueReady ||
      !name.trim() ||
      !instructions.trim() ||
      !agents.some((agent) => agent.id === agentId)
    )
      return;
    setBusy(true);
    setError("");
    try {
      const created = await api<Routine>("/api/v1/routines", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          agentId,
          instructions,
          trigger: { type: "schedule", cron, timezone },
          delivery: deliveryTargets(delivery),
        }),
      });
      router.push(`/routines/${created.id}`);
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
        <PageHeader body={t("body")} title={t("title")} />
        {error ? (
          <p className="mb-3 text-sm text-[var(--destructive)]" role="alert">
            {error}{" "}
            <Button onClick={() => void load()} type="button" variant="outline">
              {t("retry")}
            </Button>
          </p>
        ) : null}

        <ManagementLayout
          title={t("listTitle")}
          formTitle={t("create")}
          form={
            <form
              className="space-y-1"
              onSubmit={(event) => {
                event.preventDefault();
                void createRoutine();
              }}
            >
              <label className="mt-3 block text-sm" htmlFor="routine-name">
                {t("name")}
              </label>
              <Input
                className="mt-1 max-w-md"
                id="routine-name"
                onChange={(event) => setName(event.target.value)}
                value={name}
                required
              />
              <div className="mt-3 max-w-md">
                <ReferencePicker
                  label={t("agent")}
                  items={agents}
                  getDescription={(agent) => agent.slug || agent.id}
                  required
                  help={availability("help")}
                  emptyMessage={availability("empty")}
                  clearable={false}
                  disabled={busy || !catalogueReady || agents.length === 0}
                  onChange={setAgentId}
                  value={agentId}
                />
                {!loading && !error && agents.length === 0 ? (
                  <p className="mt-2 text-sm text-[var(--muted-foreground)]" role="status">
                    {availability("empty")}
                  </p>
                ) : null}
              </div>
              <label className="mt-3 block text-sm" htmlFor="routine-instructions">
                {t("instructions")}
              </label>
              <textarea
                className="mt-1 min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                id="routine-instructions"
                onChange={(event) => setInstructions(event.target.value)}
                value={instructions}
                required
              />
              <div className="mt-4">
                <ScheduleFields
                  cron={cron}
                  timezone={timezone}
                  onCronChange={(value) => {
                    setCron(value);
                    setPreview(null);
                  }}
                  onTimezoneChange={(value) => {
                    setTimezone(value);
                    setPreview(null);
                  }}
                />
              </div>
              <DeliveryFields idPrefix="routine" onChange={setDelivery} value={delivery} />
              <div className="mt-3 flex flex-wrap gap-2">
                <Button onClick={() => void showPreview()} type="button" variant="outline">
                  {t("preview")}
                </Button>
                <Button
                  disabled={
                    busy || !catalogueReady || !name.trim() || !instructions.trim() || !agentId
                  }
                  type="submit"
                >
                  {t("create")}
                </Button>
              </div>
              {preview ? (
                <div className="mt-3 text-sm text-[var(--muted-foreground)]">
                  <p>{preview.valid ? preview.description : t("invalidSchedule")}</p>
                  <ul className="mt-1 list-disc pl-5">
                    {preview.next.map((stamp) => (
                      <li key={stamp}>
                        <time dateTime={stamp}>{formatDateTime(stamp, locale)}</time>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </form>
          }
        >
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : null}
          {!loading && !error && rows.length === 0 ? <EmptyState title={t("empty")} /> : null}
          {!loading && rows.length > 0 ? (
            <div className="mb-4 flex flex-wrap gap-3">
              <Input
                aria-label={t("search")}
                placeholder={t("search")}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="min-w-0 flex-1"
                type="search"
              />
              <select
                aria-label={t("status")}
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                className="h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
              >
                <option value="">{t("allStatuses")}</option>
                {statuses.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {!loading && rows.length > 0 && filtered.length === 0 ? (
            <EmptyState title={t("noMatches")} />
          ) : null}
          <ul className="row-list">
            {pagination.rows.map((routine) => (
              <li className="p-4" key={routine.id}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium">{routine.name}</p>
                    <p className="text-sm text-[var(--muted-foreground)]">
                      {routine.triggerSummary || routine.triggerType}
                    </p>
                    <p className="mt-2 flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
                      <Badge tone={statusTone(routine.status)}>{routine.status}</Badge>
                      {routine.consecutiveFailures ? routine.consecutiveFailures : ""}
                    </p>
                  </div>
                  <Button asChild variant="outline">
                    <Link href={`/routines/${routine.id}`}>{t("open")}</Link>
                  </Button>
                </div>
              </li>
            ))}
          </ul>
          {!loading && rows.length > 0 ? <ListPagination {...pagination} /> : null}
        </ManagementLayout>
      </fieldset>
    </AppShell>
  );
}
