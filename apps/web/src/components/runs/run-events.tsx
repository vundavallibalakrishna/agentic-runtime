"use client";

import { client } from "@ar/api-client";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { DetailState } from "@/components/common/detail-state";
import { ListPagination } from "@/components/common/list-pagination";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TableScroll } from "@/components/ui/table";
import { formatCount } from "@/lib/format";
import { streamHeaders } from "@/lib/stream/reconnect";

type EventRow = { seq: number; type: string; ts: string; [key: string]: unknown };
function isEvent(value: unknown): value is EventRow {
  if (!value || typeof value !== "object") return false;
  const row = value as Partial<EventRow>;
  return (
    Number.isSafeInteger(row.seq) &&
    Number(row.seq) > 0 &&
    typeof row.type === "string" &&
    typeof row.ts === "string"
  );
}

export function RunEvents({ runId }: { runId: string }) {
  const [cursors, setCursors] = useState([0]);
  const [pageSize, setPageSize] = useState(25);
  return (
    <EventPage
      key={`${runId}:${cursors.length}:${pageSize}`}
      runId={runId}
      cursor={cursors[cursors.length - 1] ?? 0}
      page={cursors.length}
      pageSize={pageSize}
      onPrevious={() => setCursors((value) => value.slice(0, -1))}
      onNext={(seq) => setCursors((value) => [...value, seq])}
      onSize={(size) => {
        setPageSize(size);
        setCursors([0]);
      }}
    />
  );
}

function EventPage({
  runId,
  cursor,
  page,
  pageSize,
  onPrevious,
  onNext,
  onSize,
}: {
  runId: string;
  cursor: number;
  page: number;
  pageSize: number;
  onPrevious: () => void;
  onNext: (seq: number) => void;
  onSize: (size: number) => void;
}) {
  const t = useTranslations("runs");
  const [rows, setRows] = useState<EventRow[]>([]);
  const [state, setState] = useState<"loading" | "full" | "end" | "stopped" | "error">("loading");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [attempt, setAttempt] = useState(0);
  const request = useRef<AbortController | null>(null);
  // biome-ignore lint/correctness/useExhaustiveDependencies: an explicit retry restarts this read without discarding received rows
  useEffect(() => {
    const controller = new AbortController();
    request.current = controller;
    let alive = true;
    setState("loading");
    setError("");
    async function read() {
      const received: EventRow[] = [];
      let last = cursor;
      let failed = false;
      try {
        const { stream } = await client.sse.get({
          baseUrl: window.location.origin,
          url: `/api/v1/runs/${encodeURIComponent(runId)}/events`,
          credentials: "include",
          cache: "no-store",
          signal: controller.signal,
          headers: { Accept: "text/event-stream", ...streamHeaders(cursor) },
          sseMaxRetryAttempts: 1,
          onSseError: () => {
            failed = true;
          },
        });
        for await (const value of stream) {
          if (!alive || controller.signal.aborted) return;
          if (!isEvent(value)) throw new Error(t("eventsInvalid"));
          if (value.seq <= last) continue;
          received.push(value);
          last = value.seq;
          setRows([...received]);
          if (received.length === pageSize) {
            setState("full");
            controller.abort();
            return;
          }
        }
        if (!alive || controller.signal.aborted) return;
        if (failed) throw new Error(t("eventsError"));
        setRows(received);
        setState("end");
      } catch (caught) {
        if (!alive || controller.signal.aborted) return;
        setError(caught instanceof Error ? caught.message : t("eventsError"));
        setState("error");
      } finally {
        controller.abort();
      }
    }
    void read();
    return () => {
      alive = false;
      controller.abort();
    };
  }, [runId, cursor, pageSize, attempt, t]);
  const matching = rows.filter(
    (row) =>
      (!kind || row.type === kind) &&
      JSON.stringify(row).toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
  );
  const loading = state === "loading";
  return (
    <section aria-label={t("events")} className="detail-panel space-y-4">
      <p className="text-sm text-[var(--muted-foreground)]">{t("eventsHelp")}</p>
      <div className="flex flex-wrap items-center gap-3">
        <Input
          type="search"
          className="min-w-0 sm:w-auto sm:flex-1"
          aria-label={t("eventSearch")}
          placeholder={t("eventSearch")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <label className="flex items-center gap-2 text-sm">
          {t("eventType")}
          <select
            className="h-10 min-w-0 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
            value={kind}
            onChange={(event) => setKind(event.target.value)}
          >
            <option value="">{t("allEventTypes")}</option>
            {[...new Set(rows.map((row) => row.type))].sort().map((type) => (
              <option key={type}>{type}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <p role="status" className="text-sm text-[var(--muted-foreground)]">
          {t(
            loading
              ? "eventsLoading"
              : state === "stopped"
                ? "eventsStopped"
                : state === "full"
                  ? "eventsPageFull"
                  : state === "end"
                    ? "eventsEnd"
                    : "eventsError",
          )}
        </p>
        {loading ? (
          <Button
            variant="outline"
            onClick={() => {
              request.current?.abort();
              setState("stopped");
            }}
          >
            {t("eventsStop")}
          </Button>
        ) : (
          <Button variant="outline" onClick={() => setAttempt((value) => value + 1)}>
            {t("eventsRetry")}
          </Button>
        )}
      </div>
      <DetailState loading={false} error={error} />
      {!matching.length && !loading && !error ? (
        <p className="text-sm">{query || kind ? t("eventsNoMatches") : t("noEvents")}</p>
      ) : null}
      <ol className="divide-y divide-[var(--border)]">
        {matching.map((row) => (
          <EventEntry key={row.seq} row={row} />
        ))}
      </ol>
      <ListPagination
        cursor
        label={t("events")}
        page={page}
        pageSize={pageSize}
        count={matching.length}
        disabled={loading}
        canNext={(state === "full" || state === "stopped") && rows.length > 0}
        setPage={(next) =>
          next < page ? onPrevious() : onNext(rows[rows.length - 1]?.seq ?? cursor)
        }
        setPageSize={onSize}
      />
    </section>
  );
}
function EventEntry({ row }: { row: EventRow }) {
  const t = useTranslations("runs");
  const [open, setOpen] = useState(false);
  return (
    <li className="py-3 text-sm">
      <details onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary className="cursor-pointer break-words font-medium">
          {t("eventSequence")} {formatCount(row.seq)} · {row.type}
        </summary>
        {open ? (
          <div className="mt-3 space-y-2">
            <p className="break-words text-xs text-[var(--muted-foreground)]">
              {t("eventTime")}: {row.ts}
            </p>
            <TableScroll
              label={t("eventsPayload")}
              className="max-h-80 rounded-lg bg-[var(--muted)] p-3"
            >
              <pre className="whitespace-pre-wrap break-words text-xs">
                {JSON.stringify(row, null, 2)}
              </pre>
            </TableScroll>
          </div>
        ) : null}
      </details>
    </li>
  );
}
