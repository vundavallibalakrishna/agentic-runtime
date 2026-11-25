"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { CodeSample } from "@/components/common/code-sample";
import { ActionStatus, DetailState } from "@/components/common/detail-state";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { PermissionGate } from "@/components/permission-gate";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { loadSession } from "@/lib/session";

type Account = { id: string; name: string; description: string; status: string };
type Key = {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  expiresAt: string | null;
  lastUsedAt: string | null;
  revokedAt: string | null;
  key?: string;
};
type Capability = { key: string; role: string; permissions: string[] };
type Role = { id: string; key: string; name: string; permissions: string[] };
type Page<T> = { items?: T[] };

const MODE_KEY = "ar-settings-mode";
const CAPABILITY_LABELS = {
  chat: "capabilityChat",
  knowledge_search: "capabilityKnowledgeSearch",
  knowledge_manage: "capabilityKnowledgeManage",
  agents_manage: "capabilityAgentsManage",
} as const;

function day(value: string | null): string {
  return value ? new Date(value).toLocaleDateString() : "";
}

export function KeysScreen() {
  const t = useTranslations("developers");
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [canAssign, setCanAssign] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [keys, setKeys] = useState<Record<string, Key[]>>({});
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [name, setName] = useState("");
  const [chosen, setChosen] = useState<string[]>([]);
  const [roleKeys, setRoleKeys] = useState<string[]>([]);
  const [days, setDays] = useState("90");
  const [secret, setSecret] = useState("");
  const [confirming, setConfirming] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const session = await loadSession();
      const permissions = session.permissions ?? [];
      const may = permissions.includes("service_accounts:manage");
      setAllowed(may);
      setCanAssign(permissions.includes("roles:manage") && permissions.includes("users:read"));
      if (!may) return;
      const [accountPage, capabilityPage, rolePage] = await Promise.all([
        api<Page<Account>>("/api/v1/service-accounts"),
        api<Page<Capability>>("/api/v1/service-accounts:capabilities"),
        permissions.includes("users:read")
          ? api<Page<Role>>("/api/v1/roles")
          : Promise.resolve({ items: [] }),
      ]);
      const found = accountPage.items ?? [];
      setAccounts(found);
      setCapabilities(capabilityPage.items ?? []);
      setRoles(rolePage.items ?? []);
      const lists = await Promise.all(
        found.map((account) => api<Page<Key>>(`/api/v1/api-keys?serviceAccountId=${account.id}`)),
      );
      setKeys(Object.fromEntries(found.map((account, at) => [account.id, lists[at]?.items ?? []])));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
    void load();
  }, [load]);

  function chooseMode(next: boolean) {
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }

  function toggle(list: string[], value: string): string[] {
    return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
  }

  // The roles the account is given and what its key is narrowed to. In Simple these come
  // from what the person said the account is for; in Advanced from the roles they picked,
  // with the key left as wide as those roles.
  const picked = capabilities.filter((item) => chosen.includes(item.key));
  const wantedRoles = advanced ? roleKeys : [...new Set(picked.map((item) => item.role))];
  const scopes = advanced ? [] : [...new Set(picked.flatMap((item) => item.permissions))];
  const ready = name.trim() !== "" && wantedRoles.length > 0 && canAssign && !busy;

  async function run(action: () => Promise<void>, done: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(done);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("actionFailed"));
    } finally {
      setBusy(false);
      setConfirming("");
    }
  }

  async function create() {
    setSecret("");
    await run(async () => {
      const account = await api<Account>("/api/v1/service-accounts", {
        method: "POST",
        body: JSON.stringify({ name: name.trim() }),
      });
      for (const key of wantedRoles) {
        const role = roles.find((item) => item.key === key);
        if (!role) throw new Error(t("roleMissing", { role: key }));
        await api("/api/v1/role-assignments", {
          method: "POST",
          body: JSON.stringify({
            roleId: role.id,
            principalType: "service_account",
            principalId: account.id,
          }),
        });
      }
      const made = await api<Key>("/api/v1/api-keys", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          serviceAccountId: account.id,
          scopes,
          expiresInDays: Math.min(365, Math.max(1, Number(days) || 90)),
        }),
      });
      setSecret(made.key ?? "");
      setName("");
      setChosen([]);
      setRoleKeys([]);
    }, t("created"));
  }

  async function rotate(key: Key) {
    setSecret("");
    await run(async () => {
      const made = await api<Key>(`/api/v1/api-keys/${key.id}:rotate`, { method: "POST" });
      setSecret(made.key ?? "");
    }, t("rotated"));
  }

  const origin = typeof window === "undefined" ? "" : window.location.origin;
  // The sample reads the key from the caller's own environment: the secret is on this
  // page once, in one place.
  const check = `export CURA_KEY='<the key above>'\ncurl -s ${origin}/api/v1/permissions \\\n  -H "Authorization: Bearer $CURA_KEY" | head -c 200`;

  const form = (
    <form
      className="space-y-4 text-sm"
      onSubmit={(event) => {
        event.preventDefault();
        void create();
      }}
    >
      <label className="block" htmlFor="account-name">
        {t("name")}
        <Input
          className="mt-1"
          id="account-name"
          onChange={(event) => setName(event.target.value)}
          value={name}
        />
      </label>
      {advanced ? (
        <fieldset>
          <legend className="font-medium">{t("roles")}</legend>
          <p className="mb-2 text-xs text-[var(--muted-foreground)]">{t("rolesHelp")}</p>
          {roles.map((role) => (
            <label className="flex items-center gap-2 py-1" key={role.id}>
              <input
                checked={roleKeys.includes(role.key)}
                onChange={() => setRoleKeys((current) => toggle(current, role.key))}
                type="checkbox"
              />
              {role.name}
            </label>
          ))}
          <label className="mt-3 block" htmlFor="key-days">
            {t("expiresIn")}
            <Input
              className="mt-1 w-28"
              id="key-days"
              max={365}
              min={1}
              onChange={(event) => setDays(event.target.value)}
              type="number"
              value={days}
            />
          </label>
        </fieldset>
      ) : (
        <fieldset>
          <legend className="font-medium">{t("purpose")}</legend>
          {capabilities.map((item) => (
            <label className="flex items-start gap-2 py-1" key={item.key}>
              <input
                checked={chosen.includes(item.key)}
                className="mt-1"
                onChange={() => setChosen((current) => toggle(current, item.key))}
                type="checkbox"
              />
              <span>
                {item.key in CAPABILITY_LABELS
                  ? t(CAPABILITY_LABELS[item.key as keyof typeof CAPABILITY_LABELS])
                  : item.key}
              </span>
            </label>
          ))}
        </fieldset>
      )}
      {scopes.length > 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]" data-testid="grants">
          {t("grants", { permissions: scopes.join(", ") })}
        </p>
      ) : null}
      {canAssign ? null : <p role="alert">{t("cannotAssign")}</p>}
      <Button disabled={!ready} type="submit">
        {t("create")}
      </Button>
    </form>
  );

  return (
    <AppShell>
      <PageHeader
        actions={<SettingsMode advanced={advanced} onChange={chooseMode} />}
        body={t("keysBody")}
        title={t("keysTitle")}
      />
      {allowed === false ? (
        <PermissionGate allowed={false}>{null}</PermissionGate>
      ) : (
        <>
          <DetailState error={error} loading={loading} onRetry={() => void load()} />
          <ActionStatus busy={busy} notice={notice} />
          {secret ? (
            <section className="detail-panel mb-6 space-y-4" data-testid="new-secret">
              <p className="text-sm">{t("secretOnce")}</p>
              <CodeSample title={t("secretTitle")} value={secret} />
              <CodeSample title={t("checkTitle")} value={check} />
              <p className="text-sm">
                <Link className="underline" href="/developers">
                  {t("nextNotes")}
                </Link>
              </p>
            </section>
          ) : null}
          {loading ? null : (
            <ManagementLayout form={form} formTitle={t("newAccount")} title={t("accounts")}>
              {accounts.length === 0 ? (
                <EmptyState title={t("empty")} />
              ) : (
                <ul className="row-list">
                  {accounts.map((account) => (
                    <li className="p-4" key={account.id}>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="font-medium">
                          {account.name}{" "}
                          <Badge tone={statusTone(account.status)}>{account.status}</Badge>
                        </p>
                        <Button
                          disabled={busy}
                          onClick={() =>
                            confirming === account.id
                              ? void run(
                                  () =>
                                    api(`/api/v1/service-accounts/${account.id}`, {
                                      method: "DELETE",
                                    }),
                                  t("deleted"),
                                )
                              : setConfirming(account.id)
                          }
                          type="button"
                          variant="outline"
                        >
                          {confirming === account.id
                            ? t("confirmDelete", { name: account.name })
                            : t("deleteAccount", { name: account.name })}
                        </Button>
                      </div>
                      <ul className="mt-3 space-y-2 text-sm">
                        {(keys[account.id] ?? []).map((key) => (
                          <li
                            className="flex flex-wrap items-center justify-between gap-3"
                            key={key.id}
                          >
                            <span className="min-w-0 break-words">
                              <code>{key.prefix}</code>
                              <span className="text-[var(--muted-foreground)]">
                                {" · "}
                                {key.revokedAt
                                  ? t("revokedOn", { date: day(key.revokedAt) })
                                  : key.lastUsedAt
                                    ? t("lastUsed", { date: day(key.lastUsedAt) })
                                    : t("neverUsed")}
                                {key.expiresAt && !key.revokedAt
                                  ? ` · ${t("expires", { date: day(key.expiresAt) })}`
                                  : ""}
                              </span>
                            </span>
                            {key.revokedAt ? null : (
                              <span className="flex gap-2">
                                <Button
                                  disabled={busy}
                                  onClick={() => void rotate(key)}
                                  type="button"
                                  variant="outline"
                                >
                                  {t("rotate", { key: key.prefix })}
                                </Button>
                                <Button
                                  disabled={busy}
                                  onClick={() =>
                                    confirming === key.id
                                      ? void run(
                                          () =>
                                            api(`/api/v1/api-keys/${key.id}`, { method: "DELETE" }),
                                          t("revoked"),
                                        )
                                      : setConfirming(key.id)
                                  }
                                  type="button"
                                  variant="outline"
                                >
                                  {confirming === key.id
                                    ? t("confirmRevoke", { key: key.prefix })
                                    : t("revoke", { key: key.prefix })}
                                </Button>
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ul>
              )}
            </ManagementLayout>
          )}
        </>
      )}
    </AppShell>
  );
}
