"use client";

import { type ReactNode, useId, useMemo, useState } from "react";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Row = Record<string, unknown>;
const rowStatus = (row: Row) => (typeof row.status === "string" ? row.status : "");

/** Shared loaded-record search/filter controls and bounded row rendering. */
export function RecordList({
  rows,
  label,
  emptyMessage,
  fields,
  labels,
  getStatus = rowStatus,
  initialQuery = "",
  children,
}: {
  rows: Row[];
  label: string;
  emptyMessage: string;
  fields: string[];
  initialQuery?: string;
  getStatus?: (row: Row) => string;
  labels: {
    search: string;
    status: string;
    allStatuses: string;
    clear: string;
    noMatches: string;
    statusValue?: (value: string) => string;
  };
  children: (row: Row) => ReactNode;
}) {
  const searchId = useId();
  const [query, setQuery] = useState(initialQuery);
  const [status, setStatus] = useState("");
  const statuses = useMemo(
    () => [...new Set(rows.flatMap((row) => (getStatus(row) ? [getStatus(row)] : [])))].sort(),
    [rows, getStatus],
  );
  const matching = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return rows.filter(
      (row) =>
        (!status || getStatus(row) === status) &&
        (!term ||
          fields.some(
            (field) =>
              typeof row[field] === "string" && row[field].toLocaleLowerCase().includes(term),
          )),
    );
  }, [rows, fields, query, status, getStatus]);
  const page = usePagedRows(matching, `${query}::${status}`);
  return (
    <section aria-label={label}>
      {rows.length ? (
        <>
          <div className="mb-4 grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
            <label htmlFor={searchId} className="min-w-0 text-sm">
              <span className="mb-1 block">{labels.search}</span>
              <Input
                id={searchId}
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <label className="min-w-0 text-sm">
              <span className="mb-1 block">{labels.status}</span>
              <select
                className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
                value={status}
                onChange={(event) => setStatus(event.target.value)}
              >
                <option value="">{labels.allStatuses}</option>
                {statuses.map((value) => (
                  <option key={value} value={value}>
                    {labels.statusValue?.(value) ?? value}
                  </option>
                ))}
              </select>
            </label>
            {query || status ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setQuery("");
                  setStatus("");
                }}
              >
                {labels.clear}
              </Button>
            ) : null}
          </div>
          {matching.length ? null : <EmptyState title={labels.noMatches} />}
          <ul className="row-list">{page.rows.map(children)}</ul>
          <ListPagination {...page} label={label} />
        </>
      ) : (
        <EmptyState title={emptyMessage} />
      )}
    </section>
  );
}
