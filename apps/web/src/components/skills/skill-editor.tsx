"use client";

import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

import { AppShell } from "@/components/app-shell";
import { ActionStatus, BackButton, DetailState } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { ReferencePicker } from "@/components/common/reference-picker";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type Session } from "@/lib/api";
import { loadSession } from "@/lib/session";

import { SkillDependants, SkillHistory } from "./skill-records";

type Asset = { path: string; fileId?: string; sha256?: string };
type Version = {
  version: number;
  hash?: string;
  instructionsMd?: string;
  requiredTools?: string[];
  assets?: Asset[];
};
type Skill = {
  id: string;
  name: string;
  slug: string;
  description?: string;
  status?: string;
  owner?: { id: string } | null;
  publishedVersion?: number | null;
  draft?: Version | null;
  published?: Version | null;
};
const MODE_KEY = "ar-settings-mode";

export function SkillEditor() {
  const { skillId } = useParams<{ skillId: string }>();
  return <Editor key={skillId} skillId={skillId} />;
}
function Editor({ skillId }: { skillId: string }) {
  const t = useTranslations("skills");
  const router = useRouter();
  const [skill, setSkill] = useState<Skill | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [instructions, setInstructions] = useState("");
  const [tools, setTools] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const [tab, setTab] = useState("instructions");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState("");
  const [revision, setRevision] = useState(0);
  const [resourceQuery, setResourceQuery] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [assetPath, setAssetPath] = useState("");
  const uploaded = useRef("");
  const request = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const action = useRef(false);
  const busy = Boolean(pending);
  const canEdit = Boolean(
    skill &&
      skill.status !== "archived" &&
      (session?.permissions?.includes("skills:manage_all") ||
        (session?.user?.id && skill.owner?.id === session.user.id)),
  );
  const canImport = session?.permissions?.includes("skills:create") ?? false;
  const canChooseTools = session?.permissions?.includes("tools:read") ?? false;
  const source = skill?.draft ?? skill?.published;
  const assets = source?.assets ?? [];
  const dirty =
    instructions !== (source?.instructionsMd ?? "") ||
    JSON.stringify(tools) !== JSON.stringify(source?.requiredTools ?? []);
  const apply = useCallback((body: Skill) => {
    setSkill(body);
    const content = body.draft ?? body.published;
    setInstructions(content?.instructionsMd ?? "");
    setTools(content?.requiredTools ?? []);
  }, []);
  const load = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError("");
    try {
      const [body, current] = await Promise.all([
        api<Skill>(`/api/v1/skills/${skillId}`, { signal: controller.signal }),
        loadSession(),
      ]);
      if (controller.signal.aborted) return;
      apply(body);
      setSession(current);
    } catch (caught) {
      if (!controller.signal.aborted)
        setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [skillId, t, apply]);
  useEffect(() => {
    mounted.current = true;
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
    void load();
    return () => {
      mounted.current = false;
      request.current?.abort();
    };
  }, [load]);
  function chooseMode(value: boolean) {
    setAdvanced(value);
    if (!value && tab === "resources") setTab("instructions");
    window.localStorage.setItem(MODE_KEY, value ? "advanced" : "simple");
  }
  async function perform(name: string, operation: () => Promise<void>) {
    if (action.current) return;
    action.current = true;
    setPending(name);
    setActionError("");
    setNotice("");
    try {
      await operation();
    } catch (caught) {
      if (mounted.current) setActionError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      action.current = false;
      if (mounted.current) setPending("");
    }
  }
  async function persistDraft(extra?: { assets: { path: string; fileId?: string }[] }) {
    return api<Skill>(`/api/v1/skills/${skillId}`, {
      method: "PATCH",
      body: JSON.stringify({ instructionsMd: instructions, requiredTools: tools, ...extra }),
    });
  }
  function save(publish = false) {
    if (!canEdit || (publish && !instructions.trim())) return;
    void perform(publish ? "publish" : "save", async () => {
      const draft = await persistDraft();
      if (!mounted.current) return;
      // Reflect the saved draft even when the subsequent publish fails.
      apply(draft);
      setNotice(t("saved"));
      if (publish) {
        const published = await api<Skill>(`/api/v1/skills/${skillId}:publish`, {
          method: "POST",
          body: JSON.stringify({ changeNote: note }),
        });
        if (!mounted.current) return;
        apply(published);
        setNote("");
        setRevision((value) => value + 1);
      }
      setNotice(t(publish ? "published" : "saved"));
    });
  }
  function exportSkill() {
    void perform("export", async () => {
      const body = await api<{ archiveB64: string; filename: string }>(
        `/api/v1/skills/${skillId}:export`,
        { method: "POST" },
      );
      if (!mounted.current) return;
      if (!body.archiveB64 || !body.filename) throw new Error(t("exportIncomplete"));
      const bytes = Uint8Array.from(atob(body.archiveB64), (character) => character.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: "application/zip" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = body.filename;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice(t("exported"));
    });
  }
  function importSkill(selected: File) {
    if (!canImport) return;
    void perform("import", async () => {
      const markdown = await selected.text();
      if (!mounted.current) return;
      const created = await api<{ id: string }>("/api/v1/skills:import", {
        method: "POST",
        body: JSON.stringify({ markdown }),
      });
      if (mounted.current) router.push(`/skills/${created.id}`);
    });
  }
  const pathValid =
    /^[A-Za-z0-9._/-]{1,200}$/.test(assetPath) &&
    !assetPath.split("/").includes("..") &&
    !assetPath.startsWith("/") &&
    !assets.some((asset) => asset.path === assetPath);
  function attach() {
    if (!canEdit || !file || !pathValid) return;
    void perform("upload", async () => {
      if (!uploaded.current) {
        const body = new FormData();
        body.set("upload", file);
        body.set("mime_type", file.type || "application/octet-stream");
        const saved = await api<{ id: string }>("/api/v1/files:upload", { method: "POST", body });
        uploaded.current = saved.id;
      }
      if (!mounted.current) return;
      const saved = await persistDraft({
        assets: [
          ...assets.map((item) => ({ path: item.path, fileId: item.fileId })),
          { path: assetPath, fileId: uploaded.current },
        ],
      });
      if (!mounted.current) return;
      apply(saved);
      setFile(null);
      setAssetPath("");
      uploaded.current = "";
      setNotice(t("assetAdded"));
    });
  }
  const selectedTools = tools.filter((tool) =>
    tool.toLocaleLowerCase().includes(resourceQuery.trim().toLocaleLowerCase()),
  );
  const toolPagination = usePagedRows(selectedTools, resourceQuery);
  const matchingAssets = assets.filter((asset) =>
    asset.path.toLocaleLowerCase().includes(resourceQuery.trim().toLocaleLowerCase()),
  );
  const assetPagination = usePagedRows(matchingAssets, resourceQuery);
  return (
    <AppShell>
      <PageHeader
        title={skill?.name || t("title")}
        body={skill?.description || t("editorBody")}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <SettingsMode advanced={advanced} onChange={chooseMode} />
            <BackButton href="/skills">{t("back")}</BackButton>
          </div>
        }
      />
      <DetailState loading={loading} error={error} onRetry={() => void load()} />
      <ActionStatus busy={busy} notice={notice} />
      {!loading && skill ? (
        <>
          <div className="mb-5 flex flex-wrap items-center gap-3 text-sm">
            <Badge tone={statusTone(skill.status)}>
              {skill.status && t.has(`states.${skill.status}`)
                ? t(`states.${skill.status}`)
                : skill.status}
            </Badge>
            <span>
              {skill.publishedVersion != null
                ? t("publishedVersion", { version: skill.publishedVersion })
                : t("noVersions")}
            </span>
            {skill.draft?.hash &&
            skill.published?.hash &&
            skill.draft.hash !== skill.published.hash ? (
              <Badge tone="warning">{t("unpublishedDraft")}</Badge>
            ) : null}
            {dirty ? <span className="text-[var(--muted-foreground)]">{t("unsaved")}</span> : null}
          </div>
          {!canEdit ? (
            <p className="mb-4 text-sm text-[var(--muted-foreground)]">{t("readOnly")}</p>
          ) : null}
          {actionError ? (
            <p role="alert" className="mb-4 break-words text-sm text-[var(--destructive)]">
              {actionError}
            </p>
          ) : null}
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="instructions">{t("instructions")}</TabsTrigger>
              {advanced ? <TabsTrigger value="resources">{t("resources")}</TabsTrigger> : null}
              <TabsTrigger value="versions">{t("versions")}</TabsTrigger>
              <TabsTrigger value="dependants">{t("whereUsed")}</TabsTrigger>
            </TabsList>
            <TabsContent value="instructions">
              <fieldset disabled={busy} className="min-w-0 space-y-6">
                <div className="grid min-w-0 gap-6 xl:grid-cols-2">
                  <section className="detail-panel min-w-0">
                    <label className="text-sm font-medium" htmlFor="skill-md">
                      {t("instructions")}
                    </label>
                    <p className="my-2 text-xs text-[var(--muted-foreground)]">
                      {t("workingCopyHelp")}
                    </p>
                    <textarea
                      id="skill-md"
                      className="min-h-72 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"
                      value={instructions}
                      readOnly={!canEdit}
                      onChange={(event) => setInstructions(event.target.value)}
                    />
                  </section>
                  <section aria-label={t("preview")} className="detail-panel min-w-0">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <h2 className="text-sm font-medium">{t("preview")}</h2>
                      <Button
                        type="button"
                        variant="ghost"
                        aria-expanded={preview}
                        aria-controls="skill-preview"
                        onClick={() => setPreview((value) => !value)}
                      >
                        {preview ? t("hidePreview") : t("showPreview")}
                      </Button>
                    </div>
                    <div id="skill-preview">
                      {preview ? (
                        <div className="prose-sm max-h-[30rem] min-w-0 overflow-auto break-words text-sm [&_pre]:overflow-auto [&_table]:overflow-auto [&_a]:break-all">
                          <ReactMarkdown>{instructions || t("emptyPreview")}</ReactMarkdown>
                        </div>
                      ) : (
                        <p className="text-sm text-[var(--muted-foreground)]">
                          {t("previewHidden")}
                        </p>
                      )}
                    </div>
                  </section>
                </div>
                <section className="detail-panel">
                  <h2 className="text-sm font-medium">{t("publish")}</h2>
                  <p className="my-3 text-sm text-[var(--muted-foreground)]">{t("publishHelp")}</p>
                  <label className="text-sm" htmlFor="skill-change-note">
                    {t("changeNote")}
                  </label>
                  <Input
                    id="skill-change-note"
                    className="mt-1 max-w-xl"
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    disabled={!canEdit}
                  />
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!canEdit || !dirty}
                      onClick={() => save()}
                    >
                      {pending === "save" ? t("saving") : t("save")}
                    </Button>
                    <Button
                      type="button"
                      disabled={!canEdit || !instructions.trim()}
                      onClick={() => save(true)}
                    >
                      {pending === "publish" ? t("publishing") : t("publish")}
                    </Button>
                  </div>
                </section>
              </fieldset>
            </TabsContent>
            {advanced ? (
              <TabsContent value="resources">
                <fieldset disabled={busy} className="min-w-0 space-y-6">
                  <section className="detail-panel">
                    <h2 className="mb-3 text-sm font-medium">{t("resources")}</h2>
                    <Input
                      type="search"
                      aria-label={t("resourceSearch")}
                      placeholder={t("resourceSearch")}
                      value={resourceQuery}
                      onChange={(event) => setResourceQuery(event.target.value)}
                    />
                    <div className="mt-4">
                      <ReferencePicker
                        multiple
                        label={t("tools")}
                        endpoint="/api/v1/tools"
                        getValue={(row) => row.qualifiedName ?? ""}
                        value={tools}
                        onChange={(values) => setTools(values)}
                        disabled={!canEdit || !canChooseTools}
                        help={t("toolsHelp")}
                      />
                      <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                        {t(canChooseTools ? "toolsHelp" : "toolAccess")}
                      </p>
                    </div>
                    <ul className="mt-3 divide-y divide-[var(--border)]">
                      {toolPagination.rows.map((tool) => (
                        <li
                          key={tool}
                          className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
                        >
                          <span className="min-w-0 break-all">{tool}</span>
                          {canEdit ? (
                            <Button
                              type="button"
                              variant="ghost"
                              aria-label={t("removeToolNamed", { name: tool })}
                              onClick={() =>
                                setTools((values) => values.filter((value) => value !== tool))
                              }
                            >
                              {t("remove")}
                            </Button>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                    {!selectedTools.length ? (
                      <p className="mt-3 text-sm text-[var(--muted-foreground)]">
                        {t(tools.length ? "noResourceMatches" : "noTools")}
                      </p>
                    ) : null}
                    {tools.length ? (
                      <ListPagination {...toolPagination} label={t("tools")} />
                    ) : null}
                    <h3 className="mt-6 text-sm font-medium">{t("assetFiles")}</h3>
                    <ul className="mt-2 divide-y divide-[var(--border)]">
                      {assetPagination.rows.map((asset) => (
                        <li key={asset.path} className="break-all py-2 text-sm">
                          {asset.path}
                        </li>
                      ))}
                    </ul>
                    {!matchingAssets.length ? (
                      <p className="mt-3 text-sm text-[var(--muted-foreground)]">
                        {t(assets.length ? "noResourceMatches" : "noAssets")}
                      </p>
                    ) : null}
                    {assets.length ? (
                      <ListPagination {...assetPagination} label={t("assetFiles")} />
                    ) : null}
                    <p className="mt-5 text-sm text-[var(--muted-foreground)]">
                      {t("resourceSaveHelp")}
                    </p>
                    <Button
                      className="mt-3"
                      type="button"
                      variant="outline"
                      disabled={!canEdit || !dirty}
                      onClick={() => save()}
                    >
                      {pending === "save" ? t("saving") : t("save")}
                    </Button>
                  </section>
                  {canEdit ? (
                    <section className="detail-panel">
                      <h2 className="text-sm font-medium">{t("attachAsset")}</h2>
                      <p className="my-3 text-sm text-[var(--muted-foreground)]">
                        {t("assetHelp")}
                      </p>
                      <label className="block text-sm" htmlFor="skill-asset">
                        {t("assets")}
                      </label>
                      <input
                        type="file"
                        id="skill-asset"
                        className="mt-2 block w-full min-w-0 max-w-full text-sm"
                        onChange={(event) => {
                          const chosen = event.target.files?.[0];
                          if (!chosen) return;
                          setFile(chosen);
                          setAssetPath(chosen.name);
                          uploaded.current = "";
                          event.target.value = "";
                        }}
                      />
                      {file ? (
                        <>
                          <p className="mt-3 break-all text-xs">{file.name}</p>
                          <label className="mt-3 block text-sm" htmlFor="skill-asset-path">
                            {t("assetPath")}
                          </label>
                          <Input
                            id="skill-asset-path"
                            aria-invalid={!pathValid}
                            className="mt-1"
                            value={assetPath}
                            onChange={(event) => setAssetPath(event.target.value)}
                          />
                          <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                            {assets.some((asset) => asset.path === assetPath)
                              ? t("assetPathUsed")
                              : t("assetPathHelp")}
                          </p>
                          <Button
                            type="button"
                            className="mt-3"
                            disabled={!pathValid}
                            onClick={attach}
                          >
                            {t("attachAsset")}
                          </Button>
                          <Button
                            type="button"
                            className="mt-3 ml-2"
                            variant="outline"
                            onClick={() => {
                              setFile(null);
                              setAssetPath("");
                              uploaded.current = "";
                            }}
                          >
                            {t("cancelSelection")}
                          </Button>
                        </>
                      ) : null}
                    </section>
                  ) : null}
                  <section className="detail-panel">
                    <h2 className="text-sm font-medium">{t("portable")}</h2>
                    <p className="my-3 text-sm text-[var(--muted-foreground)]">{t("exportHelp")}</p>
                    <Button type="button" variant="outline" onClick={exportSkill}>
                      {pending === "export" ? t("exporting") : t("export")}
                    </Button>
                    {canImport ? (
                      <div className="mt-5">
                        <label className="block text-sm" htmlFor="skill-import">
                          {t("importNew")}
                        </label>
                        <p className="my-2 text-xs text-[var(--muted-foreground)]">
                          {t("importNewHelp")}
                        </p>
                        <input
                          id="skill-import"
                          type="file"
                          accept=".md,text/markdown"
                          className="block w-full min-w-0 max-w-full text-sm"
                          onChange={(event) => {
                            const chosen = event.target.files?.[0];
                            if (chosen) importSkill(chosen);
                            event.target.value = "";
                          }}
                        />
                      </div>
                    ) : null}
                  </section>
                </fieldset>
              </TabsContent>
            ) : null}
            <TabsContent value="versions">
              <SkillHistory key={revision} skillId={skillId} />
            </TabsContent>
            <TabsContent value="dependants">
              <SkillDependants
                key={revision}
                skillId={skillId}
                canOpenAgent={session?.permissions?.includes("agents:read") ?? false}
              />
            </TabsContent>
          </Tabs>
        </>
      ) : null}
    </AppShell>
  );
}
