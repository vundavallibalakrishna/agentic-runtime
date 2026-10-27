"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, BackButton } from "@/components/common/detail-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

const KINDS = ["web", "s3", "sharepoint", "confluence", "google_drive", "database", "mcp_resource"];

export function SourceWizard({ collectionId }: { collectionId: string }) {
  const t = useTranslations("knowledge");
  const detail = useTranslations("detail");
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState("{}");
  const [secretId, setSecretId] = useState("");
  const [dataConnectionId, setDataConnectionId] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState("web");
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  async function save() {
    if (busy || !name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const configuration =
        kind === "web" ? { url, allowlist: [new URL(url).host] } : JSON.parse(config);
      if (!configuration || typeof configuration !== "object" || Array.isArray(configuration))
        throw new Error(detail("invalidConfig"));
      await api(`/api/v1/knowledge/collections/${collectionId}/sources`, {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          kind,
          config: configuration,
          ...(secretId.trim() ? { secretId: secretId.trim() } : {}),
          ...(dataConnectionId.trim() ? { dataConnectionId: dataConnectionId.trim() } : {}),
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
        actions={<BackButton href={`/knowledge/${collectionId}`}>{t("back")}</BackButton>}
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
          {kind === "web" ? (
            <label htmlFor="source-url">
              {t("url")}
              <Input
                id="source-url"
                required
                type="url"
                placeholder="https://example.com"
                onChange={(event) => setUrl(event.target.value)}
                value={url}
              />
            </label>
          ) : (
            <>
              <label htmlFor="source-config">
                {detail("configuration")}
                <textarea
                  id="source-config"
                  className="min-h-48 rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 font-mono text-sm"
                  value={config}
                  onChange={(event) => setConfig(event.target.value)}
                />
              </label>
              <p className="text-sm text-[var(--muted-foreground)]">
                {detail("configurationHelp")}
              </p>
              <label htmlFor="source-secret">
                {detail("secretId")}
                <Input
                  id="source-secret"
                  value={secretId}
                  onChange={(event) => setSecretId(event.target.value)}
                />
              </label>
              {kind === "database" ? (
                <label htmlFor="source-connection">
                  {detail("dataConnectionId")}
                  <Input
                    id="source-connection"
                    value={dataConnectionId}
                    onChange={(event) => setDataConnectionId(event.target.value)}
                  />
                </label>
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
