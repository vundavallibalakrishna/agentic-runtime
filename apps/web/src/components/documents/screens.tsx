"use client";

import { Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { BackButton } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
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
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");

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

  function compare() {
    if (!left || !right) return;
    setError("Compare documents in chat. The library does not run a fixed compare action.");
  }

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
                {items.map((item) => {
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
                        {text(item.mediaType ?? item.media_type) || "—"}
                      </TableCell>
                      <TableCell className="tabular-nums text-[var(--muted-foreground)]">
                        {Number(item.pageCount ?? item.page_count ?? 0)}
                      </TableCell>
                      <TableCell>
                        <Badge tone={text(item.status) === "failed" ? "danger" : "success"}>
                          {t(text(item.status) === "failed" ? "failed" : "ready")}
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
          <form
            className="grid gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 sm:grid-cols-[1fr_1fr_auto]"
            onSubmit={(event) => {
              event.preventDefault();
              void compare();
            }}
          >
            <label className="text-sm">
              {t("left")}
              <select
                aria-label={t("left")}
                className="mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
                value={left}
                onChange={(event) => setLeft(event.target.value)}
              >
                <option value="">{t("left")}</option>
                {items.map((item) => (
                  <option key={text(item.id)} value={text(item.id)}>
                    {text(item.title)}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              {t("right")}
              <select
                aria-label={t("right")}
                className="mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
                value={right}
                onChange={(event) => setRight(event.target.value)}
              >
                <option value="">{t("right")}</option>
                {items.map((item) => (
                  <option key={`right-${text(item.id)}`} value={text(item.id)}>
                    {text(item.title)}
                  </option>
                ))}
              </select>
            </label>
            <Button className="self-end" disabled={busy || !left || !right} type="submit">
              {t("compare")}
            </Button>
          </form>
        </div>
      ) : null}
    </AppShell>
  );
}

export function DocumentScreen({ documentId }: { documentId: string }) {
  const t = useTranslations("documents");
  const [doc, setDoc] = useState<Row | null>(null);
  const [passages, setPassages] = useState<Row[]>([]);
  const [tables, setTables] = useState<Row[]>([]);
  const [library, setLibrary] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [requirements, setRequirements] = useState("");
  const [standard, setStandard] = useState("");
  const [anchor, setAnchor] = useState("");
  const [instruction, setInstruction] = useState("");

  useEffect(() => {
    const hash = window.location.hash.replace("#", "");
    if (!hash || passages.length === 0) return;
    document.getElementById(hash)?.scrollIntoView({ block: "center" });
  }, [passages]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const [detail, passagePage, tablePage, list] = await Promise.all([
          api<Row>(`/api/v1/library-documents/${documentId}`),
          api<{ passages?: Row[] }>(
            `/api/v1/library-documents/${documentId}/passages?pageFrom=1&pageTo=400`,
          ),
          api<{ tables?: Row[] }>(`/api/v1/library-documents/${documentId}/tables`),
          api<{ items?: Row[] }>("/api/v1/library-documents"),
        ]);
        if (cancelled) return;
        setDoc(detail);
        setPassages(passagePage.passages ?? []);
        setTables(tablePage.tables ?? []);
        setLibrary(list.items ?? []);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : t("error"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [documentId, t]);

  function runCheck() {
    setError("Check a document in chat. The library does not run a fixed judge action.");
  }

  function runRewrite() {
    if (!instruction.trim()) return;
    setError("Edit a document in chat. The library does not change the stored original.");
  }

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
          {error}
        </p>
      ) : null}
      {!loading && doc ? (
        <div className="grid items-start gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <aside className="detail-panel p-4 lg:sticky lg:top-2 lg:max-h-[calc(100dvh-6rem)] lg:overflow-y-auto">
            <Facts
              className="mb-4 border-b border-[var(--border)] pb-4"
              items={[
                { label: t("type"), value: text(doc.mediaType) },
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
                  <span className="text-[var(--muted-foreground)]"> p.{text(item.page)}</span>
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
            <div className="grid items-start gap-6 xl:grid-cols-2">
              <form
                className="detail-panel space-y-3 p-5"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runCheck();
                }}
              >
                <h2 className="panel-title">{t("check")}</h2>
                <label className="block text-sm">
                  {t("requirements")}
                  <textarea
                    aria-label={t("requirements")}
                    className="mt-1 min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-2"
                    value={requirements}
                    onChange={(event) => setRequirements(event.target.value)}
                  />
                </label>
                <label className="block text-sm">
                  {t("standard")}
                  <select
                    aria-label={t("standard")}
                    className="mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2"
                    value={standard}
                    onChange={(event) => setStandard(event.target.value)}
                  >
                    <option value="">{t("standard")}</option>
                    {library
                      .filter((item) => text(item.id) !== documentId)
                      .map((item) => (
                        <option key={text(item.id)} value={text(item.id)}>
                          {text(item.title)}
                        </option>
                      ))}
                  </select>
                </label>
                <Button type="submit">
                  {t("check")}
                </Button>
              </form>
              <form
                className="detail-panel space-y-3 p-5"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runRewrite();
                }}
              >
                <h2 className="panel-title">{t("rewrite")}</h2>
                <label className="block text-sm" htmlFor="rewrite-anchor">
                  {t("anchor")}
                  <Input
                    aria-label={t("anchor")}
                    className="mt-1"
                    id="rewrite-anchor"
                    value={anchor}
                    onChange={(event) => setAnchor(event.target.value)}
                  />
                </label>
                <label className="block text-sm">
                  {t("instruction")}
                  <textarea
                    aria-label={t("instruction")}
                    className="mt-1 min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-2"
                    value={instruction}
                    onChange={(event) => setInstruction(event.target.value)}
                  />
                </label>
                <Button disabled={!instruction.trim()} type="submit">
                  {t("previewRewrite")}
                </Button>
              </form>
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}

export function CompareScreen({ comparisonId }: { comparisonId: string }) {
  const t = useTranslations("documents");
  const [body, setBody] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!comparisonId) {
        setLoading(false);
        setError(t("error"));
        return;
      }
      try {
        const result = await api<Row>(`/api/v1/document-comparisons/${comparisonId}`);
        if (!cancelled) setBody(result);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : t("error"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [comparisonId, t]);

  const changes = rowsOf(body?.changes);
  return (
    <AppShell>
      <PageHeader
        actions={<BackButton href="/documents">{t("back")}</BackButton>}
        body={t("compareBody")}
        title={t("compareTitle")}
      />
      {loading ? <Skeleton className="h-40 w-full" /> : null}
      {error ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      {!loading && changes.length === 0 && sectionsOf(body).length === 0 && !error ? (
        <EmptyState title={t("noChanges")} />
      ) : null}
      {sectionsOf(body).length > 0 ? (
        <ul className="grid gap-3">
          {sectionsOf(body).map((section) => (
            <li
              className="grid gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 md:grid-cols-2"
              key={`${text(section.status)}-${text(section.leftAnchor)}-${text(section.rightAnchor)}`}
            >
              <p className="md:col-span-2 text-sm font-medium">
                <Badge tone={text(section.status) === "paired" ? "neutral" : "warning"}>
                  {t(
                    text(section.status) === "added"
                      ? "added"
                      : text(section.status) === "removed"
                        ? "removed"
                        : "paired",
                  )}
                </Badge>{" "}
                {text(section.heading)}
              </p>
              <blockquote className="whitespace-pre-wrap text-sm">
                {text(section.leftQuote) || t("removed")}
              </blockquote>
              <blockquote className="whitespace-pre-wrap text-sm">
                {text(section.rightQuote) || t("added")}
              </blockquote>
            </li>
          ))}
        </ul>
      ) : null}
      <ul className="row-list">
        {changes.map((change) => {
          const key = `${text(change.op)}-${text(change.leftAnchor || change.left_anchor)}-${text(change.rightAnchor || change.right_anchor)}`;
          const leftId = text(body?.leftId || body?.left_id);
          const rightId = text(body?.rightId || body?.right_id);
          const leftAnchor = text(change.leftAnchor || change.left_anchor);
          const rightAnchor = text(change.rightAnchor || change.right_anchor);
          return (
            <li className="px-5 py-4" key={key}>
              <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                <Badge
                  tone={
                    text(change.op) === "added"
                      ? "success"
                      : text(change.op) === "removed"
                        ? "danger"
                        : "warning"
                  }
                >
                  {text(change.op) === "added"
                    ? t("added")
                    : text(change.op) === "removed"
                      ? t("removed")
                      : t("changed")}
                </Badge>
                {text(change.heading)}
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs text-[var(--muted-foreground)]">{t("before")}</p>
                  {leftAnchor ? (
                    <a className="text-xs underline" href={`/documents/${leftId}#${leftAnchor}`}>
                      {leftAnchor}
                    </a>
                  ) : null}
                  <p className="mt-1 whitespace-pre-wrap text-sm">{text(change.before)}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--muted-foreground)]">{t("after")}</p>
                  {rightAnchor ? (
                    <a className="text-xs underline" href={`/documents/${rightId}#${rightAnchor}`}>
                      {rightAnchor}
                    </a>
                  ) : null}
                  <p className="mt-1 whitespace-pre-wrap text-sm">{text(change.after)}</p>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </AppShell>
  );
}

export function CheckScreen({ checkId }: { checkId: string }) {
  const t = useTranslations("documents");
  const [body, setBody] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await api<Row>(`/api/v1/document-checks/${checkId}`);
        if (!cancelled) setBody(result);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : t("error"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [checkId, t]);

  const rows = rowsOf(body?.rows);
  return (
    <AppShell>
      <PageHeader
        actions={<BackButton href="/documents">{t("back")}</BackButton>}
        body={t("checkBody")}
        title={text(body?.label) || t("checkTitle")}
      />
      {loading ? <Skeleton className="h-40 w-full" /> : null}
      {error ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      {!loading && rows.length === 0 && !error ? <EmptyState title={t("missing")} /> : null}
      {rows.length > 0 ? (
        <TableScroll
          className="rounded-xl border border-[var(--border)] bg-[var(--card)]"
          label={t("checkTitle")}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">{t("requirement")}</TableHead>
                <TableHead scope="col">{t("verdict")}</TableHead>
                <TableHead scope="col">{t("citation")}</TableHead>
                <TableHead scope="col">{t("confidence")}</TableHead>
                <TableHead scope="col">{t("reason")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                const citation =
                  row.citation && typeof row.citation === "object" ? (row.citation as Row) : null;
                const documentId = text(
                  citation?.documentId ||
                    citation?.document_id ||
                    body?.documentId ||
                    body?.document_id,
                );
                const anchor = text(citation?.anchor);
                return (
                  <TableRow key={`${text(row.requirement)}-${anchor}`}>
                    <TableCell className="min-w-56">{text(row.requirement)}</TableCell>
                    <TableCell>
                      <Badge tone={statusTone(text(row.verdict))}>{text(row.verdict)}</Badge>
                    </TableCell>
                    <TableCell>
                      {anchor ? (
                        <a className="underline" href={`/documents/${documentId}#${anchor}`}>
                          {t("openPassage")} {anchor}
                        </a>
                      ) : (
                        t("notFound")
                      )}
                      {citation?.quote ? (
                        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                          {text(citation.quote)}
                        </p>
                      ) : null}
                    </TableCell>
                    <TableCell className="tabular-nums">{text(row.confidence)}</TableCell>
                    <TableCell>{text(row.reason)}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableScroll>
      ) : null}
    </AppShell>
  );
}

export function RewriteScreen({ rewriteId }: { rewriteId: string }) {
  const t = useTranslations("documents");
  const [body, setBody] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setBody(await api<Row>(`/api/v1/document-rewrites/${rewriteId}`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [rewriteId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function decide(decision: "accept" | "reject", hunkId = "") {
    setBusy(true);
    setError("");
    try {
      setBody(
        await api<Row>(`/api/v1/document-rewrites/${rewriteId}:decide`, {
          method: "POST",
          body: JSON.stringify({ decision, hunkId }),
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  const hunks = rowsOf(body?.hunks);
  const status = text(body?.status);
  return (
    <AppShell>
      <PageHeader
        actions={
          <>
            {status ? (
              <Badge tone={statusTone(status)}>
                {status === "accepted"
                  ? t("accepted")
                  : status === "rejected"
                    ? t("rejected")
                    : t("proposed")}
              </Badge>
            ) : null}
            <BackButton href="/documents">{t("back")}</BackButton>
          </>
        }
        body={t("rewriteBody")}
        title={t("rewriteTitle")}
      />
      {loading ? <Skeleton className="h-40 w-full" /> : null}
      {error ? (
        <p className="mb-4 text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      {body ? (
        <div className="space-y-4">
          <p className="text-sm text-[var(--muted-foreground)]">{text(body.instruction)}</p>
          {status === "proposed" ? (
            <div className="flex gap-2">
              <Button disabled={busy} type="button" onClick={() => void decide("accept")}>
                {t("acceptAll")}
              </Button>
              <Button
                disabled={busy}
                type="button"
                variant="outline"
                onClick={() => void decide("reject")}
              >
                {t("rejectAll")}
              </Button>
            </div>
          ) : null}
          {hunks.map((hunk) => (
            <article className="detail-panel p-5" key={text(hunk.id)}>
              <Badge>{text(hunk.op)}</Badge>
              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <div>
                  <p className="panel-title">{t("before")}</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{text(hunk.before)}</p>
                </div>
                <div>
                  <p className="panel-title">{t("after")}</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{text(hunk.after)}</p>
                </div>
              </div>
              {status === "proposed" && !hunk.decision ? (
                <div className="mt-3 flex gap-2">
                  <Button
                    disabled={busy}
                    type="button"
                    onClick={() => void decide("accept", text(hunk.id))}
                  >
                    {t("accept")}
                  </Button>
                  <Button
                    disabled={busy}
                    type="button"
                    variant="outline"
                    onClick={() => void decide("reject", text(hunk.id))}
                  >
                    {t("reject")}
                  </Button>
                </div>
              ) : (
                <p className="mt-3">
                  {hunk.decision ? (
                    <Badge tone={statusTone(text(hunk.decision))}>{text(hunk.decision)}</Badge>
                  ) : null}
                </p>
              )}
            </article>
          ))}
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

function sectionsOf(body: Record<string, unknown> | null): Record<string, unknown>[] {
  const raw = body?.sections;
  if (!Array.isArray(raw)) return [];
  return raw.filter((item): item is Record<string, unknown> => !!item && typeof item === "object");
}
