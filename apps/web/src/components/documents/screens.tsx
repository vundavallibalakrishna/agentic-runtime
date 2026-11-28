"use client";

import { Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { BackButton } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableScroll,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { fileTypeKey } from "@/lib/file-type";

/** A file's type in plain words; a type with no name is shown as the server sent it. */
function typeLabel(t: (key: string) => string, mediaType: string): string {
  const key = fileTypeKey(mediaType);
  return key ? t(`fileType.${key}`) : mediaType;
}

type Row = Record<string, unknown>;

function text(value: unknown) {
  return value == null ? "" : String(value);
}

function rowsOf(value: unknown): Row[] {
  return Array.isArray(value)
    ? value.filter((item): item is Row => !!item && typeof item === "object")
    : [];
}

export function LibraryScreen() {
  const t = useTranslations("documents");
  const [items, setItems] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api<{ items?: Row[] }>("/api/v1/library-documents");
      setItems(page.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function upload(file: File | undefined) {
    if (!file || busy) return;
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.set("upload", file);
      await api("/api/v1/library-documents", { method: "POST", body });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  const matching = useMemo(
    () =>
      items.filter((item) =>
        [item.title, item.filename, item.mediaType ?? item.media_type]
          .join(" ")
          .toLocaleLowerCase()
          .includes(query.trim().toLocaleLowerCase()),
      ),
    [items, query],
  );
  const pagination = usePagedRows(matching, query);

  return (
    <AppShell>
      <PageHeader
        title={t("libraryTitle")}
        body={t("libraryBody")}
        actions={
          <label
            className={
              "inline-flex h-10 cursor-pointer items-center gap-2 rounded-md bg-[var(--primary)] px-4 text-sm font-medium text-[var(--primary-foreground)] hover:bg-[var(--primary-hover)] focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[var(--ring)]" +
              (busy ? " pointer-events-none opacity-60" : "")
            }
          >
            <Upload size={16} aria-hidden="true" />
            <span aria-hidden="true">{busy ? t("uploading") : t("upload")}</span>
            <input
              aria-label={t("file")}
              className="sr-only"
              disabled={busy}
              type="file"
              onChange={(event) => void upload(event.target.files?.[0])}
            />
          </label>
        }
      />
      {loading ? <Skeleton className="h-40 w-full" /> : null}
      {error ? (
        <p className="mb-4 text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      {!loading && !error && items.length === 0 ? <EmptyState title={t("empty")} /> : null}
      {items.length > 0 ? (
        <label className="mb-5 block max-w-md text-sm" htmlFor="document-search">
          {t("searchDocuments")}
          <Input
            className="mt-2"
            id="document-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
      ) : null}
      {items.length > 0 && matching.length === 0 ? (
        <p className="mb-4 text-sm text-[var(--muted-foreground)]" role="status">
          {t("noMatches")}
        </p>
      ) : null}
      {items.length > 0 ? (
        <div className="space-y-6">
          <TableScroll
            className="rounded-xl border border-[var(--border)] bg-[var(--card)]"
            label={t("libraryTitle")}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead scope="col">{t("document")}</TableHead>
                  <TableHead scope="col">{t("type")}</TableHead>
                  <TableHead scope="col">{t("pagesColumn")}</TableHead>
                  <TableHead scope="col">{t("status")}</TableHead>
                  <TableHead scope="col">
                    <span className="sr-only">{t("open")}</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pagination.rows.map((item) => {
                  const id = text(item.id);
                  return (
                    <TableRow className="hover:bg-[var(--muted)]" key={id}>
                      <TableCell className="min-w-56">
                        <a className="font-semibold hover:underline" href={`/documents/${id}`}>
                          {text(item.title)}
                        </a>
                        <p className="mt-0.5 break-all text-[var(--muted-foreground)]">
                          {text(item.filename)}
                        </p>
                      </TableCell>
                      <TableCell className="text-[var(--muted-foreground)]">
                        {typeLabel(t, text(item.mediaType ?? item.media_type)) || "—"}
                      </TableCell>
                      <TableCell className="tabular-nums text-[var(--muted-foreground)]">
                        {Number(item.pageCount ?? item.page_count ?? 0)}
                      </TableCell>
                      <TableCell>
                        <Badge tone={statusTone(text(item.status) || "ready")}>
                          {item.status
                            ? t.has(text(item.status))
                              ? t(text(item.status))
                              : text(item.status)
                            : t("ready")}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          className="mr-2 h-8 text-xs"
                          onClick={() => {
                            if (!window.confirm(t("deleteConfirm", { name: text(item.title) }))) {
                              return;
                            }
                            void api(`/api/v1/library-documents/${id}`, { method: "DELETE" })
                              .then(() => load())
                              .catch(() => setError(t("error")));
                          }}
                          type="button"
                          variant="outline"
                        >
                          {t("delete")}
                        </Button>
                        <Button asChild className="h-8 text-xs" variant="outline">
                          <a
                            aria-label={`${t("open")}: ${text(item.title)}`}
                            href={`/documents/${id}`}
                          >
                            {t("open")}
                          </a>
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableScroll>
          <ListPagination {...pagination} />
          {items.length > 1 ? <ComparePicker items={items} /> : null}
          <DocumentChatAction />
        </div>
      ) : null}
    </AppShell>
  );
}

/** Choose two documents and open what differs between them. */
function ComparePicker({ items }: { items: Row[] }) {
  const t = useTranslations("documents");
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const ready = left !== "" && right !== "" && left !== right;
  const sides = [
    { id: "compare-left", label: t("left"), value: left, set: setLeft },
    { id: "compare-right", label: t("right"), value: right, set: setRight },
  ];
  return (
    <section
      aria-labelledby="compare-heading"
      className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
    >
      <h2 className="panel-title" id="compare-heading">
        {t("compareHeading")}
      </h2>
      <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("compareHint")}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
        {sides.map((side) => (
          <label className="text-sm" htmlFor={side.id} key={side.id}>
            {side.label}
            <select
              className="mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
              id={side.id}
              onChange={(event) => side.set(event.target.value)}
              value={side.value}
            >
              <option value="">{t("choose")}</option>
              {items.map((item) => (
                <option key={text(item.id)} value={text(item.id)}>
                  {text(item.title)}
                </option>
              ))}
            </select>
          </label>
        ))}
        {ready ? (
          <Button asChild className="self-end">
            <a href={`/documents/compare?left=${left}&right=${right}`}>{t("compare")}</a>
          </Button>
        ) : (
          <Button className="self-end" disabled type="button">
            {t("compare")}
          </Button>
        )}
      </div>
    </section>
  );
}

export function DocumentScreen({ documentId }: { documentId: string }) {
  const t = useTranslations("documents");
  const [doc, setDoc] = useState<Row | null>(null);
  const [passages, setPassages] = useState<Row[]>([]);
  const [tables, setTables] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const requestVersion = useRef(0);

  useEffect(() => {
    const hash = window.location.hash.replace("#", "");
    if (!hash || passages.length === 0) return;
    document.getElementById(hash)?.scrollIntoView({ block: "center" });
  }, [passages]);

  const load = useCallback(async () => {
    const version = ++requestVersion.current;
    setLoading(true);
    setError("");
    setDoc(null);
    try {
      const [detail, passagePage, tablePage] = await Promise.all([
        api<Row>(`/api/v1/library-documents/${documentId}`),
        api<{ passages?: Row[] }>(
          `/api/v1/library-documents/${documentId}/passages?pageFrom=1&pageTo=400`,
        ),
        api<{ tables?: Row[] }>(`/api/v1/library-documents/${documentId}/tables`),
      ]);
      if (version !== requestVersion.current) return;
      setDoc(detail);
      setPassages(passagePage.passages ?? []);
      setTables(tablePage.tables ?? []);
    } catch (caught) {
      if (version === requestVersion.current)
        setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [documentId, t]);
  useEffect(() => {
    void load();
    return () => {
      requestVersion.current += 1;
    };
  }, [load]);

  const outline = rowsOf(doc?.outline);
  return (
    <AppShell>
      <PageHeader
        actions={<BackButton href="/documents">{t("back")}</BackButton>}
        body={t("viewBody")}
        title={text(doc?.title) || t("viewTitle")}
      />
      {loading ? <Skeleton className="h-48 w-full" /> : null}
      {error ? (
        <p className="mb-4 text-sm text-[var(--destructive)]" role="alert">
          {error}{" "}
          <Button type="button" variant="outline" onClick={() => void load()}>
            {t("retry")}
          </Button>
        </p>
      ) : null}
      {!loading && doc ? (
        <div className="grid items-start gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <aside className="detail-panel p-4 lg:sticky lg:top-2 lg:max-h-[calc(100dvh-6rem)] lg:overflow-y-auto">
            <Facts
              className="mb-4 border-b border-[var(--border)] pb-4"
              items={[
                { label: t("type"), value: typeLabel(t, text(doc.mediaType)) },
                { label: t("pagesColumn"), value: text(doc.pageCount) },
              ]}
            />
            <h2 className="panel-title mb-3">{t("outline")}</h2>
            <ul className="space-y-2 text-sm">
              {outline.map((item) => (
                <li key={text(item.anchor)}>
                  <a className="underline" href={`#${text(item.anchor)}`}>
                    {text(item.heading)}
                  </a>
                  {item.pageFrom != null ? (
                    <span className="text-[var(--muted-foreground)]">
                      {" "}
                      p.{text(item.pageFrom)}
                      {item.pageTo != null && item.pageTo !== item.pageFrom
                        ? `–${text(item.pageTo)}`
                        : ""}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </aside>
          <div className="space-y-6">
            <section>
              <h2 className="panel-title mb-3">{t("passages")}</h2>
              {passages.length === 0 ? <EmptyState title={t("noPassages")} /> : null}
              <ul className="row-list">
                {passages.map((passage) => (
                  <li
                    className="scroll-mt-4 px-5 py-4 target:bg-[var(--muted)]"
                    id={text(passage.anchor)}
                    key={text(passage.anchor)}
                  >
                    <p className="text-xs text-[var(--muted-foreground)]">
                      <span className="font-mono">{text(passage.anchor)}</span> · p.
                      {text(passage.page)} · {text(passage.heading)}
                    </p>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">
                      <Highlighted
                        text={text(passage.text)}
                        active={hashIs(text(passage.anchor))}
                      />
                    </p>
                  </li>
                ))}
              </ul>
            </section>
            <section>
              <h2 className="panel-title mb-3">{t("tables")}</h2>
              {tables.length === 0 ? (
                <p className="text-sm text-[var(--muted-foreground)]">{t("noTables")}</p>
              ) : null}
              {tables.map((table) => (
                <pre
                  className="mb-3 overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--muted)] p-3 text-xs"
                  key={text(table.anchor)}
                >
                  {text(table.caption)}
                  {"\n"}
                  {text(table.csv)}
                </pre>
              ))}
            </section>
            <DocumentChatAction />
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}

function hashIs(anchor: string): boolean {
  if (!anchor || typeof window === "undefined") return false;
  return window.location.hash === `#${anchor}`;
}

function Highlighted({ text: value, active }: { text: string; active: boolean }) {
  if (!active || !value) return value;
  return <mark className="bg-[var(--muted)] text-[var(--foreground)]">{value}</mark>;
}

function DocumentChatAction() {
  const t = useTranslations("documents");
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <p className="max-w-xl text-sm text-[var(--muted-foreground)]">{t("chatWorkHelp")}</p>
      <Button asChild variant="outline">
        <a href="/chat">{t("chatWork")}</a>
      </Button>
    </div>
  );
}
