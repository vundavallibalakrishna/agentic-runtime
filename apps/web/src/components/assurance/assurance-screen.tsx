"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ActionStatus } from "@/components/common/detail-state";
import { EmptyState, ManagementLayout } from "@/components/common/management-layout";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";

type Evidence = {
  id: string;
  sourceSystem?: string;
  collectionMethod?: string;
  status?: string;
  contentSha256?: string;
};
type Hold = { id: string; matter?: string; status?: string; memberCount?: number };
type Schedule = {
  recordClass?: string;
  retentionDays?: number;
  effectiveDays?: number;
  disposition?: string;
};
type Guest = { id: string; email?: string; displayName?: string; status?: string };
type Binder = { id: string; title?: string; status?: string };
type Card = { id: string; purpose?: string; oversightMode?: string; riskTier?: string };
type Officer = { id: string; displayName?: string };

export function AssuranceScreen() {
  const t = useTranslations("assurance");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [holds, setHolds] = useState<Hold[]>([]);
  const [officers, setOfficers] = useState<Officer[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [guests, setGuests] = useState<Guest[]>([]);
  const [binders, setBinders] = useState<Binder[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [matter, setMatter] = useState("");
  const [approver, setApprover] = useState("");
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [items, holdPage, schedulePage, guestPage, binderPage, cardPage] = await Promise.all([
        api<{ items: Evidence[] }>("/api/v1/evidence"),
        api<{ items: Hold[]; officers?: Officer[] }>("/api/v1/legal-holds"),
        api<{ items: Schedule[] }>("/api/v1/retention-schedules"),
        api<{ items: Guest[] }>("/api/v1/guests"),
        api<{ items: Binder[] }>("/api/v1/binders"),
        api<{ items: Card[] }>("/api/v1/agent-cards"),
      ]);
      setEvidence(items.items ?? []);
      setHolds(holdPage.items ?? []);
      setOfficers(holdPage.officers ?? []);
      setSchedules(schedulePage.items ?? []);
      setGuests(guestPage.items ?? []);
      setBinders(binderPage.items ?? []);
      setCards(cardPage.items ?? []);
      setApprover((current) => current || holdPage.officers?.[0]?.id || "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function capture() {
    setBusy(true);
    setNotice("");
    try {
      await api("/api/v1/evidence", {
        method: "POST",
        body: JSON.stringify({
          text: note || "Desk note",
          mediaType: "text/plain",
          sourceSystem: "desk",
          collectionMethod: "upload",
          provenance: { note },
        }),
      });
      setNote("");
      setNotice(t("captured"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function createHold() {
    setBusy(true);
    setError("");
    try {
      await api("/api/v1/legal-holds", {
        method: "POST",
        body: JSON.stringify({
          matter,
          custodians: [],
          scopeQuery: { conversationIds: [] },
          approverUserId: approver,
        }),
      });
      setMatter("");
      setNotice(t("holdSaved"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function invite() {
    setBusy(true);
    setError("");
    try {
      await api("/api/v1/guests", {
        method: "POST",
        body: JSON.stringify({
          email,
          displayName: email,
          kind: "external",
          authMethod: "magic_link_totp",
          grants: [{ portal: "records", scope: { evidenceIds: [] }, watermark: true }],
        }),
      });
      setEmail("");
      setNotice(t("invited"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function exportMine() {
    setBusy(true);
    try {
      await api("/api/v1/me/export");
      setNotice(t("exportReady"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title={t("title")}
        body={t("body")}
        actions={
          <Button onClick={() => void exportMine()} variant="outline">
            {t("exportMine")}
          </Button>
        }
      />
      <ActionStatus busy={busy} notice={notice} />
      {error ? <p className="mb-4 text-sm text-[var(--destructive)]">{error}</p> : null}
      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (
        <Tabs defaultValue="evidence">
          <TabsList>
            <TabsTrigger value="evidence">{t("evidence")}</TabsTrigger>
            <TabsTrigger value="holds">{t("holds")}</TabsTrigger>
            <TabsTrigger value="retention">{t("retention")}</TabsTrigger>
            <TabsTrigger value="register">{t("register")}</TabsTrigger>
            <TabsTrigger value="guests">{t("guests")}</TabsTrigger>
            <TabsTrigger value="binders">{t("binders")}</TabsTrigger>
          </TabsList>
          <TabsContent value="evidence">
            <ManagementLayout
              formTitle={t("captureTitle")}
              form={
                <form
                  className="space-y-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void capture();
                  }}
                >
                  <label className="block text-sm" htmlFor="note">
                    {t("note")}
                  </label>
                  <Input id="note" value={note} onChange={(event) => setNote(event.target.value)} />
                  <Button disabled={busy} type="submit">
                    {t("capture")}
                  </Button>
                </form>
              }
            >
              {evidence.length === 0 ? (
                <EmptyState title={t("evidenceEmpty")}>{t("evidenceEmptyBody")}</EmptyState>
              ) : (
                <ul className="divide-y divide-[var(--border)]">
                  {evidence.map((item) => (
                    <li className="py-3" key={item.id}>
                      <p className="font-medium">{item.sourceSystem}</p>
                      <p className="text-sm text-[var(--muted-foreground)]">
                        {item.collectionMethod} · {item.status}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </ManagementLayout>
          </TabsContent>
          <TabsContent value="holds">
            <ManagementLayout
              formTitle={t("holdTitle")}
              form={
                <form
                  className="space-y-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void createHold();
                  }}
                >
                  <label className="block text-sm" htmlFor="matter">
                    {t("matter")}
                  </label>
                  <Input
                    id="matter"
                    value={matter}
                    onChange={(event) => setMatter(event.target.value)}
                    required
                  />
                  <label className="block text-sm" htmlFor="approver">
                    {t("approver")}
                  </label>
                  <select
                    className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
                    id="approver"
                    onChange={(event) => setApprover(event.target.value)}
                    value={approver}
                  >
                    {officers.map((officer) => (
                      <option key={officer.id} value={officer.id}>
                        {officer.displayName}
                      </option>
                    ))}
                  </select>
                  <p className="text-sm text-[var(--muted-foreground)]">{t("twoPerson")}</p>
                  <Button disabled={busy || !approver} type="submit">
                    {t("createHold")}
                  </Button>
                </form>
              }
            >
              {holds.length === 0 ? (
                <EmptyState title={t("holdsEmpty")} />
              ) : (
                <ul className="divide-y divide-[var(--border)]">
                  {holds.map((hold) => (
                    <li className="py-3" key={hold.id}>
                      <p className="font-medium">{hold.matter}</p>
                      <p className="text-sm text-[var(--muted-foreground)]">{hold.status}</p>
                    </li>
                  ))}
                </ul>
              )}
            </ManagementLayout>
          </TabsContent>
          <TabsContent value="retention">
            {schedules.length === 0 ? (
              <EmptyState title={t("retentionEmpty")} />
            ) : (
              <ul className="divide-y divide-[var(--border)]">
                {schedules.map((row) => (
                  <li className="flex justify-between py-3 text-sm" key={row.recordClass}>
                    <span>{row.recordClass}</span>
                    <span className="text-[var(--muted-foreground)]">
                      {row.effectiveDays} {t("days")} · {row.disposition}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>
          <TabsContent value="register">
            {cards.length === 0 ? (
              <EmptyState title={t("registerEmpty")} />
            ) : (
              <ul className="divide-y divide-[var(--border)]">
                {cards.map((card) => (
                  <li className="py-3" key={card.id}>
                    <p className="font-medium">{card.purpose}</p>
                    <p className="text-sm text-[var(--muted-foreground)]">
                      {card.oversightMode} · {card.riskTier}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>
          <TabsContent value="guests">
            <ManagementLayout
              formTitle={t("inviteTitle")}
              form={
                <form
                  className="space-y-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void invite();
                  }}
                >
                  <label className="block text-sm" htmlFor="guest-email">
                    {t("email")}
                  </label>
                  <Input
                    id="guest-email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                  />
                  <Button disabled={busy} type="submit">
                    {t("invite")}
                  </Button>
                </form>
              }
            >
              {guests.length === 0 ? (
                <EmptyState title={t("guestsEmpty")} />
              ) : (
                <ul className="divide-y divide-[var(--border)]">
                  {guests.map((guest) => (
                    <li className="py-3" key={guest.id}>
                      <p className="font-medium">{guest.displayName}</p>
                      <p className="text-sm text-[var(--muted-foreground)]">
                        {guest.email} · {guest.status}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </ManagementLayout>
          </TabsContent>
          <TabsContent value="binders">
            {binders.length === 0 ? (
              <EmptyState title={t("bindersEmpty")} />
            ) : (
              <ul className="divide-y divide-[var(--border)]">
                {binders.map((binder) => (
                  <li className="py-3" key={binder.id}>
                    <p className="font-medium">{binder.title}</p>
                    <p className="text-sm text-[var(--muted-foreground)]">{binder.status}</p>
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>
        </Tabs>
      )}
    </AppShell>
  );
}
