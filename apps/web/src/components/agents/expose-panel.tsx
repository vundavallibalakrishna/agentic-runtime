"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";

type KeyRow = {
  id: string;
  label: string;
  prefix: string;
  scope: string;
  rateLimitRpm: number;
  monthlyQuota: number;
  monthCount: number;
  lastUsedAt: string | null;
  revokedAt: string | null;
  key?: string;
};

type Exposure = {
  slug: string;
  published: boolean;
  endpoints: Record<string, string>;
  keys: KeyRow[];
};

export function ExposePanel({
  agentId,
  slug,
  canEdit,
}: {
  agentId: string;
  slug: string;
  canEdit: boolean;
}) {
  const t = useTranslations("agents");
  const [exposure, setExposure] = useState<Exposure | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [label, setLabel] = useState("");
  const [rate, setRate] = useState("60");
  const [quota, setQuota] = useState("10000");
  const [secret, setSecret] = useState("");
  const [copied, setCopied] = useState("");
  const [message, setMessage] = useState("");
  const [raw, setRaw] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setExposure(await api<Exposure>(`/api/v1/agents/${agentId}/exposure`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [agentId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const origin = typeof window === "undefined" ? "" : window.location.origin;
  const keyText = secret || "YOUR_AGENT_KEY";
  const examples = useMemo(() => {
    const base = `${origin}/v1/agents/${slug}`;
    const curl = [
      `curl -s ${base}/conversations \\`,
      `  -H "Authorization: Bearer ${keyText}" \\`,
      `  -H "Content-Type: application/json"`,
      "",
      `curl -s ${base}/conversations/$CONVERSATION_ID/messages \\`,
      `  -H "Authorization: Bearer ${keyText}" \\`,
      `  -H "Content-Type: application/json" \\`,
      `  -H "Idempotency-Key: $(uuidgen)" \\`,
      `  -d '{"text":"What is 2 + 2?"}'`,
    ].join("\n");
    const javascript = [
      `const base = ${JSON.stringify(base)};`,
      `const headers = {`,
      `  Authorization: "Bearer ${keyText}",`,
      `  "Content-Type": "application/json",`,
      `};`,
      `const created = await fetch(base + "/conversations", { method: "POST", headers });`,
      `const conversation = await created.json();`,
      `const reply = await fetch(base + "/conversations/" + conversation.id + "/messages", {`,
      `  method: "POST",`,
      `  headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },`,
      `  body: JSON.stringify({ text: "What is 2 + 2?" }),`,
      `});`,
      `console.log(await reply.json());`,
    ].join("\n");
    const mcp = JSON.stringify(
      {
        mcpServers: {
          [slug]: {
            url: `${origin}/v1/mcp`,
            headers: { Authorization: `Bearer ${keyText}` },
          },
        },
      },
      null,
      2,
    );
    return { curl, javascript, mcp };
  }, [keyText, origin, slug]);

  async function copy(name: string, value: string) {
    await navigator.clipboard.writeText(value);
    setCopied(name);
  }

  async function createKey() {
    setBusy(true);
    setError("");
    try {
      const created = await api<KeyRow>(`/api/v1/agents/${agentId}/api-keys`, {
        method: "POST",
        body: JSON.stringify({
          label,
          scope: "agent",
          rateLimitRpm: Number(rate) || 60,
          monthlyQuota: Number(quota) || 0,
        }),
      });
      setSecret(created.key ?? "");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function rotate(id: string) {
    setBusy(true);
    setError("");
    try {
      const created = await api<KeyRow>(`/api/v1/agents/${agentId}/api-keys/${id}:rotate`, {
        method: "POST",
      });
      setSecret(created.key ?? "");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/agents/${agentId}/api-keys/${id}`, { method: "DELETE" });
      if (secret) setSecret("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function sendTest() {
    if (!secret) return;
    setBusy(true);
    setRaw("");
    setError("");
    try {
      const headers = {
        Authorization: `Bearer ${secret}`,
        "Content-Type": "application/json",
      };
      const created = await fetch(`/v1/agents/${slug}/conversations`, { method: "POST", headers });
      const conversation = (await created.json()) as { id?: string };
      if (!created.ok || !conversation.id) {
        setRaw(JSON.stringify(conversation, null, 2));
        return;
      }
      const reply = await fetch(`/v1/agents/${slug}/conversations/${conversation.id}/messages`, {
        method: "POST",
        headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ text: message }),
      });
      const payload = await reply.json();
      setRaw(JSON.stringify({ status: reply.status, body: payload }, null, 2));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">{t("exposeLoading")}</p>;
  }
  if (error && !exposure) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
        <Button onClick={() => void load()} type="button" variant="outline">
          {t("exposeRetry")}
        </Button>
      </div>
    );
  }

  const card = `${origin}${exposure?.endpoints.agentCard ?? `/v1/agents/${slug}/.well-known/agent-card.json`}`;

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">{t("exposeBody")}</p>
      {exposure && !exposure.published ? <p className="text-sm">{t("exposeUnpublished")}</p> : null}
      {error ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      {canEdit ? (
        <section className="detail-panel space-y-3">
          <label className="block text-sm font-medium" htmlFor="expose-label">
            {t("exposeLabel")}
          </label>
          <Input
            id="expose-label"
            onChange={(event) => setLabel(event.target.value)}
            value={label}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm" htmlFor="expose-rate">
              {t("exposeRate")}
              <Input
                className="mt-1"
                id="expose-rate"
                inputMode="numeric"
                onChange={(event) => setRate(event.target.value)}
                value={rate}
              />
            </label>
            <label className="block text-sm" htmlFor="expose-quota">
              {t("exposeQuota")}
              <Input
                className="mt-1"
                id="expose-quota"
                inputMode="numeric"
                onChange={(event) => setQuota(event.target.value)}
                value={quota}
              />
            </label>
          </div>
          <Button disabled={busy || !label.trim()} onClick={() => void createKey()} type="button">
            {t("exposeCreate")}
          </Button>
          {secret ? (
            <div className="space-y-2">
              <p className="text-sm">{t("exposeSecret")}</p>
              <pre className="overflow-x-auto whitespace-pre-wrap break-all rounded-lg bg-muted p-3 text-xs">
                {secret}
              </pre>
              <Button onClick={() => void copy("secret", secret)} type="button" variant="outline">
                {copied === "secret" ? t("exposeCopied") : t("exposeCopy")}
              </Button>
            </div>
          ) : null}
        </section>
      ) : null}
      <section className="space-y-3">
        {(exposure?.keys ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("exposeEmpty")}</p>
        ) : (
          (exposure?.keys ?? []).map((item) => (
            <article className="detail-panel" key={item.id}>
              <h2 className="text-sm font-medium">
                {item.label}{" "}
                <span className="font-normal text-muted-foreground">{item.prefix}</span>
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {t("exposeUsage")}: {item.monthCount} / {item.monthlyQuota || "—"} ·{" "}
                {item.rateLimitRpm}/min
              </p>
              <p className="text-sm text-muted-foreground">
                {t("exposeLastUsed")}: {item.lastUsedAt ? item.lastUsedAt : t("exposeNever")}
                {item.revokedAt ? ` · ${t("exposeRevoked")}` : ""}
              </p>
              {canEdit && !item.revokedAt ? (
                <div className="mt-3 flex gap-2">
                  <Button onClick={() => void rotate(item.id)} type="button" variant="outline">
                    {t("exposeRotate")}
                  </Button>
                  <Button onClick={() => void revoke(item.id)} type="button" variant="outline">
                    {t("exposeRevoke")}
                  </Button>
                </div>
              ) : null}
            </article>
          ))
        )}
      </section>
      <section className="detail-panel space-y-4">
        <Example
          title={t("exposeCurl")}
          value={examples.curl}
          onCopy={copy}
          copied={copied === "curl"}
        />
        <Example
          title={t("exposeJavaScript")}
          value={examples.javascript}
          onCopy={copy}
          copied={copied === "javascript"}
        />
        <Example
          title={t("exposeMcp")}
          value={examples.mcp}
          onCopy={copy}
          copied={copied === "mcp"}
        />
        <div>
          <h2 className="text-sm font-medium">{t("exposeA2a")}</h2>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all rounded-lg bg-muted p-3 text-xs">
            {card}
          </pre>
        </div>
      </section>
      <section className="detail-panel space-y-3">
        <h2 className="text-sm font-medium">{t("exposeConsole")}</h2>
        <p className="text-sm text-muted-foreground">{t("exposeConsoleHelp")}</p>
        {secret ? (
          <>
            <textarea
              aria-label={t("exposeConsole")}
              className="min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
              onChange={(event) => setMessage(event.target.value)}
              value={message}
            />
            <Button
              disabled={busy || !message.trim()}
              onClick={() => void sendTest()}
              type="button"
            >
              {t("exposeSend")}
            </Button>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">{t("exposeConsoleNeedKey")}</p>
        )}
        {raw ? (
          <section aria-label={t("exposeResponse")}>
            <pre className="overflow-x-auto whitespace-pre-wrap break-all rounded-lg bg-muted p-3 text-xs">
              {raw}
            </pre>
          </section>
        ) : null}
      </section>
    </div>
  );
}

function Example({
  title,
  value,
  copied,
  onCopy,
}: {
  title: string;
  value: string;
  copied: boolean;
  onCopy: (name: string, value: string) => Promise<void>;
}) {
  const t = useTranslations("agents");
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-medium">{title}</h2>
        <Button
          onClick={() => void onCopy(title.toLowerCase(), value)}
          type="button"
          variant="outline"
        >
          {copied ? t("exposeCopied") : t("exposeCopy")}
        </Button>
      </div>
      <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all rounded-lg bg-muted p-3 text-xs">
        {value}
      </pre>
    </div>
  );
}
