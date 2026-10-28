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
  const [tools, setTools] = useState<Row[]>([]);
  const [calls, setCalls] = useState<Row[]>([]);
  const [egress, setEgress] = useState("");
  const [searchProvider, setSearchProvider] = useState("none");
  const [searchSecret, setSearchSecret] = useState("");
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
    if (typeof window === "undefined") {
      return;
    }
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const rows = (page: { items?: Row[]; data?: Row[] }) => page.items ?? page.data ?? [];
      const [serverPage, callPage] = await Promise.all([
        api<{ items?: Row[]; data?: Row[] }>("/api/v1/tool-servers"),
        api<{ items?: Row[]; data?: Row[] }>("/api/v1/tool-calls"),
      ]);
      const toolPage = await api<{ items?: Row[]; data?: Row[] }>("/api/v1/tools").catch(() => ({
        items: [],
      }));
      const tenant = await api<{
        settings?: {
          egressAllowlist?: string[];
          search?: { provider?: string; secretName?: string };
        };
      }>("/api/v1/tenant").catch(() => ({ settings: undefined }));
      setServers(rows(serverPage));
      setTools(rows(toolPage));
      setCalls(rows(callPage));
      setEgress((tenant.settings?.egressAllowlist ?? []).join("\n"));
      setSearchProvider(tenant.settings?.search?.provider ?? "none");
      setSearchSecret(tenant.settings?.search?.secretName ?? "");
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
    if (typeof window !== "undefined") {
      window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
    }
  }

  async function saveAccess() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("/api/v1/tenant", {
        method: "PATCH",
        body: JSON.stringify({
          settings: {
            egressAllowlist: egress
              .split("\n")
              .map((item) => item.trim())
              .filter(Boolean),
            search: { provider: searchProvider, secretName: searchSecret.trim() },
          },
        }),
      });
      setNotice(t("accessSaved"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
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
          <section className="mb-8 rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
            <h2 className="text-lg font-medium">{t("generalTitle")}</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">{t("generalBody")}</p>
            <ul className="mt-3 space-y-2">
              {tools
                .filter((tool) => String(tool.qualifiedName ?? "").startsWith("general."))
                .map((tool) => (
                  <li key={String(tool.id ?? tool.qualifiedName)}>
                    <p className="font-medium">{String(tool.qualifiedName ?? "")}</p>
                    <p className="text-sm text-[var(--muted-foreground)]">
                      {String(tool.riskClass ?? "")} · {String(tool.description ?? "")}
                    </p>
                  </li>
                ))}
            </ul>
            <form
              className="mt-4 grid gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                void saveAccess();
              }}
            >
              <label className="block text-sm" htmlFor="egress-hosts">
                {t("egress")}
                <textarea
                  className="mt-1 min-h-16 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-sm"
                  id="egress-hosts"
                  onChange={(event) => setEgress(event.target.value)}
                  value={egress}
                />
              </label>
              <label className="block text-sm" htmlFor="search-provider">
                {t("searchProvider")}
                <select
                  className="mt-1 w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-2"
                  id="search-provider"
                  onChange={(event) => setSearchProvider(event.target.value)}
                  value={searchProvider}
                >
                  <option value="none">{t("searchNone")}</option>
                  <option value="brave">Brave</option>
                  <option value="tavily">Tavily</option>
                </select>
              </label>
              <label className="block text-sm" htmlFor="search-secret">
                {t("searchSecret")}
                <Input
                  id="search-secret"
                  onChange={(event) => setSearchSecret(event.target.value)}
                  value={searchSecret}
                />
              </label>
              <p className="text-sm text-[var(--muted-foreground)]">{t("searchHelp")}</p>
              <Button type="submit">{t("saveAccess")}</Button>
            </form>
          </section>

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
