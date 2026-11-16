"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, BackButton, DetailState } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";

type Row = Record<string, unknown>;

const TABS = ["documents", "search", "sources", "jobs"] as const;

export function CollectionScreen({ collectionId }: { collectionId: string }) {
  const t = useTranslations("knowledge");
  const detail = useTranslations("detail");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const uploadInput = useRef<HTMLInputElement>(null);
  const [collection, setCollection] = useState<Row | null>(null);
  const [documents, setDocuments] = useState<Row[]>([]);
  const [sources, setSources] = useState<Row[]>([]);
  const [jobs, setJobs] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Row[]>([]);
  const [answerable, setAnswerable] = useState<boolean | null>(null);
  // False when no rerank model scored the passages: they are the closest ones, unjudged.
  const [scored, setScored] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [libraryId, setLibraryId] = useState("");
  const [libraryDocs, setLibraryDocs] = useState<Row[]>([]);
  const [pageUrl, setPageUrl] = useState("");
  const [connections, setConnections] = useState<Row[]>([]);
  const [connectionId, setConnectionId] = useState("");

  const load = useCallback(async () => {
    setCollection(null);
    setLoading(true);
    setError("");
    try {
      const [row, docs, src, jobPage, library, links] = await Promise.all([
        api<Row>(`/api/v1/knowledge/collections/${collectionId}`),
        api<{ items: Row[] }>(`/api/v1/knowledge/collections/${collectionId}/documents`),
        api<{ items: Row[] }>(`/api/v1/knowledge/collections/${collectionId}/sources`),
        api<{ items: Row[] }>(`/api/v1/knowledge/collections/${collectionId}/jobs`),
        api<{ items: Row[] }>("/api/v1/library-documents").catch(() => ({ items: [] })),
        api<{ items: Row[] }>("/api/v1/service-connections").catch(() => ({ items: [] })),
      ]);
      setCollection(row);
      setDocuments(docs.items ?? []);
      setSources(src.items ?? []);
      setJobs(jobPage.items ?? []);
      setLibraryDocs(library.items ?? []);
      setConnections(links.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [collectionId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function ask() {
    if (busy || !query.trim()) return;
    setBusy(true);
    setHits([]);
    setAnswerable(null);
    setError("");
    try {
      const result = await api<{ hits: Row[]; answerable: boolean; scored?: boolean }>(
        "/api/v1/knowledge/search",
        {
          method: "POST",
          body: JSON.stringify({ query, collectionIds: [collectionId], debug: true }),
        },
      );
      setHits(result.hits ?? []);
      setAnswerable(result.answerable);
      setScored(result.scored !== false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function upload() {
    if (!file || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const body = new FormData();
      body.set("upload", file);
      body.set("mime_type", file.type || "text/markdown");
      const uploaded = await api<{ id: string; status: string }>("/api/v1/files:upload", {
        method: "POST",
        body,
      });
      if (uploaded.status !== "ready") throw new Error(t("error"));
      await api(`/api/v1/knowledge/collections/${collectionId}/documents`, {
        method: "POST",
        body: JSON.stringify({ fileIds: [uploaded.id] }),
      });
      setFile(null);
      if (uploadInput.current) uploadInput.current.value = "";
      setNotice(detail("uploadSuccess"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function addMember(body: Record<string, string>) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`/api/v1/knowledge/collections/${collectionId}/members`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setNotice(detail("uploadSuccess"));
      setPageUrl("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function reindex(documentId: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/knowledge/documents/${documentId}:refresh`, { method: "POST" });
      setNotice(t("reindex"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function sync(sourceId: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`/api/v1/knowledge/sources/${sourceId}:sync`, {
        method: "POST",
        body: JSON.stringify({ mode: "incremental" }),
      });
      setNotice(detail("syncSuccess"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title={String(collection?.name || t("title"))}
        body={String(collection?.description || t("body"))}
        actions={
          <>
            <BackButton href="/knowledge">{t("back")}</BackButton>
            {collection && collection.canManage !== false ? (
              <Button asChild variant="outline">
                <Link href={`/knowledge/${collectionId}/sources/new`}>{t("connect")}</Link>
              </Button>
            ) : null}
          </>
        }
      />
      <DetailState loading={loading} error={error} onRetry={() => void load()} />
      <ActionStatus busy={busy} notice={notice} />
      {!loading && collection ? (
        <fieldset disabled={busy} className="min-w-0">
          <Facts
            className="mb-6"
            items={[
              {
                label: t("embedding"),
                value: collection.embeddingModel ? (
                  <span className="font-mono text-xs">{String(collection.embeddingModel)}</span>
                ) : null,
              },
              {
                label: t("documents"),
                value: (
                  <span className="tabular-nums">
                    {documents.length} ·{" "}
                    {t("chunks", {
                      count: Number((collection.stats as Row | undefined)?.chunks || 0),
                    })}
                  </span>
                ),
              },
            ]}
          />
          <Tabs defaultValue="documents">
            <TabsList>
              {TABS.map((item) => (
                <TabsTrigger key={item} value={item}>
                  {t(item)}
                </TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value="documents">
              <section>
                {collection.canManage !== false ? (
                  <div className="detail-panel mb-6">
                    <h2 className="panel-title mb-4">{t("addTitle")}</h2>
                    <form
                      className="flex flex-wrap items-end gap-3"
                      onSubmit={(event) => {
                        event.preventDefault();
                        void upload();
                      }}
                    >
                      <label className="min-w-0 flex-1 text-sm" htmlFor="knowledge-file">
                        {t("upload")}
                        <Input
                          ref={uploadInput}
                          className="mt-2 max-w-full"
                          id="knowledge-file"
                          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                          type="file"
                        />
                      </label>
                      <Button disabled={!file || busy} type="submit">
                        {t("upload")}
                      </Button>
                    </form>
                    <form
                      className="mt-5 grid gap-3 border-t border-[var(--border)] pt-5 md:grid-cols-[minmax(0,1fr)_auto]"
                      onSubmit={(event) => {
                        event.preventDefault();
                        if (libraryId)
                          void addMember({ kind: "library", libraryDocumentId: libraryId });
                      }}
                    >
                      <label className="text-sm" htmlFor="knowledge-library">
                        {t("library")}
                        <select
                          className="mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
                          id="knowledge-library"
                          onChange={(event) => setLibraryId(event.target.value)}
                          value={libraryId}
                        >
                          <option value="">{t("library")}</option>
                          {libraryDocs.map((row) => (
                            <option key={String(row.id)} value={String(row.id)}>
                              {String(row.title)}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="flex items-end">
                        <Button disabled={!libraryId || busy} type="submit">
                          {t("addLibrary")}
                        </Button>
                      </div>
                      <label className="text-sm" htmlFor="knowledge-url">
                        {t("url")}
                        <Input
                          className="mt-2"
                          id="knowledge-url"
                          onChange={(event) => setPageUrl(event.target.value)}
                          value={pageUrl}
                        />
                      </label>
                      <div className="flex items-end">
                        <Button
                          disabled={!pageUrl.trim() || busy}
                          onClick={() => void addMember({ kind: "url", url: pageUrl.trim() })}
                          type="button"
                        >
                          {t("addUrl")}
                        </Button>
                      </div>
                      <label className="text-sm" htmlFor="knowledge-connection">
                        {t("connection")}
                        <select
                          className="mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
                          id="knowledge-connection"
                          onChange={(event) => setConnectionId(event.target.value)}
                          value={connectionId}
                        >
                          <option value="">{t("connection")}</option>
                          {connections.map((row) => (
                            <option key={String(row.id)} value={String(row.id)}>
                              {String(row.name)}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="flex items-end">
                        <Button
                          disabled={!connectionId || busy}
                          onClick={() =>
                            void addMember({
                              kind: "connection",
                              connectionId,
                              url: pageUrl.trim(),
                            })
                          }
                          type="button"
                        >
                          {t("addConnection")}
                        </Button>
                      </div>
                    </form>
                  </div>
                ) : null}
                {documents.length === 0 ? <EmptyState title={t("emptyDocuments")} /> : null}
                <ul className="row-list">
                  {documents.map((row) => (
                    <li
                      className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                      key={String(row.id)}
                    >
                      <div className="min-w-0">
                        <p className="font-medium">{String(row.title)}</p>
                        <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
                          {t("chunks", { count: Number(row.chunkCount || 0) })}
                          {row.canRead === false ? ` · ${t("hidden")}` : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge tone={statusTone(String(row.status))}>{String(row.status)}</Badge>
                        {collection.canManage !== false ? (
                          <Button
                            className="h-8 text-xs"
                            onClick={() => void reindex(String(row.id))}
                            type="button"
                            variant="outline"
                          >
                            {t("reindex")}
                          </Button>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            </TabsContent>
            <TabsContent value="search">
              <form
                className="detail-panel grid gap-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void ask();
                }}
              >
                <label htmlFor="knowledge-query">
                  {t("query")}
                  <Input
                    id="knowledge-query"
                    onChange={(event) => setQuery(event.target.value)}
                    value={query}
                  />
                </label>
                <Button
                  className="justify-self-start"
                  disabled={!query.trim() || busy}
                  type="submit"
                >
                  {t("ask")}
                </Button>
                {answerable === true ? (
                  <p role="status">{scored ? t("answerable") : t("closest")}</p>
                ) : null}
                {answerable === false ? <p>{t("noHits")}</p> : null}
                <ul aria-label={t("hits")} className="row-list">
                  {hits.map((hit) => (
                    <li className="px-4 py-3" key={String(hit.chunkId)}>
                      <p className="font-medium">{String(hit.title)}</p>
                      <p className="mt-1 text-sm">{String(hit.snippet)}</p>
                      <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                        {hit.page
                          ? t("pageAnchor", {
                              page: String(hit.page),
                              anchor: String(hit.anchor || ""),
                            })
                          : null}{" "}
                        {hit.rerankScore === undefined || hit.rerankScore === null
                          ? null
                          : Number(hit.rerankScore).toFixed(2)}
                        {!scored && typeof hit.similarity === "number"
                          ? t("closeness", { percent: Math.round(hit.similarity * 100) })
                          : null}
                      </p>
                    </li>
                  ))}
                </ul>
              </form>
            </TabsContent>
            <TabsContent value="sources">
              {sources.length === 0 ? <EmptyState title={detail("noSources")} /> : null}
              <ul className="row-list">
                {sources.map((row) => (
                  <li
                    className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm"
                    key={String(row.id)}
                  >
                    <span className="font-medium">{String(row.name)}</span>
                    <span className="text-[var(--muted-foreground)]">{String(row.kind)}</span>
                    <Badge className="mr-auto" tone={statusTone(String(row.status))}>
                      {String(row.status)}
                    </Badge>
                    {collection.canManage !== false && row.kind !== "upload" ? (
                      <Button
                        onClick={() => void sync(String(row.id))}
                        type="button"
                        variant="outline"
                      >
                        {t("sync")}
                      </Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </TabsContent>
            <TabsContent value="jobs">
              {jobs.length === 0 ? <EmptyState title={detail("noJobs")} /> : null}
              <ul className="row-list">
                {jobs.map((row) => (
                  <li
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
                    key={String(row.id)}
                  >
                    <span className="font-medium">{String(row.kind)}</span>
                    <Badge tone={statusTone(String(row.status))}>{String(row.status)}</Badge>
                  </li>
                ))}
              </ul>
            </TabsContent>
          </Tabs>
        </fieldset>
      ) : null}
    </AppShell>
  );
}
