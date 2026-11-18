"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Session } from "@/lib/api";

type Queue = { id?: string; name?: string; subjectType?: string };

/**
 * Where an administrator chooses the review queue that accepted replies are signed in.
 * With no queue chosen, a reply stays labelled as AI-generated and nobody is offered
 * Accept. It is drawn only for someone who may change the organisation's settings.
 */
export function ReplyAcceptanceSettings() {
  const t = useTranslations("reviews");
  const [allowed, setAllowed] = useState(false);
  const [queues, setQueues] = useState<Queue[] | null>(null);
  const [chosen, setChosen] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const session = await api<Session>("/api/v1/auth/session");
      const held = session.permissions ?? [];
      if (!held.includes("tenant:manage") || !held.includes("reviews:read")) return;
      if (cancelled) return;
      setAllowed(true);
      const [tenant, listed] = await Promise.all([
        api<{ settings?: { approvals?: { replyReviewQueueId?: string | null } } }>(
          "/api/v1/tenant",
        ),
        api<{ items?: Queue[] }>("/api/v1/review-queues"),
      ]);
      if (cancelled) return;
      setChosen(tenant.settings?.approvals?.replyReviewQueueId ?? "");
      setQueues((listed.items ?? []).filter((queue) => queue.subjectType === "message"));
    }
    load().catch((caught: unknown) => {
      if (cancelled) return;
      setQueues([]);
      setError(caught instanceof Error ? caught.message : t("error"));
    });
    return () => {
      cancelled = true;
    };
  }, [t]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("/api/v1/tenant", {
        method: "PATCH",
        body: JSON.stringify({ settings: { approvals: { replyReviewQueueId: chosen || null } } }),
      });
      setNotice(t("replySaved"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  if (!allowed) return null;
  return (
    <section aria-labelledby="reply-acceptance" className="mt-10">
      <h2 className="text-sm font-semibold" id="reply-acceptance">
        {t("replyTitle")}
      </h2>
      <p className="mb-4 mt-1 max-w-2xl text-sm leading-relaxed text-[var(--muted-foreground)]">
        {t("replyBody")}
      </p>
      {queues === null ? (
        <div aria-busy="true">
          <span className="sr-only">{t("replyLoading")}</span>
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (
        <form
          className="grid gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
          onSubmit={(event) => void save(event)}
        >
          <div className="grid gap-1">
            <label className="text-sm font-medium" htmlFor="reply-queue">
              {t("replyQueue")}
            </label>
            <select
              className="w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
              id="reply-queue"
              onChange={(event) => setChosen(event.target.value)}
              value={chosen}
            >
              <option value="">{t("replyOff")}</option>
              {queues.map((queue) => (
                <option key={String(queue.id)} value={String(queue.id)}>
                  {String(queue.name ?? queue.id)}
                </option>
              ))}
            </select>
            {queues.length === 0 ? (
              <p className="text-xs leading-relaxed text-[var(--muted-foreground)]">
                {t("replyNoQueues")}
              </p>
            ) : null}
          </div>
          {error ? (
            <p className="text-sm text-[var(--destructive)]" role="alert">
              {error}
            </p>
          ) : null}
          {notice ? (
            <p className="text-sm" role="status">
              {notice}
            </p>
          ) : null}
          <Button className="justify-self-start" disabled={busy} type="submit">
            {t("replySave")}
          </Button>
        </form>
      )}
    </section>
  );
}
