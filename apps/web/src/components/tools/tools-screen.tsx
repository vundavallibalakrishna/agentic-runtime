"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus } from "@/components/common/detail-state";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api } from "@/lib/api";

type Row = Record<string, unknown>;

const MODE_KEY = "ar-settings-mode";

export function ToolsScreen() {
  const t = useTranslations("tools");
  const [servers, setServers] = useState<Row[]>([]);
  const [calls, setCalls] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const [slug, setSlug] = useState("echo");
  const [name, setName] = useState("Echo");
  const [address, setAddress] = useState("memory://echo");
  const [kind, setKind] = useState("remote_mcp");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [serverPage, callPage] = await Promise.all([
        api<{ items: Row[] }>("/api/v1/tool-servers"),
        api<{ items: Row[] }>("/api/v1/tool-calls"),
      ]);
      setServers(serverPage.items ?? []);
      setCalls(callPage.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  function chooseMode(next: boolean) {
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }

  async function register() {
    if (busy) return;
    setBusy(true);
    setNotice("");
    setError("");
    try {
      const endpoint = kind === "remote_mcp" ? address : undefined;
      const created = await api<Row>("/api/v1/tool-servers", {
        method: "POST",
        body: JSON.stringify({
          slug,
          name,
          kind,
          version: {
            version: "1.0.0",
            endpointUrl: endpoint,
            authMode: "none",
            config: kind === "sql" ? { dataConnectionId: address } : {},
          },
        }),
      });
      const serverId = String(created.id);
      const versions = created.versions as Row[] | undefined;
      const versionId = String(versions?.[0]?.id ?? "");
      const detail = await api<Row>(`/api/v1/tool-servers/${serverId}/versions/${versionId}`);
      const tools = (detail.tools as Row[] | undefined) ?? [];
      for (const tool of tools) {
        await api(
          `/api/v1/tool-servers/${serverId}/versions/${versionId}/tools/${String(tool.id)}`,
          {
            method: "PATCH",
            body: JSON.stringify({ riskClass: String(tool.riskClass ?? "R0") }),
          },
        );
      }
      await api(`/api/v1/tool-servers/${serverId}/versions/${versionId}:submit`, {
        method: "POST",
      });
      try {
        await api(`/api/v1/tool-servers/${serverId}/versions/${versionId}:approve`, {
          method: "POST",
          body: JSON.stringify({ notes: "Confirmed from the simple wizard." }),
        });
        setNotice(t("approved"));
      } catch (failure) {
        if (!(failure instanceof ApiError) || failure.status !== 403) throw failure;
        setNotice(t("submitted"));
      }
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <ActionStatus busy={busy} />
      <fieldset disabled={busy} className="min-w-0">
        <PageHeader
          title={t("title")}
          body={t("body")}
          actions={<SettingsMode advanced={advanced} onChange={chooseMode} />}
        />
        <div className="mb-6 flex flex-wrap gap-2">
          <Button asChild variant="outline">
            <a href="/connections">{t("connections")}</a>
          </Button>
          <Button asChild variant="ghost">
            <a href="/chat?agent=desk">{t("desk")}</a>
          </Button>
        </div>
        <ManagementLayout
          title={t("listTitle")}
          formTitle={t("register")}
          form={
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                void register();
              }}
            >
              <label className="block text-sm" htmlFor="tool-slug">
                {t("slug")}
                <Input
                  id="tool-slug"
                  onChange={(event) => setSlug(event.target.value)}
                  value={slug}
                />
              </label>
              <label className="block text-sm" htmlFor="tool-name">
                {t("name")}
                <Input
                  id="tool-name"
                  onChange={(event) => setName(event.target.value)}
                  value={name}
                />
              </label>
              <label className="block text-sm" htmlFor="tool-address">
                {t("address")}
                <Input
                  id="tool-address"
                  onChange={(event) => setAddress(event.target.value)}
                  value={address}
                />
              </label>
              {advanced ? (
                <label className="block text-sm" htmlFor="tool-kind">
                  {t("kind")}
                  <select
                    className="mt-1 w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-2"
                    id="tool-kind"
                    onChange={(event) => setKind(event.target.value)}
                    value={kind}
                  >
                    <option value="remote_mcp">{t("remote")}</option>
                    <option value="openapi">{t("openapi")}</option>
                    <option value="sql">{t("sql")}</option>
                  </select>
                </label>
              ) : null}
              <Button type="submit">{t("save")}</Button>
              {notice ? <p role="status">{notice}</p> : null}
            </form>
          }
        >
          {loading ? (
            <div aria-busy="true" className="space-y-2">
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-24 w-full" />
              <p className="sr-only">{t("loading")}</p>
            </div>
          ) : null}
          {error ? (
            <div className="mb-4" role="alert">
              <p>{error}</p>
              <Button onClick={() => void load()} type="button" variant="outline">
                {t("retry")}
              </Button>
            </div>
          ) : null}
          {!loading && !error && servers.length === 0 ? <EmptyState title={t("empty")} /> : null}
          {!loading && servers.length > 0 ? (
            <ul className="mb-8 grid gap-3">
              {servers.map((server) => (
                <li
                  className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3"
                  key={String(server.id)}
                >
                  <h2 className="text-lg font-medium">{String(server.name)}</h2>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    {String(server.slug)} · {String(server.kind)} · {String(server.status)}
                  </p>
                </li>
              ))}
            </ul>
          ) : null}

          <section>
            <h2 className="mb-2 text-lg font-medium">{t("calls")}</h2>
            {calls.length === 0 ? (
              <p className="text-sm text-[var(--muted-foreground)]">{t("noCalls")}</p>
            ) : null}
            <ul className="space-y-2">
              {calls.slice(0, 8).map((call) => (
                <li
                  className="rounded-xl border border-[var(--border)] px-3 py-2 text-sm"
                  key={String(call.id)}
                >
                  <p>{String(call.qualifiedName ?? "")}</p>
                  <p className="text-[var(--muted-foreground)]">{String(call.status ?? "")}</p>
                  <p>{String(call.resultPreview ?? "")}</p>
                </li>
              ))}
            </ul>
          </section>
        </ManagementLayout>
      </fieldset>
    </AppShell>
  );
}
