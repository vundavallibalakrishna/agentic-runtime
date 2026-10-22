"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

const KINDS = ["web", "s3", "sharepoint", "confluence", "google_drive", "database", "mcp_resource"];

export function SourceWizard({ collectionId }: { collectionId: string }) {
  const t = useTranslations("knowledge");
  const [name, setName] = useState("Company site");
  const [kind, setKind] = useState("web");
  const [url, setUrl] = useState("https://example.com");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function save() {
    setError("");
    try {
      await api(`/api/v1/knowledge/collections/${collectionId}/sources`, {
        method: "POST",
        body: JSON.stringify({ name, kind, config: { url, allowlist: ["example.com"] } }),
      });
      setNotice(t("saved"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    }
  }

  return (
    <AppShell>
      <p className="mb-2 text-sm">
        <Link className="underline" href={`/knowledge/${collectionId}`}>
          {t("back")}
        </Link>
      </p>
      <PageHeader title={t("connect")} body={t("body")} />
      {error ? <p role="alert">{error}</p> : null}
      {notice ? <p role="status">{notice}</p> : null}
      <form
        className="grid max-w-xl gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label htmlFor="source-name">
          {t("name")}
          <Input id="source-name" onChange={(event) => setName(event.target.value)} value={name} />
        </label>
        <label htmlFor="source-kind">
          {t("sourceKind")}
          <select
            className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2"
            id="source-kind"
            onChange={(event) => setKind(event.target.value)}
            value={kind}
          >
            {KINDS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="source-url">
          {t("url")}
          <Input id="source-url" onChange={(event) => setUrl(event.target.value)} value={url} />
        </label>
        <Button type="submit">{t("connect")}</Button>
      </form>
    </AppShell>
  );
}
