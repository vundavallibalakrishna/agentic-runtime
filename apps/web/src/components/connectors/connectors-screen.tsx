"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus } from "@/components/common/detail-state";
import { EmptyState } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Row = Record<string, unknown>;

function verificationLabel(
  t: (key: "live" | "public" | "not_live") => string,
  verification: string,
) {
  if (verification === "live") return t("live");
  if (verification === "public") return t("public");
  return t("not_live");
}

export function ConnectorsScreen({ slug }: { slug?: string }) {
  const t = useTranslations("connectors");
  const params = useParams<{ slug?: string }>();
  const selected = slug ?? params.slug;
  const [rows, setRows] = useState<Row[]>([]);
  const [detail, setDetail] = useState<Row | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [secret, setSecret] = useState("");
  const [clientId, setClientId] = useState("");
  const [kind, setKind] = useState("");
  const [config, setConfig] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api<{ items: Row[] }>("/api/v1/connectors");
      setRows(page.items ?? []);
      if (selected) {
        setDetail(await api<Row>(`/api/v1/connectors/${selected}`));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [selected, t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!detail) return;
    setKind(String(detail.authKind ?? ""));
    setName(String(detail.slug ?? ""));
  }, [detail]);

  const categories = useMemo(
    () => [...new Set(rows.map((row) => String(row.category ?? "")))].filter(Boolean),
    [rows],
  );
  const visible = rows.filter((row) => {
    const text = `${row.name} ${row.summary} ${row.category}`.toLowerCase();
    if (query && !text.includes(query.toLowerCase())) return false;
    if (category && row.category !== category) return false;
    return true;
  });

  async function install(event: FormEvent) {
    event.preventDefault();
    if (!selected || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`/api/v1/connectors/${selected}:install`, {
        method: "POST",
        body: JSON.stringify({
          connectionName: name,
          kind,
          secret,
          username,
          clientId,
          config,
        }),
      });
      setSecret("");
      setNotice(t("saved"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function testConnection() {
    const installId = String((detail?.install as Row | undefined)?.id ?? "");
    if (!installId) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<Row>(`/api/v1/connector-installs/${installId}:test`, {
        method: "POST",
      });
      setNotice(result.ok ? t("tested") : String(result.error ?? t("error")));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function toggleTool(toolName: string, enabled: boolean) {
    const installRow = detail?.install as Row | undefined;
    const installId = String(installRow?.id ?? "");
    if (!installId) return;
    const current = Array.isArray(installRow?.disabledTools)
      ? (installRow.disabledTools as string[])
      : [];
    const disabled = enabled ? current.filter((item) => item !== toolName) : [...current, toolName];
    setBusy(true);
    try {
      await api(`/api/v1/connector-installs/${installId}`, {
        method: "PATCH",
        body: JSON.stringify({ disabledTools: disabled }),
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    const installId = String((detail?.install as Row | undefined)?.id ?? "");
    if (!installId) return;
    setBusy(true);
    try {
      await api(`/api/v1/connector-installs/${installId}`, { method: "DELETE" });
      setNotice(t("removed"));
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
      <PageHeader
        title={selected ? String(detail?.name ?? t("title")) : t("title")}
        body={selected ? String(detail?.summary ?? "") : t("body")}
        actions={
          selected ? (
            <Button asChild variant="outline">
              <Link href="/connectors">{t("back")}</Link>
            </Button>
          ) : null
        }
      />
      {error ? (
        <p role="alert">
          {error}{" "}
          <button className="underline" onClick={() => void load()} type="button">
            {t("retry")}
          </button>
        </p>
      ) : null}
      {notice ? <p role="status">{notice}</p> : null}
      {loading ? <Skeleton className="h-40 w-full" /> : null}
      {!loading && !selected ? (
        <>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row">
            <label className="min-w-0 flex-1 text-sm" htmlFor="connector-search">
              {t("search")}
              <Input
                className="mt-1"
                id="connector-search"
                onChange={(event) => setQuery(event.target.value)}
                value={query}
              />
            </label>
            <label className="text-sm" htmlFor="connector-category">
              {t("category")}
              <select
                className="mt-1 block h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
                id="connector-category"
                onChange={(event) => setCategory(event.target.value)}
                value={category}
              >
                <option value="">{t("all")}</option>
                {categories.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {!error && visible.length === 0 ? <EmptyState title={t("empty")} /> : null}
          <p className="mb-4 text-sm text-[var(--muted-foreground)]">{t("builtHint")}</p>
          <ul className="grid gap-3 md:grid-cols-2">
            {visible.map((row) => {
              const rowSlug = String(row.slug);
              const verification = String(row.verification ?? "not_live");
              return (
                <li key={rowSlug}>
                  <Link
                    className="block rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 hover:bg-[var(--muted)]"
                    href={`/connectors/${rowSlug}`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{String(row.name)}</span>
                      <Badge>{t("built")}</Badge>
                      <Badge>{verificationLabel(t, verification)}</Badge>
                      {row.installed ? <Badge>{t("installed")}</Badge> : null}
                    </div>
                    <p className="mt-2 text-sm text-[var(--muted-foreground)]">
                      {String(row.summary)}
                    </p>
                    <p className="mt-2 text-sm">{String(row.verificationNote ?? "")}</p>
                    <p className="mt-3 text-sm underline">{t("open")}</p>
                  </Link>
                </li>
              );
            })}
          </ul>
        </>
      ) : null}
      {!loading && selected && detail ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <section>
            <div className="flex flex-wrap gap-2">
              <Badge>{t("built")}</Badge>
              <Badge>{verificationLabel(t, String(detail.verification ?? ""))}</Badge>
              <Badge>{detail.installed ? t("installed") : t("notInstalled")}</Badge>
            </div>
            <p className="mt-3 text-sm text-[var(--muted-foreground)]">{t("builtHint")}</p>
            <p className="mt-3 text-sm">{String(detail.verificationNote ?? "")}</p>
            <p className="mt-2 text-sm text-[var(--muted-foreground)]">
              {t("rate", { count: Number(detail.ratePerMinute ?? 0) })}
            </p>
            <h2 className="mt-6 text-lg font-medium">{t("guide")}</h2>
            <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm">
              {(Array.isArray(detail.steps) ? (detail.steps as string[]) : []).map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <p className="mt-4">
              <a
                className="underline"
                href={String(detail.registrationUrl ?? "")}
                rel="noreferrer"
                target="_blank"
              >
                {t("register")}
              </a>
            </p>
            <p className="mt-2 text-sm">
              {t("docs")}: <code>{String(detail.docs ?? "")}</code>
            </p>
            <h2 className="mt-6 text-lg font-medium">{t("scopes")}</h2>
            {Array.isArray(detail.scopes) && detail.scopes.length > 0 ? (
              <ul className="mt-2 list-disc pl-5 text-sm">
                {(detail.scopes as string[]).map((scope) => (
                  <li key={scope}>
                    <code>{scope}</code>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-[var(--muted-foreground)]">{t("noScopes")}</p>
            )}
            <h2 className="mt-6 text-lg font-medium">{t("tools")}</h2>
            <ul className="mt-2 grid gap-2">
              {(Array.isArray(detail.tools) ? (detail.tools as Row[]) : []).map((tool) => {
                const toolName = String(tool.name);
                const enabled = Boolean(tool.enabled);
                return (
                  <li
                    className="flex items-start justify-between gap-3 rounded-lg border border-[var(--border)] p-3"
                    key={toolName}
                  >
                    <div>
                      <p className="text-sm font-medium">
                        {String(tool.title)}{" "}
                        <span className="text-[var(--muted-foreground)]">
                          {tool.risk === "W2" ? t("asks") : t("read")}
                        </span>
                      </p>
                      <p className="text-sm text-[var(--muted-foreground)]">
                        {String(tool.description)}
                      </p>
                    </div>
                    {detail.installed ? (
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          checked={enabled}
                          onChange={(event) => void toggleTool(toolName, event.target.checked)}
                          type="checkbox"
                        />
                        {t("enable")}
                      </label>
                    ) : null}
                  </li>
                );
              })}
            </ul>
            <p className="mt-4 text-sm">
              <Link className="underline" href="/agents">
                {t("attach")}
              </Link>
            </p>
          </section>
          <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            {detail.installed ? (
              <div className="grid gap-3">
                <p className="text-sm">
                  {t("connectionName")}:{" "}
                  {String((detail.install as Row | undefined)?.connectionName ?? "")}
                </p>
                {(detail.install as Row | undefined)?.lastError ? (
                  <p role="alert">{String((detail.install as Row).lastError)}</p>
                ) : null}
                <Button onClick={() => void testConnection()} type="button">
                  {t("test")}
                </Button>
                {detail.authorizeUrl ? (
                  <a className="text-sm underline" href={String(detail.authorizeUrl)}>
                    {t("reconnect")}
                  </a>
                ) : null}
                <Button onClick={() => void remove()} type="button" variant="outline">
                  {t("remove")}
                </Button>
              </div>
            ) : (
              <form className="grid gap-3" onSubmit={(event) => void install(event)}>
                <label className="text-sm" htmlFor="connector-name">
                  {t("connectionName")}
                  <Input
                    className="mt-1"
                    id="connector-name"
                    onChange={(event) => setName(event.target.value)}
                    value={name}
                  />
                </label>
                <label className="text-sm" htmlFor="connector-kind">
                  {t("kind")}
                  <select
                    className="mt-1 block h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
                    id="connector-kind"
                    onChange={(event) => setKind(event.target.value)}
                    value={kind}
                  >
                    {(Array.isArray(detail.authKinds) ? (detail.authKinds as string[]) : []).map(
                      (item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ),
                    )}
                  </select>
                </label>
                {kind === "basic" ? (
                  <label className="text-sm" htmlFor="connector-username">
                    {t("username")}
                    <Input
                      className="mt-1"
                      id="connector-username"
                      onChange={(event) => setUsername(event.target.value)}
                      value={username}
                    />
                  </label>
                ) : null}
                {kind.startsWith("oauth") ? (
                  <label className="text-sm" htmlFor="connector-client">
                    {t("clientId")}
                    <Input
                      className="mt-1"
                      id="connector-client"
                      onChange={(event) => setClientId(event.target.value)}
                      value={clientId}
                    />
                  </label>
                ) : null}
                <label className="text-sm" htmlFor="connector-secret">
                  {t("secret")}
                  <Input
                    className="mt-1"
                    id="connector-secret"
                    onChange={(event) => setSecret(event.target.value)}
                    type="password"
                    value={secret}
                  />
                </label>
                {(Array.isArray(detail.fields) ? (detail.fields as Row[]) : []).map((field) => {
                  const fieldName = String(field.name);
                  return (
                    <label className="text-sm" htmlFor={`field-${fieldName}`} key={fieldName}>
                      {String(field.label)}
                      <Input
                        className="mt-1"
                        id={`field-${fieldName}`}
                        onChange={(event) =>
                          setConfig((current) => ({ ...current, [fieldName]: event.target.value }))
                        }
                        placeholder={String(field.placeholder ?? "")}
                        value={config[fieldName] ?? ""}
                      />
                    </label>
                  );
                })}
                <Button type="submit">{t("connect")}</Button>
              </form>
            )}
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
