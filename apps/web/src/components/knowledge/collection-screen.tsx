"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, BackButton, DetailState } from "@/components/common/detail-state";
import { Facts } from "@/components/common/facts";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { RecordList } from "@/components/common/record-list";
import { ReferencePicker } from "@/components/common/reference-picker";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";

type Row = Record<string, unknown>;

const TABS = ["documents", "search", "sources", "jobs"] as const;

function CollectionRecords(props: {
  rows: Row[];
  label: string;
  emptyMessage: string;
  fields: string[];
  children: (row: Row) => ReactNode;
}) {
  const t = useTranslations("knowledge");
  return (
    <RecordList
      {...props}
      labels={{
        search: t("findRecords", { label: props.label }),
        status: t("status"),
        allStatuses: t("allStatuses"),
        clear: t("clearFilters"),
        noMatches: t("noRecordMatches"),
      }}
    />
  );
}

export function CollectionScreen({ collectionId }: { collectionId: string }) {
  return <CollectionView key={collectionId} collectionId={collectionId} />;
}

function CollectionView({ collectionId }: { collectionId: string }) {
  const t = useTranslations("knowledge");
  const detail = useTranslations("detail");
  const readRequest = useRef<AbortController | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const [addKind, setAddKind] = useState("upload");
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
  const [searchedQuery, setSearchedQuery] = useState("");
  const [answerable, setAnswerable] = useState<boolean | null>(null);
  // False when no rerank model scored the passages: they are the closest ones, unjudged.
  const [scored, setScored] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [libraryId, setLibraryId] = useState("");
  const [pageUrl, setPageUrl] = useState("");
  const [connectionId, setConnectionId] = useState("");

  const load = useCallback(async () => {
    readRequest.current?.abort();
    const request = new AbortController();
    readRequest.current = request;
    setLoading(true);
    setError("");
    try {
      const [row, docs, src, jobPage] = await Promise.all([
        api<Row>(`/api/v1/knowledge/collections/${collectionId}`, { signal: request.signal }),
        api<{ items: Row[] }>(`/api/v1/knowledge/collections/${collectionId}/documents`, {
          signal: request.signal,
        }),
        api<{ items: Row[] }>(`/api/v1/knowledge/collections/${collectionId}/sources`, {
          signal: request.signal,
        }),
        api<{ items: Row[] }>(`/api/v1/knowledge/collections/${collectionId}/jobs`, {
          signal: request.signal,
        }),
      ]);
      if (request.signal.aborted) return;
      setCollection(row);
      setDocuments(docs.items ?? []);
      setSources(src.items ?? []);
      setJobs(jobPage.items ?? []);
    } catch (caught) {
      if (!request.signal.aborted) setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      if (readRequest.current === request) {
        readRequest.current = null;
        setLoading(false);
      }
    }
  }, [collectionId, t]);

  useEffect(() => {
    void load();
    return () => {
      readRequest.current?.abort();
      actionRequest.current?.abort();
    };
  }, [load]);

  const hitPage = usePagedRows(hits, searchedQuery);

  async function perform(action: (signal: AbortSignal) => Promise<void>) {
    if (actionRequest.current || loading) return;
    const request = new AbortController();
    actionRequest.current = request;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action(request.signal);
    } catch (caught) {
      if (!request.signal.aborted) setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      if (actionRequest.current === request) {
        actionRequest.current = null;
        setBusy(false);
      }
    }
  }

  async function ask() {
    if (!query.trim()) return;
    const submittedQuery = query;
    await perform(async (signal) => {
      setHits([]);
      setSearchedQuery("");
      setAnswerable(null);
      const result = await api<{ hits: Row[]; answerable: boolean; scored?: boolean }>(
        "/api/v1/knowledge/search",
        {
          method: "POST",
          signal,
          body: JSON.stringify({
            query: submittedQuery,
            collectionIds: [collectionId],
            debug: true,
          }),
        },
      );
      if (signal.aborted) return;
      setHits(result.hits ?? []);
      setSearchedQuery(submittedQuery);
      setAnswerable(result.answerable);
      setScored(result.scored !== false);
    });
  }

  async function upload() {
    if (!file || !collection || collection.canManage === false) return;
    await perform(async (signal) => {
      const body = new FormData();
      body.set("upload", file);
      body.set("mime_type", file.type || "text/markdown");
      const uploaded = await api<{ id?: string; status?: string }>("/api/v1/files:upload", {
        method: "POST",
        body,
        signal,
      });
      if (signal.aborted) return;
      if (uploaded.status !== "ready" || typeof uploaded.id !== "string" || !uploaded.id)
        throw new Error(t("uploadUnconfirmed"));
      await api(`/api/v1/knowledge/collections/${collectionId}/documents`, {
        method: "POST",
        signal,
        body: JSON.stringify({ fileIds: [uploaded.id] }),
      });
      if (signal.aborted) return;
      setFile(null);
      if (uploadInput.current) uploadInput.current.value = "";
      setNotice(detail("uploadSuccess"));
      await load();
    });
  }

  async function addMember(body: Record<string, string>) {
    if (!collection || collection.canManage === false) return;
    await perform(async (signal) => {
      await api(`/api/v1/knowledge/collections/${collectionId}/members`, {
        method: "POST",
        signal,
        body: JSON.stringify(body),
      });
      if (signal.aborted) return;
      setNotice(detail("uploadSuccess"));
      setPageUrl("");
      setLibraryId("");
      setConnectionId("");
      await load();
    });
  }

  async function reindex(documentId: string) {
    if (!collection || collection.canManage === false) return;
    await perform(async (signal) => {
      await api(`/api/v1/knowledge/documents/${documentId}:refresh`, { method: "POST", signal });
      if (signal.aborted) return;
      setNotice(t("refreshRequested"));
      await load();
    });
  }

  async function sync(sourceId: string) {
    if (!collection || collection.canManage === false) return;
    await perform(async (signal) => {
      await api(`/api/v1/knowledge/sources/${sourceId}:sync`, {
        method: "POST",
        signal,
        body: JSON.stringify({ mode: "incremental" }),
      });
      if (signal.aborted) return;
      setNotice(detail("syncSuccess"));
      await load();
    });
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
      <DetailState
        loading={loading && !collection}
        error={error}
        onRetry={busy ? undefined : () => void load()}
      />
      <ActionStatus busy={busy || (loading && Boolean(collection))} notice={notice} />
      {collection ? (
        <fieldset disabled={busy || loading} className="min-w-0">
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
                    <label className="mb-4 block max-w-sm text-sm" htmlFor="knowledge-add-kind">
                      {t("addMethod")}
                      <select
                        className="mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
                        id="knowledge-add-kind"
                        value={addKind}
                        onChange={(event) => setAddKind(event.target.value)}
                      >
                        <option value="upload">{t("upload")}</option>
                        <option value="library">{t("library")}</option>
                        <option value="url">{t("url")}</option>
                        <option value="connection">{t("connection")}</option>
                      </select>
                    </label>
                    {addKind === "upload" ? (
                      <form
                        className="flex flex-wrap items-end gap-3"
                        onSubmit={(event) => {
                          event.preventDefault();
                          void upload();
                        }}
                      >
                        <label
                          className="w-full min-w-0 text-sm sm:flex-1"
                          htmlFor="knowledge-file"
                        >
                          {t("upload")}
                          <Input
                            ref={uploadInput}
                            className="mt-2 max-w-full"
                            id="knowledge-file"
                            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                            type="file"
                          />
                        </label>
                        <Button className="w-full sm:w-auto" disabled={!file || busy} type="submit">
                          {t("upload")}
                        </Button>
                      </form>
                    ) : (
                      <form
                        className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]"
                        onSubmit={(event) => {
                          event.preventDefault();
                          if (addKind === "library" && libraryId)
                            void addMember({ kind: "library", libraryDocumentId: libraryId });
                          if (addKind === "url" && pageUrl.trim())
                            void addMember({ kind: "url", url: pageUrl.trim() });
                          if (addKind === "connection" && connectionId)
                            void addMember({
                              kind: "connection",
                              connectionId,
                              url: pageUrl.trim(),
                            });
                        }}
                      >
                        {addKind === "library" ? (
                          <>
                            <ReferencePicker
                              label={t("library")}
                              endpoint="/api/v1/library-documents"
                              value={libraryId}
                              onChange={setLibraryId}
                              required
                              disabled={busy}
                            />
                            <div className="flex items-end">
                              <Button disabled={!libraryId || busy} type="submit">
                                {t("addLibrary")}
                              </Button>
                            </div>
                          </>
                        ) : null}
                        {addKind === "url" ? (
                          <>
                            <label className="text-sm" htmlFor="knowledge-url">
                              {t("url")}
                              <Input
                                className="mt-2"
                                id="knowledge-url"
                                type="url"
                                required
                                onChange={(event) => setPageUrl(event.target.value)}
                                value={pageUrl}
                              />
                            </label>
                            <div className="flex items-end">
                              <Button disabled={!pageUrl.trim() || busy} type="submit">
                                {t("addUrl")}
                              </Button>
                            </div>
                          </>
                        ) : null}
                        {addKind === "connection" ? (
                          <>
                            <label
                              className="text-sm md:col-span-2"
                              htmlFor="knowledge-connection-url"
                            >
                              {t("url")}
                              <Input
                                className="mt-2"
                                id="knowledge-connection-url"
                                type="url"
                                onChange={(event) => setPageUrl(event.target.value)}
                                value={pageUrl}
                              />
                            </label>
                            <ReferencePicker
                              label={t("connection")}
                              endpoint="/api/v1/service-connections"
                              value={connectionId}
                              onChange={setConnectionId}
                              required
                              disabled={busy}
                            />
                            <div className="flex items-end">
                              <Button disabled={!connectionId || busy} type="submit">
                                {t("addConnection")}
                              </Button>
                            </div>
                          </>
                        ) : null}
                      </form>
                    )}
                  </div>
                ) : null}
                <CollectionRecords
                  rows={documents}
                  label={t("documents")}
                  emptyMessage={t("emptyDocuments")}
                  fields={["id", "title", "status", "fileId"]}
                >
                  {(row) => (
                    <li
                      className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                      key={String(row.id)}
                    >
                      <div className="min-w-0">
                        <p className="break-words font-medium">{String(row.title ?? row.id)}</p>
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
                  )}
                </CollectionRecords>
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
                {searchedQuery ? (
                  <p className="break-words text-sm text-[var(--muted-foreground)]">
                    {t("resultsFor", { query: searchedQuery })}
                  </p>
                ) : null}
                <ul aria-label={t("hits")} className="row-list">
                  {hitPage.rows.map((hit) => (
                    <li className="px-4 py-3" key={String(hit.chunkId)}>
                      <p className="break-words font-medium">{String(hit.title ?? "")}</p>
                      <p className="mt-1 break-words text-sm">{String(hit.snippet ?? "")}</p>
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
                {hits.length ? <ListPagination {...hitPage} label={t("hits")} /> : null}
              </form>
            </TabsContent>
            <TabsContent value="sources">
              <CollectionRecords
                rows={sources}
                label={t("sources")}
                emptyMessage={detail("noSources")}
                fields={["id", "name", "kind", "status"]}
              >
                {(row) => (
                  <li
                    className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm"
                    key={String(row.id)}
                  >
                    <span className="max-w-full break-all font-medium">
                      {String(row.name ?? row.id)}
                    </span>
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
                )}
              </CollectionRecords>
            </TabsContent>
            <TabsContent value="jobs">
              <CollectionRecords
                rows={jobs}
                label={t("jobs")}
                emptyMessage={detail("noJobs")}
                fields={["id", "kind", "status"]}
              >
                {(row) => (
                  <li
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
                    key={String(row.id)}
                  >
                    <span className="font-medium">{String(row.kind)}</span>
                    <Badge tone={statusTone(String(row.status))}>{String(row.status)}</Badge>
                  </li>
                )}
              </CollectionRecords>
            </TabsContent>
          </Tabs>
        </fieldset>
      ) : null}
    </AppShell>
  );
}
