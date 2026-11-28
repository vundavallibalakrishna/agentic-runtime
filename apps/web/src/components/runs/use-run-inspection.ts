"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, type Session } from "@/lib/api";
import { loadSession } from "@/lib/session";

import { liveStatuses } from "./format";
export type Run = {
  id: string;
  userId?: string;
  agentId?: string;
  answeredModel?: string;
  status?: string;
  trigger?: string;
  resultSummary?: string;
  agentName?: string;
  agentSlug?: string;
  traceUrl?: string;
  langfuseUrl?: string;
  startedAt?: string | null;
  endedAt?: string | null;
  usage?: { steps?: number; wallClockMs?: number; costMicros?: number; tokensOut?: number };
  budget?: { maxSteps?: number; maxCostMicros?: number };
  error?: { code?: string; message?: string };
};
export type Step = { id?: string; kind?: string; detail?: { agent?: string } };
export type Tool = { id?: string; qualifiedName?: string; status?: string; [key: string]: unknown };

type Section = "steps" | "tools" | "children";
/** Shared snapshots for chat and the full inspector. Errors never masquerade as empty activity. */
export function useRunInspection(
  runId: string,
  {
    includeChildren = false,
    includeIdentity = false,
    allowPolling = true,
    pollInterval = 2000,
  }: {
    includeChildren?: boolean;
    includeIdentity?: boolean;
    allowPolling?: boolean;
    pollInterval?: number;
  } = {},
) {
  const t = useTranslations("runs");
  const [run, setRun] = useState<Run | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [children, setChildren] = useState<Run[]>([]);
  const [steps, setSteps] = useState<Step[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sectionErrors, setSectionErrors] = useState({ children: "", steps: "", tools: "" });
  const commands = useRef<{ refresh: () => void; pause: () => void } | null>(null);
  const previousId = useRef("");
  useEffect(() => {
    let disposed = false;
    let paused = false;
    let controller: AbortController | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    if (previousId.current !== runId) {
      previousId.current = runId;
      setRun(null);
      setSteps([]);
      setTools([]);
      setChildren([]);
      setSession(null);
      setSectionErrors({ children: "", steps: "", tools: "" });
    }
    function stop() {
      controller?.abort();
      if (timer) clearTimeout(timer);
    }
    async function read(quiet = false) {
      if (disposed || paused) return;
      stop();
      const current = new AbortController();
      controller = current;
      const request = { signal: current.signal };
      const valid = () => !disposed && !current.signal.aborted && !paused;
      if (!quiet) setLoading(true);
      try {
        const [saved, identity] = await Promise.all([
          api<Run>(`/api/v1/runs/${runId}`, request),
          includeIdentity ? loadSession() : undefined,
        ]);
        if (!valid()) return;
        setRun(saved);
        if (identity) setSession(identity);
        setError("");
        async function collection<T>(section: Section, setter: (rows: T[]) => void) {
          try {
            const page = await api<{ items: T[] }>(
              `/api/v1/runs/${runId}/${section === "tools" ? "tool-calls" : section}`,
              request,
            );
            if (!valid()) return false;
            setter(page.items ?? []);
            setSectionErrors((errors) => ({ ...errors, [section]: "" }));
            return true;
          } catch (caught) {
            if (valid())
              setSectionErrors((errors) => ({
                ...errors,
                [section]: caught instanceof Error ? caught.message : t("error"),
              }));
            return false;
          }
        }
        const ready = await Promise.all([
          collection<Step>("steps", setSteps),
          collection<Tool>("tools", setTools),
          includeChildren ? collection<Run>("children", setChildren) : undefined,
        ]);
        if (!valid()) return;
        setLoading(false);
        if (
          allowPolling &&
          ready.every((value) => value !== false) &&
          liveStatuses.includes(saved.status ?? "")
        )
          timer = setTimeout(() => void read(true), pollInterval);
      } catch (caught) {
        if (valid()) {
          setError(caught instanceof Error ? caught.message : t("error"));
          setLoading(false);
        }
      }
    }
    commands.current = {
      refresh: () => {
        paused = false;
        void read();
      },
      pause: () => {
        paused = true;
        stop();
        setLoading(false);
      },
    };
    void read();
    return () => {
      disposed = true;
      stop();
      commands.current = null;
    };
  }, [runId, includeChildren, includeIdentity, allowPolling, pollInterval, t]);
  const refresh = useCallback(() => commands.current?.refresh(), []);
  const pause = useCallback(() => commands.current?.pause(), []);
  return {
    run,
    setRun,
    session,
    children,
    steps,
    tools,
    loading,
    error,
    sectionErrors,
    refresh,
    pause,
  };
}
