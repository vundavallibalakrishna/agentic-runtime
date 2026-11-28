"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, BackButton } from "@/components/common/detail-state";
import { ReferencePicker } from "@/components/common/reference-picker";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

const KINDS = ["web", "s3", "sharepoint", "confluence", "google_drive", "database", "mcp_resource"];

// What each kind needs, as a starting point a person fills in. No value is a default the
// product relies on: an empty one is refused with a message that says what is missing.
const STARTERS: Record<string, Record<string, string>> = {
  s3: { bucket: "", prefix: "", endpoint: "", region: "", connection: "" },
  database: { query: "", idColumn: "id", titleColumn: "title", textColumn: "text" },
  mcp_resource: { server: "" },
  sharepoint: { url: "", connection: "" },
  confluence: { url: "", connection: "" },
  google_drive: { url: "", connection: "" },
};

const HELP: Record<string, string> = {
  s3: "configurationHelpS3",
  database: "configurationHelpDatabase",
  mcp_resource: "configurationHelpMcp",
  sharepoint: "configurationHelpUrl",
  confluence: "configurationHelpUrl",
  google_drive: "configurationHelpUrl",
};

function starter(kind: string): string {
  return JSON.stringify(STARTERS[kind] ?? {}, null, 2);
}

export function SourceWizard({ collectionId }: { collectionId: string }) {
  const t = useTranslations("knowledge");
  const detail = useTranslations("detail");
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState("{}");
  const [dataConnectionId, setDataConnectionId] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState("web");
  const [url, setUrl] = useState("");
  const [maxPages, setMaxPages] = useState("200");
  const [maxDepth, setMaxDepth] = useState("0");
  const [error, setError] = useState("");

  async function save() {
    if (busy || !name.trim()) return;
    setBusy(true);
    setError("");
    try {
      let configuration: unknown;
      if (kind === "web") {
        let address: URL;
        try {
          address = new URL(url.trim());
        } catch {
          throw new Error(detail("invalidWebUrl"));
        }
        if (!["https:", "http:"].includes(address.protocol) || address.username || address.password)
          throw new Error(detail("invalidWebUrl"));
        configuration = {
          start_urls: [url.trim()],
          allowed_domains: [address.hostname],
          max_pages: Math.max(1, Number(maxPages) || 1),
          max_depth: Math.max(0, Number(maxDepth) || 0),
        };
      } else {
        configuration = JSON.parse(config);
      }
      if (!configuration || typeof configuration !== "object" || Array.isArray(configuration))
        throw new Error(detail("invalidConfig"));
      await api(`/api/v1/knowledge/collections/${collectionId}/sources`, {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          kind,
          config: configuration,
          ...(kind === "database" && dataConnectionId.trim()
            ? { dataConnectionId: dataConnectionId.trim() }
            : {}),
        }),
      });
      router.push(`/knowledge/${collectionId}`);
    } catch (caught) {
      setError(
        caught instanceof SyntaxError
          ? detail("invalidConfig")
          : caught instanceof Error
            ? caught.message
            : t("error"),
      );
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title={t("connect")}
        body={detail("sourceBody")}
        actions={
          <BackButton href={`/knowledge/${collectionId}`}>{detail("backToCollection")}</BackButton>
        }
      />
      {error ? (
        <p role="alert" className="mb-4 text-sm text-[var(--destructive)]">
          {error}
        </p>
      ) : null}
      <ActionStatus busy={busy} />
      <form
        className="detail-panel management-form mx-auto max-w-2xl"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <fieldset disabled={busy} className="grid gap-5">
          <label htmlFor="source-name">
            {t("name")}
            <Input
              required
              id="source-name"
              onChange={(event) => setName(event.target.value)}
              value={name}
            />
          </label>
          <label htmlFor="source-kind">
            {t("sourceKind")}
            <select
              className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2"
              id="source-kind"
              onChange={(event) => {
                setKind(event.target.value);
                setConfig(starter(event.target.value));
              }}
              value={kind}
            >
              {KINDS.map((item) => (
                <option key={item} value={item}>
                  {t(`sourceKinds.${item}`)}
                </option>
              ))}
            </select>
          </label>
          {kind === "web" ? (
            <>
              <label htmlFor="source-url">
                {t("url")}
                <Input
                  id="source-url"
                  required
                  type="url"
                  aria-describedby="source-url-help"
                  onChange={(event) => setUrl(event.target.value)}
                  value={url}
                />
              </label>
              <p id="source-url-help" className="-mt-2 text-xs text-[var(--muted-foreground)]">
                {t("urlHelp")}
              </p>
              <div className="flex flex-wrap gap-4">
                <label htmlFor="source-max-pages">
                  {t("maxPages")}
                  <Input
                    className="mt-1 w-28"
                    id="source-max-pages"
                    max={10000}
                    min={1}
                    onChange={(event) => setMaxPages(event.target.value)}
                    type="number"
                    value={maxPages}
                  />
                </label>
                <label htmlFor="source-max-depth">
                  {t("linkDepth")}
                  <Input
                    className="mt-1 w-28"
                    id="source-max-depth"
                    max={5}
                    min={0}
                    onChange={(event) => setMaxDepth(event.target.value)}
                    type="number"
                    value={maxDepth}
                  />
                </label>
              </div>
              <p className="-mt-2 text-xs text-[var(--muted-foreground)]">{t("crawlHelp")}</p>
            </>
          ) : (
            <>
              <label htmlFor="source-config">
                {detail("configuration")}
                <textarea
                  id="source-config"
                  className="mt-1 block min-h-48 w-full min-w-0 rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 font-mono text-sm"
                  aria-describedby="source-config-help"
                  value={config}
                  onChange={(event) => setConfig(event.target.value)}
                />
              </label>
              <p id="source-config-help" className="text-sm text-[var(--muted-foreground)]">
                {detail(HELP[kind] ?? "configurationHelp")} {detail("configurationHelp")}
              </p>
              {kind === "database" ? (
                <ReferencePicker
                  label={detail("dataConnection")}
                  endpoint="/api/v1/data-connections"
                  value={dataConnectionId}
                  onChange={setDataConnectionId}
                  disabled={busy}
                />
              ) : null}
            </>
          )}
          <Button disabled={busy || !name.trim() || (kind === "web" && !url.trim())} type="submit">
            {t("connect")}
          </Button>
        </fieldset>
      </form>
    </AppShell>
  );
}
