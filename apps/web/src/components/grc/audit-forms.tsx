"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { localIso, RecordForm } from "@/components/grc/record-form";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

type Row = { id: string; title: string };
type AuditSection = "requests" | "reviews" | "reports" | "inspections" | "privacy" | "resilience";

const templates = ["soa", "soc2_binder", "cscrf", "dpdp_breach", "board_pack"] as const;

export function AuditForms({
  section,
  rows,
  onChanged,
  onNotice,
  onRender,
}: {
  section: AuditSection;
  rows: Row[];
  onChanged: () => Promise<void>;
  onNotice: (message: string) => void;
  onRender: (template: (typeof templates)[number]) => Promise<void>;
}) {
  const t = useTranslations("grc");
  const required = (label: string) => t("fieldRequired", { label });
  const evidence = useEvidence(section === "privacy" || section === "resilience");

  async function send(path: string, body: unknown, method = "POST") {
    try {
      await api(path, { method, body: JSON.stringify(body) });
    } catch (caught) {
      throw new Error(caught instanceof Error ? caught.message : t("error"));
    }
    onNotice(t("saved"));
    await onChanged();
  }

  if (section === "requests") {
    return (
      <div className="space-y-4">
        <RecordForm
          fields={[
            { name: "title", label: t("requestTitle"), required: true },
            { name: "dueAt", label: t("dueAt"), type: "datetime" },
          ]}
          id="grc-pbc"
          onSubmit={(values) =>
            send("/api/v1/ext/grc/pbc-requests", {
              title: values.title,
              ...(values.dueAt ? { dueAt: localIso(values.dueAt) } : {}),
            })
          }
          requiredMessage={required}
          submitLabel={t("addRequest")}
          title={t("newRequest")}
        />
        {rows.length > 0 ? (
          <RecordForm
            fields={[
              {
                name: "id",
                label: t("request"),
                required: true,
                type: "select",
                options: rows.map((row) => ({ value: row.id, label: row.title })),
              },
              {
                name: "status",
                label: t("status"),
                required: true,
                type: "select",
                options: ["open", "responded", "provided", "accepted"].map((status) => ({
                  value: status,
                  label: t(status),
                })),
              },
            ]}
            id="grc-pbc-status"
            onSubmit={(values) =>
              send(`/api/v1/ext/grc/pbc-requests/${values.id}`, { status: values.status }, "PATCH")
            }
            requiredMessage={required}
            submitLabel={t("saveChanges")}
            title={t("updateRequest")}
          />
        ) : null}
      </div>
    );
  }

  if (section === "reviews") {
    return (
      <div className="space-y-4">
        <RecordForm
          fields={[{ name: "title", label: t("campaignTitle"), required: true }]}
          hint={t("reviewsHint")}
          id="grc-campaign"
          onSubmit={(values) =>
            send("/api/v1/ext/grc/campaigns", { kind: "access_review", title: values.title })
          }
          requiredMessage={required}
          submitLabel={t("addCampaign")}
          title={t("newCampaign")}
        />
        <RecordForm
          fields={[
            { name: "name", label: t("ruleName"), required: true },
            { name: "entitlementA", label: t("entitlementA"), required: true },
            { name: "entitlementB", label: t("entitlementB"), required: true },
          ]}
          id="grc-sod"
          onSubmit={(values) =>
            send("/api/v1/ext/grc/sod-rules", {
              name: values.name,
              entitlementA: values.entitlementA,
              entitlementB: values.entitlementB,
            })
          }
          requiredMessage={required}
          submitLabel={t("addRule")}
          title={t("newRule")}
        />
        <SodDelete onChanged={onChanged} onNotice={onNotice} rows={rows} />
      </div>
    );
  }

  if (section === "reports") {
    return (
      <RecordForm
        fields={[
          {
            name: "template",
            label: t("template"),
            required: true,
            type: "select",
            options: templates.map((key) => ({ value: key, label: t(key) })),
          },
        ]}
        hint={t("reportsHint")}
        id="grc-report"
        onSubmit={async (values) => {
          await onRender(values.template as (typeof templates)[number]);
        }}
        requiredMessage={required}
        submitLabel={t("generateReport")}
        title={t("newReport")}
      />
    );
  }

  if (section === "inspections") {
    return (
      <RecordForm
        fields={[
          { name: "regulator", label: t("regulator"), required: true },
          { name: "startedOn", label: t("startedOn"), required: true, type: "date" },
        ]}
        hint={t("inspectionsHint")}
        id="grc-inspection"
        onSubmit={(values) =>
          send("/api/v1/ext/grc/inspections", {
            regulator: values.regulator,
            startedOn: localIso(values.startedOn),
          })
        }
        requiredMessage={required}
        submitLabel={t("openInspection")}
        title={t("newInspection")}
      />
    );
  }

  if (section === "privacy") {
    const evidenceField = {
      name: "evidenceItemId",
      label: t("evidenceItem"),
      required: true,
      type: "select" as const,
      options: evidence.map((item) => ({ value: item.id, label: item.title })),
    };
    return (
      <div className="space-y-4">
        <RecordForm
          fields={[
            {
              name: "requestType",
              label: t("requestType"),
              required: true,
              type: "select",
              options: ["access", "correction", "erasure", "portability"].map((kind) => ({
                value: kind,
                label: t(kind),
              })),
            },
            { name: "dueAt", label: t("dueAt"), required: true, type: "datetime" },
          ]}
          hint={t("privacyHint")}
          id="grc-dsar"
          onSubmit={(values) =>
            send("/api/v1/ext/grc/dsar-requests", {
              requestType: values.requestType,
              dueAt: localIso(values.dueAt),
            })
          }
          requiredMessage={required}
          submitLabel={t("addDsar")}
          title={t("newDsar")}
        />
        <RecordForm
          fields={[
            { name: "subjectRef", label: t("subjectRef"), required: true },
            { name: "purpose", label: t("purpose"), required: true },
            evidenceField,
          ]}
          hint={evidence.length === 0 ? t("evidenceFirst") : t("consentHint")}
          id="grc-consent"
          onSubmit={(values) =>
            send("/api/v1/ext/grc/consent-records", {
              subjectRef: values.subjectRef,
              purpose: values.purpose,
              evidenceItemId: values.evidenceItemId,
              state: "granted",
            })
          }
          requiredMessage={required}
          submitLabel={t("addConsent")}
          title={t("newConsent")}
        />
        <Fulfil rows={rows} onChanged={onChanged} onNotice={onNotice} />
      </div>
    );
  }

  return (
    <RecordForm
      fields={[
        {
          name: "kind",
          label: t("testKind"),
          required: true,
          type: "select",
          options: [
            { value: "bcp", label: t("bcp") },
            { value: "dr", label: t("dr") },
          ],
        },
        {
          name: "outcome",
          label: t("outcome"),
          required: true,
          type: "select",
          options: [
            { value: "pass", label: t("pass") },
            { value: "fail", label: t("fail") },
            { value: "partial", label: t("partial") },
          ],
        },
        { name: "testedOn", label: t("testedOn"), required: true, type: "date" },
        {
          name: "evidenceItemId",
          label: t("evidenceItem"),
          type: "select",
          options: evidence.map((item) => ({ value: item.id, label: item.title })),
          hint: t("failNeedsEvidence"),
        },
      ]}
      hint={t("resilienceHint")}
      id="grc-resilience"
      onSubmit={async (values) => {
        if (values.outcome === "fail" && !values.evidenceItemId) {
          throw new Error(required(t("evidenceItem")));
        }
        await send("/api/v1/ext/grc/resilience-tests", {
          kind: values.kind,
          outcome: values.outcome,
          testedOn: localIso(values.testedOn),
          ...(values.evidenceItemId ? { evidenceItemId: values.evidenceItemId } : {}),
        });
      }}
      requiredMessage={required}
      submitLabel={t("addTestRecord")}
      title={t("newResilience")}
    />
  );
}

function useEvidence(enabled: boolean) {
  const [items, setItems] = useState<{ id: string; title: string }[]>([]);
  useEffect(() => {
    if (!enabled) return;
    void api<{ items?: { id: string; sourceSystem?: string }[] }>("/api/v1/evidence")
      .then((page) =>
        setItems(
          (page.items ?? []).map((item) => ({
            id: item.id,
            title: item.sourceSystem || item.id,
          })),
        ),
      )
      .catch(() => setItems([]));
  }, [enabled]);
  return items;
}

function SodDelete({
  rows,
  onChanged,
  onNotice,
}: {
  rows: Row[];
  onChanged: () => Promise<void>;
  onNotice: (message: string) => void;
}) {
  const t = useTranslations("grc");
  const [ruleId, setRuleId] = useState("");
  const [error, setError] = useState("");
  if (rows.length === 0) return null;
  return (
    <form
      className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
      onSubmit={(event) => {
        event.preventDefault();
        void (async () => {
          if (!ruleId) {
            setError(t("fieldRequired", { label: t("ruleName") }));
            return;
          }
          setError("");
          try {
            await api(`/api/v1/ext/grc/sod-rules/${ruleId}`, { method: "DELETE" });
            onNotice(t("deleted"));
            await onChanged();
          } catch (caught) {
            setError(caught instanceof Error ? caught.message : t("error"));
          }
        })();
      }}
    >
      <h2 className="text-base font-semibold">{t("deleteRule")}</h2>
      <p className="text-sm text-[var(--muted-foreground)]">{t("deleteRuleHint")}</p>
      <label className="block text-sm" htmlFor="grc-delete-rule">
        {t("ruleName")}
        <select
          className="mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
          id="grc-delete-rule"
          onChange={(event) => setRuleId(event.target.value)}
          value={ruleId}
        >
          <option value="" />
          {rows.map((row) => (
            <option key={row.id} value={row.id}>
              {row.title}
            </option>
          ))}
        </select>
      </label>
      {error ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      <Button type="submit" variant="outline">
        {t("deleteRule")}
      </Button>
    </form>
  );
}

function Fulfil({
  rows,
  onChanged,
  onNotice,
}: {
  rows: Row[];
  onChanged: () => Promise<void>;
  onNotice: (message: string) => void;
}) {
  const t = useTranslations("grc");
  const [requestId, setRequestId] = useState("");
  const [error, setError] = useState("");
  if (rows.length === 0) return null;
  return (
    <form
      className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
      onSubmit={(event) => {
        event.preventDefault();
        void (async () => {
          if (!requestId) {
            setError(t("fieldRequired", { label: t("request") }));
            return;
          }
          setError("");
          try {
            await api(`/api/v1/ext/grc/dsar-requests/${requestId}:fulfil`, { method: "POST" });
            onNotice(t("fulfilled"));
            await onChanged();
          } catch (caught) {
            const message = caught instanceof Error ? caught.message : t("error");
            setError(message === "review_required" ? t("reviewRequired") : message);
          }
        })();
      }}
    >
      <h2 className="text-base font-semibold">{t("fulfilDsar")}</h2>
      <label className="block text-sm" htmlFor="grc-fulfil">
        {t("request")}
        <select
          className="mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
          id="grc-fulfil"
          onChange={(event) => setRequestId(event.target.value)}
          value={requestId}
        >
          <option value="" />
          {rows.map((row) => (
            <option key={row.id} value={row.id}>
              {row.title}
            </option>
          ))}
        </select>
      </label>
      {error ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      <Button type="submit" variant="outline">
        {t("fulfilDsar")}
      </Button>
    </form>
  );
}
