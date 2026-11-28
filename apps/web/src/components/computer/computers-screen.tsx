"use client";

import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ActionStatus, DetailState, ErrorMessage } from "@/components/common/detail-state";
import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { SettingsMode } from "@/components/common/settings-mode";
import { PageHeader } from "@/components/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { TableScroll } from "@/components/ui/table";
import { ApiError, api, type DisplayError } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { loadSession } from "@/lib/session";

type Row = Record<string, unknown>;
type Template = Row & {
  id: string;
  name: string;
  slug: string;
  cpuMillis: number;
  memoryMb: number;
  allowPackages: boolean;
};
type Instance = Row & { id: string; status: string };
type Kind = "read" | "save" | "terminate";
type Operation = { controller: AbortController; kind: Kind };
const MODE_KEY = "ar-settings-mode";
const text = (value: unknown): value is string =>
  typeof value === "string" && Boolean(value.trim());
const positive = (value: unknown): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value > 0;
const optionalResource = (value: string) => !value.trim() || positive(Number(value));
const templateValid = (value: unknown): value is Template => {
  if (!value || typeof value !== "object") return false;
  const row = value as Row;
  return (
    text(row.id) &&
    text(row.name) &&
    text(row.slug) &&
    positive(row.cpuMillis) &&
    positive(row.memoryMb) &&
    typeof row.allowPackages === "boolean"
  );
};
const instanceValid = (value: unknown): value is Instance => {
  if (!value || typeof value !== "object") return false;
  const row = value as Row;
  return (
    text(row.id) &&
    text(row.status) &&
    [row.scopeKey, row.templateSlug, row.error].every(
      (item) => item == null || typeof item === "string",
    )
  );
};
const ended = (row: Instance) => ["terminated", "failed"].includes(row.status);
const permissionFailure = (error: unknown) =>
  error instanceof ApiError &&
  (error.status === 401 || (error.status === 403 && error.code !== "csrf_failed"));

export function ComputersScreen() {
  const t = useTranslations("computers");
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [live, setLive] = useState<Instance[] | null>(null);
  const [templateError, setTemplateError] = useState<DisplayError>("");
  const [instanceError, setInstanceError] = useState<DisplayError>("");
  const [actionError, setActionError] = useState<DisplayError>("");
  const [notice, setNotice] = useState("");
  const [lastAction, setLastAction] = useState<"save" | "terminate" | null>(null);
  const [pending, setPending] = useState<Kind | null>("read");
  const [reading, setReading] = useState({ templates: true, instances: true });
  const [manage, setManage] = useState<boolean | null>(null);
  const [canStop, setCanStop] = useState(false);
  const [uncertain, setUncertain] = useState<"template" | "instance" | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [cpu, setCpu] = useState("");
  const [memory, setMemory] = useState("");
  const [packages, setPackages] = useState<"default" | "allow" | "block">("default");
  const [formError, setFormError] = useState("");
  const [templateQuery, setTemplateQuery] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<Instance | null>(null);
  const operation = useRef<Operation | null>(null);
  const feedback = useRef<HTMLDivElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const refreshButton = useRef<HTMLButtonElement>(null);
  const templateSearch = useRef<HTMLInputElement>(null);
  const nameInput = useRef<HTMLInputElement>(null);
  const instanceSearch = useRef<HTMLInputElement>(null);

  const deny = useCallback(() => {
    setManage(false);
    setCanStop(false);
    setTemplates(null);
    setLive(null);
  }, []);
  const permitted = useCallback(
    async (active: Operation) => {
      const session = await loadSession();
      if (active.controller.signal.aborted) return false;
      const allowed = (session.permissions ?? []).includes("sandboxes:manage");
      setManage(allowed);
      setCanStop(allowed && (session.permissions ?? []).includes("chat:use"));
      if (!allowed) deny();
      return allowed;
    },
    [deny],
  );
  const read = useCallback(
    async (active: Operation) => {
      const result: { templates: Template[] | null; instances: Instance[] | null } = {
        templates: null,
        instances: null,
      };
      setReading({ templates: true, instances: true });
      setTemplateError("");
      setInstanceError("");
      let denied = false;
      const failed = (caught: unknown, section: "templates" | "instances") => {
        if (active.controller.signal.aborted) return;
        if (permissionFailure(caught)) {
          denied = true;
          result.templates = null;
          result.instances = null;
          deny();
        }
        const failure = caught instanceof Error ? caught : t("error");
        if (section === "templates") setTemplateError(failure);
        else setInstanceError(failure);
      };
      const finished = (section: "templates" | "instances") => {
        if (!active.controller.signal.aborted)
          setReading((current) => ({ ...current, [section]: false }));
      };
      try {
        if (!(await permitted(active))) return result;
        const options = { signal: active.controller.signal };
        await Promise.all([
          api<{ items: unknown[] }>("/api/v1/sandbox-templates", options)
            .then((body) => {
              if (active.controller.signal.aborted || denied) return;
              if (!Array.isArray(body?.items) || !body.items.every(templateValid))
                throw new Error(t("templateMetadataError"));
              result.templates = body.items;
              setTemplates(body.items);
            })
            .catch((caught) => failed(caught, "templates"))
            .finally(() => finished("templates")),
          api<{ items: unknown[] }>("/api/v1/sandboxes", options)
            .then((body) => {
              if (active.controller.signal.aborted || denied) return;
              if (!Array.isArray(body?.items) || !body.items.every(instanceValid))
                throw new Error(t("instanceMetadataError"));
              result.instances = body.items;
              setLive(body.items);
            })
            .catch((caught) => failed(caught, "instances"))
            .finally(() => finished("instances")),
        ]);
      } catch (caught) {
        failed(caught, "templates");
        failed(caught, "instances");
      } finally {
        if (!active.controller.signal.aborted) setReading({ templates: false, instances: false });
      }
      return result;
    },
    [permitted, deny, t],
  );
  const refresh = useCallback(async () => {
    if (operation.current) return;
    const active: Operation = { controller: new AbortController(), kind: "read" };
    operation.current = active;
    setPending("read");
    try {
      const result = await read(active);
      if (active.controller.signal.aborted) return;
      if (
        (uncertain === "template" && result.templates) ||
        (uncertain === "instance" && result.instances)
      ) {
        setUncertain(null);
        setActionError("");
        setNotice(t("checked"));
      }
    } finally {
      if (operation.current === active) {
        operation.current = null;
        setPending(null);
      }
    }
  }, [read, uncertain, t]);
  // The initial read is separate from manual recovery so uncertainty changes never replay a read or write.
  useEffect(() => {
    const active: Operation = { controller: new AbortController(), kind: "read" };
    operation.current = active;
    void read(active).finally(() => {
      if (operation.current === active) {
        operation.current = null;
        setPending(null);
      }
    });
    return () => {
      operation.current?.controller.abort();
      operation.current = null;
    };
  }, [read]);
  useEffect(() => {
    setAdvanced(window.localStorage.getItem(MODE_KEY) === "advanced");
  }, []);
  useEffect(() => {
    if (actionError) feedback.current?.focus();
  }, [actionError]);
  function choose(next: boolean) {
    setAdvanced(next);
    window.localStorage.setItem(MODE_KEY, next ? "advanced" : "simple");
  }
  const formValid = Boolean(
    name.trim() &&
      /^[a-z0-9-]+$/i.test(slug.trim()) &&
      optionalResource(cpu) &&
      optionalResource(memory) &&
      ["default", "allow", "block"].includes(packages),
  );
  const writesHeld = Boolean(pending || uncertain || !manage);
  const freshSelected = selected && live?.find((row) => row.id === selected.id);

  async function save() {
    if (operation.current || uncertain || !manage || templateError || templates === null) return;
    if (!formValid) {
      setFormError(t("invalidForm"));
      return;
    }
    const body = {
      name: name.trim(),
      slug: slug.trim().toLowerCase(),
      ...(cpu.trim() ? { cpuMillis: Number(cpu) } : {}),
      ...(memory.trim() ? { memoryMb: Number(memory) } : {}),
      ...(packages !== "default" ? { allowPackages: packages === "allow" } : {}),
    };
    const active: Operation = { controller: new AbortController(), kind: "save" };
    operation.current = active;
    setPending("save");
    setLastAction("save");
    setActionError("");
    setNotice("");
    setFormError("");
    try {
      if (!(await permitted(active))) return;
      const saved = await api<unknown>("/api/v1/sandbox-templates", {
        method: "POST",
        body: JSON.stringify(body),
        signal: active.controller.signal,
      });
      if (active.controller.signal.aborted) return;
      if (
        !templateValid(saved) ||
        Object.entries(body).some(([key, value]) => saved[key] !== value)
      )
        throw new Error(t("saveUnconfirmed"));
      setNotice(t("saved"));
      setName("");
      setSlug("");
      setCpu("");
      setMemory("");
      setPackages("default");
      const result = await read(active);
      if (active.controller.signal.aborted) return;
      if (result.templates && !result.templates.some((row) => row.id === saved.id))
        setNotice(t("savedNotListed"));
    } catch (caught) {
      if (!active.controller.signal.aborted) {
        setActionError(caught instanceof Error ? caught : t("error"));
        setUncertain("template");
        if (permissionFailure(caught)) deny();
      }
    } finally {
      if (operation.current === active) {
        operation.current = null;
        setPending(null);
      }
    }
  }
  async function terminate() {
    if (
      operation.current ||
      uncertain ||
      !canStop ||
      instanceError ||
      !freshSelected ||
      ended(freshSelected)
    )
      return;
    const id = freshSelected.id;
    const active: Operation = { controller: new AbortController(), kind: "terminate" };
    operation.current = active;
    setPending("terminate");
    setLastAction("terminate");
    setActionError("");
    setNotice("");
    try {
      if (!(await permitted(active))) return;
      const session = await loadSession();
      if (active.controller.signal.aborted) return;
      if (!(session.permissions ?? []).includes("chat:use")) throw new Error(t("stopDenied"));
      const receipt = await api<unknown>(`/api/v1/sandboxes/${encodeURIComponent(id)}:terminate`, {
        method: "POST",
        signal: active.controller.signal,
      });
      if (active.controller.signal.aborted) return;
      if (!instanceValid(receipt) || receipt.id !== id || !ended(receipt))
        throw new Error(t("stopUnconfirmed"));
      setNotice(t("stopped"));
      const result = await read(active);
      if (active.controller.signal.aborted) return;
      if (result.instances?.some((row) => row.id === id && !ended(row)))
        setNotice(t("stopNotReflected"));
      setSelected(null);
    } catch (caught) {
      if (!active.controller.signal.aborted) {
        setActionError(caught instanceof Error ? caught : t("error"));
        setUncertain("instance");
        if (permissionFailure(caught)) deny();
      }
    } finally {
      if (operation.current === active) {
        operation.current = null;
        setPending(null);
      }
    }
  }

  const matchingTemplates = useMemo(
    () =>
      (templates ?? []).filter((row) =>
        `${row.name} ${row.slug}`
          .toLocaleLowerCase()
          .includes(templateQuery.trim().toLocaleLowerCase()),
      ),
    [templates, templateQuery],
  );
  const matching = useMemo(
    () =>
      (live ?? []).filter(
        (row) =>
          (!status || row.status === status) &&
          [row.id, row.scopeKey, row.templateSlug, row.status]
            .join(" ")
            .toLocaleLowerCase()
            .includes(query.trim().toLocaleLowerCase()),
      ),
    [live, query, status],
  );
  const statuses = useMemo(
    () => [...new Set([status, ...(live ?? []).map((row) => row.status)])].filter(Boolean).sort(),
    [live, status],
  );
  const templatePage = usePagedRows(matchingTemplates, templateQuery);
  const instancePage = usePagedRows(matching, JSON.stringify([query, status]));
  const actionFeedback = actionError ? (
    <div
      ref={feedback}
      role="alert"
      tabIndex={-1}
      className="mb-4 space-y-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-sm"
    >
      <ErrorMessage error={actionError} />
      <p>{t("checkBeforeRetry")}</p>
      <Button
        type="button"
        variant="outline"
        disabled={Boolean(pending)}
        onClick={() => void refresh()}
      >
        {t("refresh")}
      </Button>
    </div>
  ) : null;
  const retry = pending ? undefined : () => void refresh();

  return (
    <AppShell>
      <PageHeader
        title={t("title")}
        body={t("body")}
        actions={
          <div className="flex flex-wrap gap-2">
            {manage ? (
              <Button
                className="xl:hidden"
                type="button"
                disabled={Boolean(pending)}
                onClick={() => nameInput.current?.focus()}
              >
                {t("createTitle")}
              </Button>
            ) : null}
            <Button asChild variant="outline" className="inline-flex items-center gap-2">
              <button
                ref={refreshButton}
                aria-label={t("refresh")}
                type="button"
                disabled={Boolean(pending)}
                onClick={() => void refresh()}
              >
                <RefreshCw size={16} aria-hidden="true" />
                <span className="hidden sm:inline">{t("refresh")}</span>
              </button>
            </Button>
            <SettingsMode advanced={advanced} onChange={choose} />
          </div>
        }
      />
      {manage === false ? <p className="mb-5 text-sm">{t("readDenied")}</p> : null}
      <ManagementLayout
        title={t("listTitle")}
        formTitle={t("createTitle")}
        form={
          manage ? (
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                void save();
              }}
            >
              <p className="text-sm leading-relaxed text-[var(--muted-foreground)]">
                {t("createHelp")}
              </p>
              <ActionStatus
                busy={pending === "save"}
                busyLabel={t("saving")}
                notice={lastAction === "save" ? notice : ""}
              />
              {lastAction === "save" && !selected ? actionFeedback : null}
              <fieldset className="grid min-w-0 gap-4" disabled={Boolean(pending) || !manage}>
                <label htmlFor="computer-name">
                  {t("name")}
                  <Input
                    className="mt-1"
                    id="computer-name"
                    ref={nameInput}
                    required
                    value={name}
                    onChange={(event) => {
                      setName(event.target.value);
                      setFormError("");
                    }}
                  />
                </label>
                <label htmlFor="computer-slug">
                  {t("slug")}
                  <Input
                    className="mt-1"
                    id="computer-slug"
                    required
                    pattern="[A-Za-z0-9-]+"
                    autoCapitalize="none"
                    spellCheck={false}
                    aria-describedby="computer-slug-help"
                    value={slug}
                    onChange={(event) => {
                      setSlug(event.target.value);
                      setFormError("");
                    }}
                  />
                </label>
                <p
                  id="computer-slug-help"
                  className="text-xs leading-relaxed text-[var(--muted-foreground)]"
                >
                  {t("slugHelp")}
                </p>
                {advanced ? (
                  <>
                    <p
                      id="computer-resource-help"
                      className="text-xs leading-relaxed text-[var(--muted-foreground)]"
                    >
                      {t("resourceHelp")}
                    </p>
                    <label htmlFor="computer-cpu">
                      {t("cpu")}
                      <Input
                        className="mt-1"
                        id="computer-cpu"
                        type="number"
                        min={1}
                        step={1}
                        aria-describedby="computer-resource-help"
                        aria-invalid={!optionalResource(cpu)}
                        value={cpu}
                        onChange={(event) => setCpu(event.target.value)}
                      />
                    </label>
                    <label htmlFor="computer-memory">
                      {t("memory")}
                      <Input
                        className="mt-1"
                        id="computer-memory"
                        type="number"
                        min={1}
                        step={1}
                        aria-describedby="computer-resource-help"
                        aria-invalid={!optionalResource(memory)}
                        value={memory}
                        onChange={(event) => setMemory(event.target.value)}
                      />
                    </label>
                    <div className="text-sm">
                      <label className="mb-1 block" htmlFor="computer-packages">
                        {t("packages")}
                      </label>
                      <select
                        id="computer-packages"
                        className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
                        value={packages}
                        onChange={(event) =>
                          setPackages(event.target.value as "default" | "allow" | "block")
                        }
                      >
                        <option value="default">{t("packageDefault")}</option>
                        <option value="allow">{t("packageAllow")}</option>
                        <option value="block">{t("packageBlock")}</option>
                      </select>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setCpu("");
                        setMemory("");
                        setPackages("default");
                      }}
                    >
                      {t("resourceReset")}
                    </Button>
                  </>
                ) : cpu || memory || packages !== "default" ? (
                  <div className="space-y-2 text-sm">
                    <p>{t("advancedIncluded")}</p>
                    <Button type="button" variant="outline" onClick={() => choose(true)}>
                      {t("reviewAdvanced")}
                    </Button>
                  </div>
                ) : null}
                {formError ? (
                  <p role="alert" className="text-sm text-[var(--destructive)]">
                    {formError}
                  </p>
                ) : null}
                <Button
                  type="submit"
                  disabled={
                    !formValid || writesHeld || Boolean(templateError) || templates === null
                  }
                >
                  {t(pending === "save" ? "saving" : "save")}
                </Button>
              </fieldset>
              {uncertain ? (
                <p className="text-xs text-[var(--muted-foreground)]">{t("checkBeforeRetry")}</p>
              ) : null}
            </form>
          ) : null
        }
      >
        <p className="mb-4 text-sm leading-relaxed text-[var(--muted-foreground)]">
          {t("templateHelp")}
        </p>
        <DetailState
          loading={reading.templates && templates === null && manage !== false}
          error={templateError}
          onRetry={retry}
        />
        {templates && manage ? (
          <section aria-label={t("listTitle")}>
            {reading.templates || templateError ? (
              <p className="mb-4 text-sm text-[var(--muted-foreground)]" role="status">
                {t("retainedTemplates")}
              </p>
            ) : null}
            {templates.length ? (
              <>
                <label className="mb-3 block text-sm" htmlFor="template-search">
                  {t("findTemplate")}
                  <Input
                    ref={templateSearch}
                    className="mt-1"
                    id="template-search"
                    type="search"
                    value={templateQuery}
                    onChange={(event) => setTemplateQuery(event.target.value)}
                  />
                </label>
                {templateQuery ? (
                  <Button
                    className="mb-3"
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setTemplateQuery("");
                      templateSearch.current?.focus();
                    }}
                  >
                    {t("clearFilters")}
                  </Button>
                ) : null}
                {!matchingTemplates.length ? <EmptyState title={t("noMatches")} compact /> : null}
                <ul className="row-list">
                  {templatePage.rows.map((row) => (
                    <li className="min-w-0 p-4" key={row.id}>
                      <h3 className="break-words font-medium">{row.name}</h3>
                      <p className="mt-1 break-words text-sm text-[var(--muted-foreground)]">
                        {row.slug} · {formatCount(row.cpuMillis)} {t("cpuUnit")} ·{" "}
                        {formatCount(row.memoryMb)} {t("memoryUnit")}
                      </p>
                      <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                        {t(row.allowPackages ? "packagesAllowed" : "packagesOff")}
                      </p>
                    </li>
                  ))}
                </ul>
                <ListPagination {...templatePage} label={t("listTitle")} />
              </>
            ) : (
              <EmptyState title={t("empty")} compact />
            )}
          </section>
        ) : null}
        <section
          aria-labelledby="computer-instances"
          className="mt-8 border-t border-[var(--border)] pt-6"
        >
          <h2 id="computer-instances" className="mb-3 text-sm font-semibold">
            {t("live")}
          </h2>
          <p className="mb-4 text-sm leading-relaxed text-[var(--muted-foreground)]">
            {t("instanceHelp")}
          </p>
          <ActionStatus
            busy={pending === "terminate"}
            busyLabel={t("stopping")}
            notice={lastAction === "terminate" ? notice : ""}
          />
          {lastAction === "terminate" && !selected ? actionFeedback : null}
          <DetailState
            loading={reading.instances && live === null && manage !== false}
            error={instanceError}
            onRetry={retry}
          />
          {live && manage ? (
            <>
              {reading.instances || instanceError ? (
                <p className="mb-4 text-sm text-[var(--muted-foreground)]" role="status">
                  {t("retainedInstances")}
                </p>
              ) : null}
              {live.length ? (
                <>
                  <div className="mb-3 grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                    <label className="min-w-0 text-sm" htmlFor="instance-search">
                      {t("findComputer")}
                      <Input
                        ref={instanceSearch}
                        className="mt-1"
                        id="instance-search"
                        type="search"
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                      />
                    </label>
                    <div className="min-w-0 text-sm">
                      <label className="mb-1 block" htmlFor="instance-status">
                        {t("status")}
                      </label>
                      <select
                        className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3"
                        id="instance-status"
                        value={status}
                        onChange={(event) => setStatus(event.target.value)}
                      >
                        <option value="">{t("allStatuses")}</option>
                        {statuses.map((value) => (
                          <option key={value} value={value}>
                            {value}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  {query || status ? (
                    <Button
                      className="mb-3"
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setQuery("");
                        setStatus("");
                        instanceSearch.current?.focus();
                      }}
                    >
                      {t("clearFilters")}
                    </Button>
                  ) : null}
                  {!matching.length ? <EmptyState title={t("noMatches")} compact /> : null}
                  <ul className="row-list">
                    {instancePage.rows.map((row) => (
                      <li className="min-w-0 p-4" key={row.id}>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="min-w-0 break-all font-medium">
                            {String(row.templateSlug || row.scopeKey || row.id)}
                          </p>
                          <Badge tone={statusTone(row.status)}>{row.status}</Badge>
                        </div>
                        <p className="mt-1 break-all font-mono text-xs text-[var(--muted-foreground)]">
                          {t("instanceId")}: {row.id}
                        </p>
                        {text(row.error) ? <RecordedError id={row.id} error={row.error} /> : null}
                        {!ended(row) && canStop ? (
                          <Button
                            className="mt-3"
                            disabled={writesHeld || Boolean(instanceError)}
                            aria-label={t("stopNamed", { id: row.id })}
                            type="button"
                            variant="outline"
                            onClick={(event) => {
                              trigger.current = event.currentTarget;
                              setSelected(row);
                            }}
                          >
                            {t("stopConfirm")}
                          </Button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                  <ListPagination {...instancePage} label={t("live")} />
                </>
              ) : (
                <EmptyState title={t("emptyLive")} compact />
              )}
              {!canStop ? (
                <p className="mt-3 text-xs text-[var(--muted-foreground)]">{t("stopDenied")}</p>
              ) : null}
            </>
          ) : null}
        </section>
      </ManagementLayout>
      <Dialog
        open={Boolean(selected)}
        onOpenChange={(open) => {
          if (!open && !operation.current) setSelected(null);
        }}
      >
        <DialogContent
          title={t("stopTitle")}
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            cancel.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (trigger.current?.isConnected && !trigger.current.disabled) trigger.current.focus();
            else refreshButton.current?.focus();
          }}
        >
          <p className="mt-3 text-sm">{t("stopHelp")}</p>
          {selected?.templateSlug || selected?.scopeKey ? (
            <p className="mt-3 break-words font-medium">
              {String(selected.templateSlug || selected.scopeKey)}
            </p>
          ) : null}
          <p className="my-3 break-all font-mono text-xs">{selected?.id}</p>
          <ActionStatus busy={pending === "terminate"} busyLabel={t("stopping")} />
          {!freshSelected || ended(freshSelected) ? (
            <p className="mb-3 text-sm">{t("stopUnavailable")}</p>
          ) : null}
          {actionFeedback}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <button
                ref={cancel}
                type="button"
                disabled={Boolean(pending)}
                onClick={() => setSelected(null)}
              >
                {t("cancel")}
              </button>
            </Button>
            <Button
              type="button"
              disabled={
                writesHeld ||
                !canStop ||
                Boolean(instanceError) ||
                !freshSelected ||
                ended(freshSelected)
              }
              onClick={() => void terminate()}
            >
              {t(pending === "terminate" ? "stopping" : "stopConfirm")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}

function RecordedError({ id, error }: { id: string; error: string }) {
  const t = useTranslations("computers");
  const [open, setOpen] = useState(false);
  return (
    <details className="mt-3 text-xs" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="cursor-pointer font-medium text-[var(--muted-foreground)] underline underline-offset-4">
        {t("recordedError")}
      </summary>
      {open ? (
        <TableScroll
          label={t("errorDetails", { id })}
          className="mt-2 max-h-48 rounded-lg border border-[var(--border)] p-3"
        >
          <p className="whitespace-pre-wrap break-words">{error}</p>
        </TableScroll>
      ) : null}
    </details>
  );
}
