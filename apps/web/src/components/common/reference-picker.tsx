"use client";

import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

export type Reference = {
  id: string;
  name?: string;
  displayName?: string;
  email?: string;
  kind?: string;
  title?: string;
  filename?: string;
  fileId?: string;
  qualifiedName?: string;
  toolId?: string;
  mediaType?: string;
  status?: string;
  disabled?: boolean;
};
type Props<T extends Reference> = {
  label: string;
  disabled?: boolean;
  compact?: boolean;
  hideLabel?: boolean;
  clearable?: boolean;
  emptyLabel?: string;
  resetLabel?: string;
  help?: string;
  emptyMessage?: string;
  required?: boolean;
  selection?: T | null | undefined;
  filterRow?: (row: T) => boolean;
  getValue?: (row: T) => string;
  getLabel?: (row: T) => string;
  getDescription?: (row: T) => string;
} & ({ endpoint: string; items?: never } | { endpoint?: never; items: T[] }) &
  (
    | { multiple?: false; value: string; onChange: (value: string) => void }
    | { multiple: true; value: string[]; onChange: (values: string[], rows: T[]) => void }
  );
const rowLabel = (row: Reference) =>
  row.name ||
  row.displayName ||
  row.title ||
  row.filename ||
  row.qualifiedName ||
  row.email ||
  row.id;
const rowValue = (row: Reference) => row.id;

const rowDescription = (row: Reference) =>
  [row.kind, row.email, row.filename || row.qualifiedName || row.id].filter(Boolean).join(" · ");

/** Selects real metadata from the caller's loaded list or its existing endpoint. */
export function ReferencePicker<T extends Reference = Reference>(props: Props<T>) {
  return <ReferenceChoices key={props.endpoint ?? "items"} {...props} />;
}

function ReferenceChoices<T extends Reference>(props: Props<T>) {
  const {
    label,
    endpoint,
    disabled = false,
    compact = false,
    getValue = rowValue,
    getLabel = rowLabel,
    getDescription = rowDescription,
    hideLabel = false,
    clearable = true,
  } = props;
  const t = useTranslations("referencePicker");
  const [open, setOpen] = useState(false);
  const visibleOpen = open && !disabled;
  const [rows, setRows] = useState<T[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [chosen, setChosen] = useState<T | null>(null);
  const [pending, setPending] = useState<string[]>([]);
  const active = useRef<AbortController | null>(null);
  const source = props.items ?? rows;
  const load = useCallback(async () => {
    if (!endpoint) return;
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    setError("");
    try {
      const page = await api<{ items?: T[]; data?: T[] }>(endpoint, { signal: controller.signal });
      if (!controller.signal.aborted) setRows(page.items ?? page.data ?? []);
    } catch (caught) {
      if (!controller.signal.aborted)
        setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [endpoint, t]);
  useEffect(() => {
    if (visibleOpen && endpoint) void load();
    return () => active.current?.abort();
  }, [visibleOpen, endpoint, load]);
  useEffect(() => {
    if (disabled) {
      active.current?.abort();
      setOpen(false);
      setPending([]);
    }
  }, [disabled]);
  const filterRow = props.filterRow;
  const available = useMemo(
    () =>
      visibleOpen
        ? [
            ...new Map(
              (source ?? [])
                .filter((row) => (filterRow?.(row) ?? true) && getValue(row))
                .map((row) => [getValue(row), row]),
            ).values(),
          ]
        : [],
    [source, visibleOpen, filterRow, getValue],
  );
  const pendingIds = new Set(pending);
  const term = query.trim().toLocaleLowerCase();
  const filtered = useMemo(
    () =>
      term
        ? available.filter((row) =>
            [
              row.name,
              row.displayName,
              row.email,
              row.title,
              row.filename,
              row.kind,
              row.id,
              row.fileId,
              row.qualifiedName,
              row.toolId,
              row.mediaType,
              getLabel(row),
              getDescription(row),
            ].some((text) => text?.toLocaleLowerCase().includes(term)),
          )
        : available,
    [available, term, getLabel, getDescription],
  );
  const pagination = usePagedRows(filtered, query);
  const value = props.multiple ? "" : props.value;
  const selected = useMemo(
    () =>
      (value ? source?.find((row) => getValue(row) === value) : null) ??
      (chosen && getValue(chosen) === value ? chosen : null) ??
      (props.selection && getValue(props.selection) === value ? props.selection : null),
    [source, value, getValue, chosen, props.selection],
  );
  const description = value
    ? selected
      ? getLabel(selected)
      : value
    : (props.emptyLabel ?? t(props.required ? "required" : "optional"));
  const buttonText =
    compact || props.multiple
      ? label
      : value
        ? selected
          ? getLabel(selected)
          : value
        : (props.emptyLabel ?? t("choose"));
  const details = (row: T) => {
    const description = getDescription(row);
    return (
      <>
        <span className="block break-words font-medium">{getLabel(row)}</span>
        {description ? (
          <span className="mt-1 block break-all text-xs text-[var(--muted-foreground)]">
            {description}
          </span>
        ) : null}
      </>
    );
  };

  return (
    <Dialog open={visibleOpen} onOpenChange={(next) => setOpen(next && !disabled)}>
      <div className="min-w-0">
        {!compact && !hideLabel ? <p className="mb-1 text-sm">{label}</p> : null}
        <div className="flex flex-wrap items-center gap-2">
          <DialogTrigger>
            <Button
              type="button"
              variant="outline"
              className={compact ? "min-w-0 max-w-full h-9 text-xs" : "min-w-0 max-w-full"}
              title={buttonText}
              disabled={disabled}
              aria-label={compact || props.multiple ? label : `${label}: ${buttonText}`}
              aria-description={
                props.multiple ? t("selected", { count: props.value.length }) : description
              }
              onClick={() => {
                setQuery("");
                setPending(props.multiple ? [...props.value] : []);
              }}
            >
              <span className="truncate">{buttonText}</span>
            </Button>
          </DialogTrigger>
          {!compact && !props.multiple ? (
            value ? (
              clearable && !props.resetLabel ? (
                <Button
                  type="button"
                  variant="ghost"
                  disabled={disabled}
                  aria-label={t("clearNamed", { label })}
                  onClick={() => {
                    if (!disabled) props.onChange("");
                  }}
                >
                  {t("clear")}
                </Button>
              ) : null
            ) : !hideLabel ? (
              <span className="text-xs text-[var(--muted-foreground)]">
                {t(props.required ? "required" : "optional")}
              </span>
            ) : null
          ) : null}
        </div>
        <DialogContent title={label}>
          {props.help ? (
            <p className="mt-3 text-sm text-[var(--muted-foreground)]">{props.help}</p>
          ) : null}
          <Input
            className="my-4"
            type="search"
            aria-label={t("search")}
            placeholder={t("search")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {!props.multiple && clearable && props.resetLabel ? (
            <Button
              className="mb-3"
              type="button"
              variant="outline"
              disabled={disabled || !value}
              onClick={() => {
                if (props.multiple || disabled) return;
                props.onChange("");
                setChosen(null);
                setOpen(false);
              }}
            >
              {props.resetLabel}
            </Button>
          ) : null}
          {loading || (source === null && !error) ? (
            <div role="status" aria-busy="true">
              <span className="sr-only">{t("loading")}</span>
              <Skeleton className="h-32 w-full" />
            </div>
          ) : error ? (
            <p role="alert" className="text-sm text-[var(--destructive)]">
              {error}{" "}
              <Button type="button" variant="outline" onClick={() => void load()}>
                {t("retry")}
              </Button>
            </p>
          ) : (
            <>
              {filtered.length === 0 ? (
                <p className="py-4 text-sm text-[var(--muted-foreground)]">
                  {query.trim() ? t("noMatches") : (props.emptyMessage ?? t("empty"))}
                </p>
              ) : null}
              <ul className="max-h-[45dvh] overflow-auto divide-y divide-[var(--border)]">
                {pagination.rows.map((row) => (
                  <li key={getValue(row)}>
                    {props.multiple ? (
                      <label className="flex cursor-pointer items-start gap-3 rounded-lg p-3 text-sm hover:bg-[var(--muted)]">
                        <input
                          className="mt-1"
                          type="checkbox"
                          disabled={disabled}
                          checked={pendingIds.has(getValue(row))}
                          aria-label={
                            row.qualifiedName && row.qualifiedName !== getLabel(row)
                              ? `${getLabel(row)} (${row.qualifiedName})`
                              : getLabel(row)
                          }
                          onChange={(event) =>
                            !disabled &&
                            setPending((current) =>
                              event.target.checked
                                ? [...new Set([...current, getValue(row)])]
                                : current.filter((id) => id !== getValue(row)),
                            )
                          }
                        />
                        <span className="min-w-0">{details(row)}</span>
                      </label>
                    ) : (
                      <button
                        type="button"
                        disabled={disabled}
                        aria-current={getValue(row) === value ? true : undefined}
                        aria-description={
                          getValue(row) === value ? t("currentSelection") : undefined
                        }
                        className={`flex w-full items-center gap-3 rounded-lg p-3 text-left text-sm hover:bg-[var(--muted)] focus-visible:outline-2 focus-visible:outline-[var(--ring)]${getValue(row) === value ? " bg-[var(--muted)]" : ""}`}
                        onClick={() => {
                          if (props.multiple || disabled) return;
                          setChosen(row);
                          const next = getValue(row);
                          if (next !== value) props.onChange(next);
                          setOpen(false);
                        }}
                      >
                        <span className="min-w-0 flex-1">{details(row)}</span>
                        {getValue(row) === value ? (
                          <Check
                            aria-hidden="true"
                            className="shrink-0 text-[var(--primary)]"
                            size={16}
                          />
                        ) : null}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
              {available.length > 0 ? (
                <ListPagination {...pagination} label={label} compact />
              ) : null}
            </>
          )}
          <div className="mt-4 flex flex-wrap justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("cancel")}
            </Button>
            {props.multiple ? (
              <Button
                type="button"
                disabled={disabled || loading || source === null || Boolean(error)}
                onClick={() => {
                  if (!props.multiple || disabled) return;
                  props.onChange(
                    pending,
                    available.filter((row) => pendingIds.has(getValue(row))),
                  );
                  setOpen(false);
                }}
              >
                {t("useSelected", { count: pending.length })}
              </Button>
            ) : null}
          </div>
        </DialogContent>
      </div>
    </Dialog>
  );
}
