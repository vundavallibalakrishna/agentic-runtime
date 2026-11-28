"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { formatCount } from "@/lib/format";

const pageSizes = [25, 50, 100] as const;

/** Bounds rendered rows. Transport pagination remains the owning endpoint's responsibility. */
export function usePagedRows<T>(rows: T[], filterKey = "") {
  const [position, setPosition] = useState({ key: filterKey, page: 1 });
  const [pageSize, setPageSize] = useState<number>(pageSizes[0]);
  useEffect(() => {
    setPosition((current) => (current.key === filterKey ? current : { key: filterKey, page: 1 }));
  }, [filterKey]);
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  const page = Math.min(position.key === filterKey ? position.page : 1, pages);
  const setPage = (next: number) =>
    setPosition({ key: filterKey, page: Math.max(1, Math.min(next, pages)) });
  return {
    rows: rows.slice((page - 1) * pageSize, page * pageSize),
    page,
    pages,
    pageSize,
    total: rows.length,
    setPage,
    setPageSize: (size: number) => {
      setPageSize(size);
      setPage(1);
    },
  };
}

type SharedPagination = {
  label?: string;
  compact?: boolean;
  previousLabel?: string;
  nextLabel?: string;
};
type Pagination = SharedPagination &
  (
    | (Omit<ReturnType<typeof usePagedRows>, "rows"> & { cursor?: false })
    | {
        cursor: true;
        page: number;
        pageSize: number;
        count: number;
        canNext: boolean;
        disabled?: boolean;
        setPage: (page: number) => void;
        setPageSize: (size: number) => void;
      }
  );
export function ListPagination(props: Pagination) {
  const { page, pageSize, setPage, setPageSize, label, compact = false } = props;
  const disabled = props.cursor && props.disabled;
  const showNavigation = props.cursor ? true : props.pages > 1;
  const showPageSize = !compact && (props.cursor ? true : props.total > pageSizes[0]);
  const t = useTranslations("pagination");
  const previousLabel = props.previousLabel ?? t("previous");
  const nextLabel = props.nextLabel ?? t("next");
  return (
    <nav
      aria-label={label ? `${t("label")}: ${label}` : t("label")}
      className={
        compact
          ? "flex flex-col items-center gap-2 text-[11px]"
          : "mt-4 flex flex-wrap items-center justify-between gap-3 text-sm"
      }
    >
      <p className="text-[var(--muted-foreground)]" role="status" aria-live="polite">
        {props.cursor
          ? t("cursorRange", { count: formatCount(props.count) })
          : t("range", {
              start: formatCount(props.total ? (page - 1) * pageSize + 1 : 0),
              end: formatCount(Math.min(page * pageSize, props.total)),
              total: formatCount(props.total),
            })}
      </p>
      {showPageSize || showNavigation ? (
        <div className="flex flex-wrap items-center gap-2">
          {showPageSize ? (
            <label className="flex w-full items-center gap-2 sm:w-auto">
              {t("size")}
              <select
                className="h-9 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
                value={pageSize}
                onChange={(event) => setPageSize(Number(event.target.value))}
              >
                {pageSizes.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {showNavigation ? (
            <>
              <Button
                type="button"
                variant="outline"
                aria-label={compact ? previousLabel : undefined}
                className={
                  compact
                    ? props.previousLabel
                      ? "min-h-8 px-2 py-1 text-xs"
                      : "size-8 p-0"
                    : undefined
                }
                disabled={disabled || page <= 1}
                onClick={() => setPage(page - 1)}
              >
                {compact && !props.previousLabel ? (
                  <ChevronLeft size={14} aria-hidden="true" />
                ) : (
                  previousLabel
                )}
              </Button>
              <span className="whitespace-nowrap tabular-nums">
                {props.cursor
                  ? t("cursorPage", { page: formatCount(page) })
                  : t("page", { page: formatCount(page), pages: formatCount(props.pages) })}
              </span>
              <Button
                type="button"
                variant="outline"
                aria-label={compact ? nextLabel : undefined}
                className={
                  compact
                    ? props.nextLabel
                      ? "min-h-8 px-2 py-1 text-xs"
                      : "size-8 p-0"
                    : undefined
                }
                disabled={disabled || (props.cursor ? !props.canNext : page >= props.pages)}
                onClick={() => setPage(page + 1)}
              >
                {compact && !props.nextLabel ? (
                  <ChevronRight size={14} aria-hidden="true" />
                ) : (
                  nextLabel
                )}
              </Button>
            </>
          ) : null}
        </div>
      ) : null}
    </nav>
  );
}
