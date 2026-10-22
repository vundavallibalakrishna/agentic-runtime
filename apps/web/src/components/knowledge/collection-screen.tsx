"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Row = Record<string, unknown>;

const TABS = ["documents", "search", "sources", "jobs"] as const;

export function CollectionScreen({ collectionId }: { collectionId: string }) {
  const t = useTranslations("knowledge");
  const [collection, setCollection] = useState<Row | null>(null);
  const [documents, setDocuments] = useState<Row[]>([]);
  const [sources, setSources] = useState<Row[]>([]);
  const [jobs, setJobs] = useState<Row[]>([]);
  const [tab, setTab] = useState<(typeof TABS)[number]>("documents");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("When does the visitor desk open?");
  const [hits, setHits] = useState<Row[]>([]);
  const [answerable, setAnswerable] = useState<boolean | null>(null);
  const [file, setFile] = useState<File | null>(null);

  const load = useCallback(async () => {
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
    }
  }

  async function upload() {
    if (!file) {
      return;
    }
    setError("");
    const body = new FormData();
    body.set("upload", file);
    body.set("mime_type", file.type || "text/markdown");
    const uploaded = await api<{ id: string; status: string }>("/api/v1/files:upload", {
      method: "POST",
      body,
    });
    if (uploaded.status !== "ready") {
      setError(t("error"));
      return;
    }
    await api(`/api/v1/knowledge/collections/${collectionId}/documents`, {
      method: "POST",
      body: JSON.stringify({ fileIds: [uploaded.id] }),
    });
    setFile(null);
    await load();
  }

  async function sync(sourceId: string) {
    await api(`/api/v1/knowledge/sources/${sourceId}:sync`, {
      method: "POST",
      body: JSON.stringify({ mode: "incremental" }),
    });
    await load();
  }

  return (
    <AppShell>
      <p className="mb-2 text-sm">
        <Link className="underline" href="/knowledge">
          {t("back")}
        </Link>
      </p>
      <PageHeader
        title={String(collection?.name || t("title"))}
        body={String(collection?.description || t("body"))}
      />
      {error ? (
        <p role="alert">
          {error}{" "}
          <button className="underline" onClick={() => void load()} type="button">
            {t("retry")}
          </button>
        </p>
      ) : null}
      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((item) => (
          <Button
            key={item}
            onClick={() => setTab(item)}
            type="button"
            variant={tab === item ? "default" : "outline"}
          >
            {t(item)}
          </Button>
        ))}
        <Button asChild type="button" variant="outline">
          <Link href={`/knowledge/${collectionId}/sources/new`}>{t("connect")}</Link>
        </Button>
      </div>
      {loading ? <Skeleton className="h-32 w-full" /> : null}
      {tab === "documents" ? (
        <section>
          <form
            className="mb-4 flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              void upload();
            }}
          >
            <label htmlFor="knowledge-file">
              {t("upload")}
              <Input
                id="knowledge-file"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                type="file"
              />
            </label>
            <Button type="submit">{t("upload")}</Button>
          </form>
          {documents.length === 0 ? <p>{t("emptyDocuments")}</p> : null}
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
      ) : null}
      {tab === "search" ? (
        <form
          className="grid max-w-xl gap-3"
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
          <Button type="submit">{t("ask")}</Button>
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
      ) : null}
      {tab === "sources" ? (
        <ul className="grid gap-2">
          {sources.map((row) => (
            <li
              className="flex items-center justify-between gap-3 rounded-lg border border-[var(--border)] p-3"
              key={String(row.id)}
            >
              <span>
                {String(row.name)} · {String(row.kind)} · {String(row.status)}
              </span>
              {row.kind !== "upload" ? (
                <Button onClick={() => void sync(String(row.id))} type="button" variant="outline">
                  {t("sync")}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {tab === "jobs" ? (
        <ul className="grid gap-2">
          {jobs.map((row) => (
            <li key={String(row.id)}>
              {String(row.kind)} · {String(row.status)}
            </li>
          ))}
        </ul>
      ) : null}
    </AppShell>
  );
}
