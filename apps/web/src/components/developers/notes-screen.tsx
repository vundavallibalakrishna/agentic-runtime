"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { NotesView, wholeGuide } from "@/components/developers/notes-view";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { loadSession } from "@/lib/session";

type Agent = { slug: string; name: string; status?: string };

export function NotesScreen() {
  const t = useTranslations("developers");
  const [origin, setOrigin] = useState("");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentSlug, setAgentSlug] = useState("");
  const [canManageKeys, setCanManageKeys] = useState(false);

  useEffect(() => {
    setOrigin(window.location.origin);
    // The samples name one of this workspace's own agents. The notes read the same
    // without them, so a failure here leaves the placeholder.
    void loadSession()
      .then((session) => {
        const permissions = session.permissions ?? [];
        setCanManageKeys(permissions.includes("service_accounts:manage"));
        return permissions.includes("agents:read")
          ? api<{ items?: Agent[] }>("/api/v1/agents")
          : { items: [] };
      })
      .then((page) => {
        const found = page.items ?? [];
        setAgents(found);
        setAgentSlug((current) => current || found[0]?.slug || "");
      })
      .catch(() => undefined);
  }, []);

  const values = { baseUrl: origin || "<BASE_URL>", agentSlug: agentSlug || "<agent-slug>" };

  function download() {
    const file = new Blob([wholeGuide(values)], { type: "text/markdown" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(file);
    link.download = "integration-guide.md";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return (
    <AppShell>
      <PageHeader
        actions={
          <Button onClick={download} type="button" variant="outline">
            {t("download")}
          </Button>
        }
        body={t("notesBody")}
        title={t("notesTitle")}
      />
      <div className="mb-6 flex flex-wrap items-end gap-4 text-sm">
        {agents.length > 0 ? (
          <label htmlFor="notes-agent">
            {t("sampleAgent")}
            <select
              className="mt-1 block rounded-lg border border-[var(--border)] bg-[var(--card)] p-2"
              id="notes-agent"
              onChange={(event) => setAgentSlug(event.target.value)}
              value={agentSlug}
            >
              {agents.map((agent) => (
                <option key={agent.slug} value={agent.slug}>
                  {agent.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {canManageKeys ? (
          <Link className="underline" href="/admin/developers/keys">
            {t("toKeys")}
          </Link>
        ) : null}
        <a className="underline" href="/api/v1/openapi.json">
          {t("openapiManagement")}
        </a>
        <a className="underline" href="/v1/openapi.json">
          {t("openapiAgent")}
        </a>
        <Link className="underline" href="/developer-guide">
          {t("publicCopy")}
        </Link>
      </div>
      <NotesView agentSlug={values.agentSlug} baseUrl={values.baseUrl} />
    </AppShell>
  );
}
