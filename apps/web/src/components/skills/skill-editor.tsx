"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type Asset = { path: string; fileId?: string; sha256?: string };
type Version = {
  version: number;
  instructionsMd?: string;
  requiredTools?: string[];
  assets?: Asset[];
  hash?: string;
};
type Skill = {
  id: string;
  name: string;
  slug: string;
  description?: string;
  status?: string;
  publishedVersion?: number | null;
  draft?: Version | null;
  published?: Version | null;
};
type Used = {
  agents?: { slug?: string; name?: string; state?: string; updateAvailable?: boolean }[];
};

const MODE_KEY = "ar-settings-mode";

export function SkillEditor() {
  const t = useTranslations("skills");
  const params = useParams<{ skillId: string }>();
  const skillId = params.skillId;
  const [skill, setSkill] = useState<Skill | null>(null);
  const [instructions, setInstructions] = useState("");
  const [note, setNote] = useState("");
  const [tools, setTools] = useState("");
  const [versions, setVersions] = useState<Version[]>([]);
  const [used, setUsed] = useState<Used>({});
  const [preview, setPreview] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const body = await api<Skill>(`/api/v1/skills/${skillId}`);
      const history = await api<{ items: Version[] }>(`/api/v1/skills/${skillId}/versions`);
      const where = await api<Used>(`/api/v1/skills/${skillId}/where-used`);
      const source = body.draft ?? body.published;
      setSkill(body);
      setInstructions(source?.instructionsMd ?? "");
      setTools((source?.requiredTools ?? []).join(", "));
      setVersions(history.items ?? []);
      setUsed(where);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [skillId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/skills/${skillId}`, {
        method: "PATCH",
        body: JSON.stringify({
          instructionsMd: instructions,
          requiredTools: tools
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
        }),
      });
      setNotice(t("saved"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    setBusy(true);
    setError("");
    try {
      await save();
      await api(`/api/v1/skills/${skillId}:publish`, {
        method: "POST",
        body: JSON.stringify({ changeNote: note }),
      });
      setNote("");
      setNotice(t("published"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function republish() {
    setBusy(true);
    setError("");
    try {
      const result = await api<{ results: { slug?: string; status?: string }[] }>(
        `/api/v1/skills/${skillId}:republish-dependants`,
        { method: "POST", body: "{}" },
      );
      const failed = (result.results ?? []).filter((item) => item.status !== "published");
      setNotice(failed.length ? t("republishPartial") : t("republished"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File) {
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.set("upload", file);
      body.set("mime_type", file.type || "text/plain");
      const saved = await api<{ id: string }>("/api/v1/files:upload", { method: "POST", body });
      const current = skill?.draft?.assets ?? skill?.published?.assets ?? [];
      await api(`/api/v1/skills/${skillId}`, {
        method: "PATCH",
        body: JSON.stringify({
          assets: [
            ...current.map((item) => ({ path: item.path, fileId: item.fileId })),
            { path: file.name, fileId: saved.id },
          ],
        }),
      });
      setNotice(t("assetAdded"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  const assets = skill?.draft?.assets ?? skill?.published?.assets ?? [];

  return (
    <AppShell>
      <PageHeader body={skill?.description || t("editorBody")} title={skill?.name || t("title")} />
      <Button asChild className="mb-4" variant="outline">
        <Link href="/skills">{t("back")}</Link>
      </Button>
      {error ? (
        <p className="mb-3 text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? <p className="mb-3 text-sm">{notice}</p> : null}
      {loading ? <Skeleton className="h-40 w-full" /> : null}
      {!loading && skill ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <section>
            <label className="text-sm font-medium" htmlFor="skill-md">
              {t("instructions")}
            </label>
            <textarea
              className="mt-2 min-h-64 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
              id="skill-md"
              onChange={(event) => setInstructions(event.target.value)}
              value={instructions}
            />
          </section>
          <section
            aria-label={t("preview")}
            className="rounded-xl border border-[var(--border)] p-4"
          >
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-medium">{t("preview")}</h2>
              <Button
                onClick={() => setPreview((current) => !current)}
                type="button"
                variant="ghost"
              >
                {preview ? t("hidePreview") : t("showPreview")}
              </Button>
            </div>
            {preview ? (
              <div className="prose-sm text-sm">
                <ReactMarkdown>{instructions || t("emptyPreview")}</ReactMarkdown>
              </div>
            ) : (
              <p className="text-sm text-[var(--muted-foreground)]">{t("emptyPreview")}</p>
            )}
          </section>
        </div>
      ) : null}
      {advanced ? (
        <section className="mt-4">
          <label className="text-sm" htmlFor="required-tools">
            {t("tools")}
          </label>
          <Input
            className="mt-1 max-w-xl"
            id="required-tools"
            onChange={(event) => setTools(event.target.value)}
            value={tools}
          />
          <label className="mt-3 block text-sm" htmlFor="skill-asset">
            {t("assets")}
          </label>
          <input
            className="mt-1 block text-sm"
            id="skill-asset"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                void upload(file);
              }
            }}
            type="file"
          />
          <ul className="mt-2 text-sm">
            {assets.map((asset) => (
              <li key={asset.path}>{asset.path}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <section className="mt-6 rounded-xl border border-[var(--border)] p-4">
        <h2 className="text-sm font-medium">{t("publish")}</h2>
        <Input
          aria-label={t("changeNote")}
          className="mt-2 max-w-md"
          onChange={(event) => setNote(event.target.value)}
          placeholder={t("changeNote")}
          value={note}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <Button disabled={busy} onClick={() => void save()} type="button" variant="outline">
            {t("save")}
          </Button>
          <Button disabled={busy} onClick={() => void publish()} type="button">
            {t("publish")}
          </Button>
          <Button
            onClick={() => {
              const next = !advanced;
              setAdvanced(next);
              window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
            }}
            type="button"
            variant="ghost"
          >
            {advanced ? t("hideAdvanced") : t("showAdvanced")}
          </Button>
        </div>
      </section>
      <section className="mt-4">
        <h2 className="text-sm font-medium">{t("versions")}</h2>
        {versions.length === 0 ? (
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">{t("noVersions")}</p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {versions.map((version) => (
              <li key={version.version}>v{version.version}</li>
            ))}
          </ul>
        )}
      </section>
      <section className="mt-4">
        <h2 className="text-sm font-medium">{t("whereUsed")}</h2>
        {(used.agents ?? []).length === 0 ? (
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">{t("unused")}</p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {(used.agents ?? []).map((agent) => (
              <li key={`${agent.slug}-${agent.state}`}>
                {agent.name || agent.slug} · {agent.state}
                {agent.updateAvailable ? ` · ${t("updateAvailable")}` : ""}
              </li>
            ))}
          </ul>
        )}
        <Button
          className="mt-3"
          disabled={busy}
          onClick={() => void republish()}
          type="button"
          variant="outline"
        >
          {t("republish")}
        </Button>
      </section>
    </AppShell>
  );
}
