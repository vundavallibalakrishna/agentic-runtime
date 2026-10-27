"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, BackButton, DetailState } from "@/components/common/detail-state";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
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
  const [query, setQuery] = useState("When does the visitor desk open?");
  const [hits, setHits] = useState<Row[]>([]);
  const [answerable, setAnswerable] = useState<boolean | null>(null);
  const [file, setFile] = useState<File | null>(null);

  const load = useCallback(async () => {
    setCollection(null);
    setLoading(true);
    setError("");
    try {
      const [row, docs, src, jobPage] = await Promise.all([
        api<Row>(`/api/v1/knowledge/collections/${collectionId}`),
        api<{ items: Row[] }>(`/api/v1/knowledge/collections/${collectionId}/documents`),
        api<{ items: Row[] }>(`/api/v1/knowledge/collections/${collectionId}/sources`),
        api<{ items: Row[] }>(`/api/v1/knowledge/collections/${collectionId}/jobs`),
      ]);
      setCollection(row);
      setDocuments(docs.items ?? []);
      setSources(src.items ?? []);
      setJobs(jobPage.items ?? []);
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
      const result = await api<{ hits: Row[]; answerable: boolean }>("/api/v1/knowledge/search", {
        method: "POST",
        body: JSON.stringify({ query, collectionIds: [collectionId], debug: true }),
      });
      setHits(result.hits ?? []);
      setAnswerable(result.answerable);
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
                  <form
                    className="detail-panel mb-6 flex flex-wrap items-end gap-3"
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
                ) : null}
                {documents.length === 0 ? <EmptyState title={t("emptyDocuments")} /> : null}
                <ul className="divide-y divide-[var(--border)]">
                  {documents.map((row) => (
                    <li className="py-3" key={String(row.id)}>
                      <p className="font-medium">{String(row.title)}</p>
                      <p className="text-xs text-[var(--muted-foreground)]">
                        {String(row.status)} · {String((row.source as Row | undefined)?.kind || "")}
                        {row.canRead === false ? ` · ${t("hidden")}` : ""}
                      </p>
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
                {answerable === true ? <p role="status">{t("answerable")}</p> : null}
                {answerable === false ? <p>{t("noHits")}</p> : null}
                <ul className="grid gap-3">
                  {hits.map((hit) => (
                    <li
                      className="rounded-lg border border-[var(--border)] p-3"
                      key={String(hit.chunkId)}
                    >
                      <p className="font-medium">{String(hit.title)}</p>
                      <p className="mt-1 text-sm">{String(hit.snippet)}</p>
                      <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                        {Number(hit.rerankScore ?? hit.score).toFixed(2)}
                      </p>
                    </li>
                  ))}
                </ul>
              </form>
            </TabsContent>
            <TabsContent value="sources">
              {sources.length === 0 ? <EmptyState title={detail("noSources")} /> : null}
              <ul className="grid gap-2">
                {sources.map((row) => (
                  <li
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--border)] p-3"
                    key={String(row.id)}
                  >
                    <span>
                      {String(row.name)} · {String(row.kind)} · {String(row.status)}
                    </span>
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
              <ul className="grid gap-2">
                {jobs.map((row) => (
                  <li className="detail-panel text-sm" key={String(row.id)}>
                    {String(row.kind)} · {String(row.status)}
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
