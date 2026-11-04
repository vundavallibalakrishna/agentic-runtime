"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
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

  async function compare() {
    if (!left || !right || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ id?: string }>(`/api/v1/library-documents/${left}:compare`, {
        method: "POST",
        body: JSON.stringify({ otherDocumentId: right }),
      });
      window.location.assign(`/documents/compare?comparisonId=${result.id ?? ""}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title={t("libraryTitle")}
        body={t("libraryBody")}
        actions={
          <label className="inline-flex cursor-pointer items-center">
            <span className="sr-only">{t("file")}</span>
            <input
              aria-label={t("file")}
              className="max-w-56 text-sm"
              type="file"
              onChange={(event) => void upload(event.target.files?.[0])}
            />
          </label>
        }
      />
      {loading ? <Skeleton className="h-40 w-full" /> : null}
      {error ? <p className="mb-4 text-sm text-[var(--destructive)]">{error}</p> : null}
      {!loading && items.length === 0 ? <EmptyState title={t("empty")} /> : null}
      {items.length > 0 ? (
        <div className="space-y-6">
          <ul className="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--card)]">
            {items.map((item) => {
              const id = text(item.id);
              return (
                <li
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                  key={id}
                >
                  <div>
                    <a className="font-medium underline" href={`/documents/${id}`}>
                      {text(item.title)}
                    </a>
                    <p className="text-sm text-[var(--muted-foreground)]">
                      {text(item.filename)} ·{" "}
                      {t("pages", { count: Number(item.pageCount ?? item.page_count ?? 0) })} ·{" "}
                      {t("ready")}
                    </p>
                  </div>
                  <a className="text-sm underline" href={`/documents/${id}`}>
                    {t("open")}
                  </a>
                </li>
              );
            })}
          </ul>
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
  const [busy, setBusy] = useState(false);

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

  async function runCheck() {
    setBusy(true);
    setError("");
    try {
      const result = await api<{ id?: string }>(`/api/v1/library-documents/${documentId}:check`, {
        method: "POST",
        body: JSON.stringify({
          requirements: requirements
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean),
          standardDocumentId: standard || null,
          label: "Check",
        }),
      });
      window.location.assign(`/documents/checks/${result.id ?? ""}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
      setBusy(false);
    }
  }

  async function runRewrite() {
    if (!instruction.trim()) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ id?: string }>(`/api/v1/library-documents/${documentId}:rewrite`, {
        method: "POST",
        body: JSON.stringify({ anchor, instruction }),
      });
      window.location.assign(`/documents/rewrites/${result.id ?? ""}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
      setBusy(false);
    }
  }

  const outline = rowsOf(doc?.outline);
  return (
    <AppShell>
      <PageHeader title={text(doc?.title) || t("viewTitle")} body={t("viewBody")} />
      <p className="mb-4 text-sm">
        <a className="underline" href="/documents">
          {t("back")}
        </a>
      </p>
      {loading ? <Skeleton className="h-48 w-full" /> : null}
      {error ? <p className="mb-4 text-sm text-[var(--destructive)]">{error}</p> : null}
      {!loading && doc ? (
        <div className="grid gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <aside className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h2 className="mb-3 text-sm font-semibold">{t("outline")}</h2>
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
            <section className="space-y-3">
              <h2 className="text-sm font-semibold">{t("passages")}</h2>
              {passages.length === 0 ? <EmptyState title={t("noPassages")} /> : null}
              {passages.map((passage) => (
                <article
                  className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
                  id={text(passage.anchor)}
                  key={text(passage.anchor)}
                >
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {text(passage.anchor)} · p.{text(passage.page)} · {text(passage.heading)}
                  </p>
                  <p className="mt-2 whitespace-pre-wrap text-sm">{text(passage.text)}</p>
                </article>
              ))}
            </section>
            <section>
              <h2 className="mb-3 text-sm font-semibold">{t("tables")}</h2>
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
            <form
              className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
              onSubmit={(event) => {
                event.preventDefault();
                void runCheck();
              }}
            >
              <h2 className="text-sm font-semibold">{t("check")}</h2>
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
              <Button disabled={busy} type="submit">
                {t("check")}
              </Button>
            </form>
            <form
              className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
              onSubmit={(event) => {
                event.preventDefault();
                void runRewrite();
              }}
            >
              <h2 className="text-sm font-semibold">{t("rewrite")}</h2>
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
              <Button disabled={busy || !instruction.trim()} type="submit">
                {t("previewRewrite")}
              </Button>
            </form>
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
      <PageHeader title={t("compareTitle")} body={t("compareBody")} />
      {loading ? <Skeleton className="h-40 w-full" /> : null}
      {error ? <p className="text-sm text-[var(--destructive)]">{error}</p> : null}
      {!loading && changes.length === 0 && !error ? <EmptyState title={t("noChanges")} /> : null}
      <ul className="space-y-4">
        {changes.map((change) => {
          const key = `${text(change.op)}-${text(change.leftAnchor || change.left_anchor)}-${text(change.rightAnchor || change.right_anchor)}`;
          const leftId = text(body?.leftId || body?.left_id);
          const rightId = text(body?.rightId || body?.right_id);
          const leftAnchor = text(change.leftAnchor || change.left_anchor);
          const rightAnchor = text(change.rightAnchor || change.right_anchor);
          return (
            <li className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4" key={key}>
              <p className="text-sm font-medium">
                {text(change.op) === "added"
                  ? t("added")
                  : text(change.op) === "removed"
                    ? t("removed")
                    : t("changed")}{" "}
                · {text(change.heading)}
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
      <PageHeader title={text(body?.label) || t("checkTitle")} body={t("checkBody")} />
      {loading ? <Skeleton className="h-40 w-full" /> : null}
      {error ? <p className="text-sm text-[var(--destructive)]">{error}</p> : null}
      {!loading && rows.length === 0 && !error ? <EmptyState title={t("missing")} /> : null}
      {rows.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-[var(--muted)]">
              <tr>
                <th className="px-3 py-2">{t("requirement")}</th>
                <th className="px-3 py-2">{t("verdict")}</th>
                <th className="px-3 py-2">{t("citation")}</th>
                <th className="px-3 py-2">{t("confidence")}</th>
                <th className="px-3 py-2">{t("reason")}</th>
              </tr>
            </thead>
            <tbody>
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
                  <tr
                    className="border-t border-[var(--border)]"
                    key={`${text(row.requirement)}-${anchor}`}
                  >
                    <td className="px-3 py-2">{text(row.requirement)}</td>
                    <td className="px-3 py-2">{text(row.verdict)}</td>
                    <td className="px-3 py-2">
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
                    </td>
                    <td className="px-3 py-2">{text(row.confidence)}</td>
                    <td className="px-3 py-2">{text(row.reason)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
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
      <PageHeader title={t("rewriteTitle")} body={t("rewriteBody")} />
      {loading ? <Skeleton className="h-40 w-full" /> : null}
      {error ? <p className="mb-4 text-sm text-[var(--destructive)]">{error}</p> : null}
      {body ? (
        <div className="space-y-4">
          <p className="text-sm text-[var(--muted-foreground)]">
            {text(body.instruction)} ·{" "}
            {status === "accepted"
              ? t("accepted")
              : status === "rejected"
                ? t("rejected")
                : t("proposed")}
          </p>
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
            <article
              className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
              key={text(hunk.id)}
            >
              <p className="text-xs text-[var(--muted-foreground)]">{text(hunk.op)}</p>
              <div className="mt-2 grid gap-3 md:grid-cols-2">
                <p className="whitespace-pre-wrap text-sm">{text(hunk.before)}</p>
                <p className="whitespace-pre-wrap text-sm">{text(hunk.after)}</p>
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
                <p className="mt-2 text-xs text-[var(--muted-foreground)]">{text(hunk.decision)}</p>
              )}
            </article>
          ))}
        </div>
      ) : null}
    </AppShell>
  );
}
