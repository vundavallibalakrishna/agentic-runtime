"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { type Field, localIso, RecordForm } from "@/components/grc/record-form";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";

type Row = { id: string; title: string };

const tiers = ["critical", "high", "medium", "low"] as const;
const scores = ["1", "2", "3", "4", "5"];

export function WorkflowForms({
  section,
  rows,
  onChanged,
  onNotice,
}: {
  section:
    | "questionnaires"
    | "vendors"
    | "policies"
    | "risks"
    | "regulatory"
    | "incidents"
    | "exceptions"
    | "ethics";
  rows: Row[];
  onChanged: () => Promise<void>;
  onNotice: (message: string) => void;
}) {
  const t = useTranslations("grc");
  const required = (label: string) => t("fieldRequired", { label });

  async function send(path: string, body: unknown, method = "POST") {
    try {
      await api(path, { method, body: JSON.stringify(body) });
    } catch (caught) {
      throw new Error(caught instanceof Error ? caught.message : t("error"));
    }
    onNotice(t("saved"));
    await onChanged();
  }

  if (section === "questionnaires") {
    return (
      <div className="space-y-4">
        <RecordForm
          fields={[
            { name: "question", label: t("question"), required: true },
            { name: "answer", label: t("answer"), type: "textarea" },
          ]}
          hint={t("answerHint")}
          id="grc-answer"
          onSubmit={(values) =>
            send("/api/v1/ext/grc/answer-library", {
              question: values.question,
              answerMd: values.answer || "",
            })
          }
          requiredMessage={required}
          submitLabel={t("addAnswer")}
          title={t("newAnswer")}
        />
        <QuestionUpload onChanged={onChanged} onNotice={onNotice} requiredMessage={required} />
        <EditSelect
          label={t("editAnswer")}
          onSubmit={(id, values) =>
            send(
              `/api/v1/ext/grc/answer-library/${id}`,
              {
                question: values.question,
                answerMd: values.answer || "",
              },
              "PATCH",
            )
          }
          rows={rows}
          titleField={t("question")}
          bodyField={t("answer")}
        />
      </div>
    );
  }

  if (section === "vendors") {
    return (
      <div className="space-y-4">
        <RecordForm
          fields={[
            { name: "name", label: t("vendorName"), required: true },
            {
              name: "tier",
              label: t("tier"),
              type: "select",
              options: tiers.map((tier) => ({ value: tier, label: t(tier) })),
            },
          ]}
          id="grc-vendor"
          onSubmit={(values) =>
            send("/api/v1/ext/grc/vendors", {
              name: values.name,
              ...(values.tier ? { tier: values.tier } : {}),
            })
          }
          requiredMessage={required}
          submitLabel={t("addVendor")}
          title={t("newVendor")}
        />
        <RecordForm
          fields={[
            {
              name: "vendorId",
              label: t("vendor"),
              required: true,
              type: "select",
              options: rows.map((row) => ({ value: row.id, label: row.title })),
            },
            {
              name: "kind",
              label: t("assessmentKind"),
              required: true,
              type: "select",
              options: [
                { value: "intake", label: t("intake") },
                { value: "questionnaire", label: t("questionnaireKind") },
                { value: "document_review", label: t("documentReview") },
              ],
            },
          ]}
          hint={rows.length === 0 ? t("vendorFirst") : t("assessmentHint")}
          id="grc-assessment"
          onSubmit={async (values) => {
            await send(`/api/v1/ext/grc/vendors/${values.vendorId}/assessments`, {
              kind: values.kind,
            });
          }}
          requiredMessage={required}
          submitLabel={t("addAssessment")}
          title={t("newAssessment")}
        />
        <EditSelect
          label={t("editVendor")}
          onSubmit={(id, values) =>
            send(
              `/api/v1/ext/grc/vendors/${id}`,
              { name: values.question, ...(values.answer ? { tier: values.answer } : {}) },
              "PATCH",
            )
          }
          rows={rows}
          titleField={t("vendorName")}
          bodyField={t("tier")}
        />
      </div>
    );
  }

  if (section === "policies") {
    return (
      <div className="space-y-4">
        <RecordForm
          fields={[
            { name: "key", label: t("policyKey"), required: true, hint: t("policyKeyHint") },
            { name: "title", label: t("policyTitle"), required: true },
          ]}
          id="grc-policy"
          onSubmit={(values) =>
            send("/api/v1/ext/grc/policies", { key: values.key, title: values.title })
          }
          requiredMessage={required}
          submitLabel={t("addPolicy")}
          title={t("newPolicy")}
        />
        <RecordForm
          fields={[
            {
              name: "policyId",
              label: t("policy"),
              required: true,
              type: "select",
              options: rows.map((row) => ({ value: row.id, label: row.title })),
            },
            { name: "body", label: t("policyBody"), required: true, type: "textarea" },
            { name: "note", label: t("changeNote") },
          ]}
          hint={t("draftHint")}
          id="grc-policy-version"
          onSubmit={(values) =>
            send(`/api/v1/ext/grc/policies/${values.policyId}/versions`, {
              bodyMd: values.body,
              changeNote: values.note || "",
            })
          }
          requiredMessage={required}
          submitLabel={t("saveDraft")}
          title={t("newDraft")}
        />
        <PolicyReview onChanged={onChanged} onNotice={onNotice} rows={rows} />
      </div>
    );
  }

  if (section === "risks") {
    const scoreOptions = scores.map((score) => ({ value: score, label: score }));
    return (
      <div className="space-y-4">
        <RecordForm
          fields={[
            { name: "title", label: t("riskTitle"), required: true },
            { name: "statement", label: t("riskStatement"), required: true, type: "textarea" },
            {
              name: "likelihood",
              label: t("likelihood"),
              required: true,
              type: "select",
              options: scoreOptions,
            },
            {
              name: "impact",
              label: t("impact"),
              required: true,
              type: "select",
              options: scoreOptions,
            },
          ]}
          id="grc-risk"
          onSubmit={(values) =>
            send("/api/v1/ext/grc/risks", {
              title: values.title,
              statement: values.statement,
              likelihood: Number(values.likelihood),
              impact: Number(values.impact),
            })
          }
          requiredMessage={required}
          submitLabel={t("addRisk")}
          title={t("newRisk")}
        />
        <EditSelect
          label={t("editRisk")}
          onSubmit={(id, values) =>
            send(
              `/api/v1/ext/grc/risks/${id}`,
              { title: values.question, statement: values.answer },
              "PATCH",
            )
          }
          rows={rows}
          titleField={t("riskTitle")}
          bodyField={t("riskStatement")}
        />
      </div>
    );
  }

  if (section === "regulatory") {
    return (
      <div className="space-y-4">
        <RecordForm
          fields={[
            { name: "regulator", label: t("regulator"), required: true },
            { name: "url", label: t("feedUrl"), required: true, hint: t("feedUrlHint") },
          ]}
          id="grc-feed"
          onSubmit={(values) =>
            send("/api/v1/ext/grc/regulator-feeds", {
              regulator: values.regulator,
              url: values.url,
            })
          }
          requiredMessage={required}
          submitLabel={t("addFeed")}
          title={t("newFeed")}
        />
        <RecordForm
          fields={[
            { name: "regulator", label: t("regulator"), required: true },
            { name: "citation", label: t("citation"), required: true },
            { name: "statement", label: t("obligation"), required: true, type: "textarea" },
          ]}
          id="grc-obligation"
          onSubmit={(values) =>
            send("/api/v1/ext/grc/obligations", {
              regulator: values.regulator,
              citation: values.citation,
              statement: values.statement,
            })
          }
          requiredMessage={required}
          submitLabel={t("addObligation")}
          title={t("newObligation")}
        />
      </div>
    );
  }

  if (section === "incidents") {
    return (
      <div className="space-y-4">
        <RecordForm
          fields={[
            { name: "title", label: t("incidentTitle"), required: true },
            { name: "summary", label: t("summary"), type: "textarea" },
            { name: "detectedAt", label: t("detectedAt"), required: true, type: "datetime" },
          ]}
          id="grc-incident"
          onSubmit={(values) =>
            send("/api/v1/ext/grc/incidents", {
              title: values.title,
              summary: values.summary || "",
              detectedAt: localIso(values.detectedAt),
            })
          }
          requiredMessage={required}
          submitLabel={t("addIncident")}
          title={t("newIncident")}
        />
        <RecordForm
          fields={[
            {
              name: "incidentId",
              label: t("incident"),
              required: true,
              type: "select",
              options: rows.map((row) => ({ value: row.id, label: row.title })),
            },
            {
              name: "regime",
              label: t("regime"),
              required: true,
              type: "select",
              options: [
                { value: "cert_in", label: t("certIn") },
                { value: "dpdp", label: t("dpdp") },
                { value: "gdpr", label: t("gdpr") },
              ],
            },
          ]}
          id="grc-clock"
          onSubmit={(values) =>
            send(`/api/v1/ext/grc/incidents/${values.incidentId}:start-clock`, {
              regime: values.regime,
            })
          }
          requiredMessage={required}
          submitLabel={t("startClock")}
          title={t("newClock")}
        />
        <RecordForm
          fields={[
            {
              name: "incidentId",
              label: t("incident"),
              required: true,
              type: "select",
              options: rows.map((row) => ({ value: row.id, label: row.title })),
            },
          ]}
          hint={t("closeIncidentHint")}
          id="grc-close-incident"
          onSubmit={(values) =>
            send(`/api/v1/ext/grc/incidents/${values.incidentId}`, { status: "closed" }, "PATCH")
          }
          requiredMessage={required}
          submitLabel={t("closeIncident")}
          title={t("closeIncident")}
        />
      </div>
    );
  }

  if (section === "exceptions") {
    return <ExceptionForm onSend={send} requiredMessage={required} />;
  }

  return (
    <RecordForm
      fields={[{ name: "title", label: t("caseTitle"), required: true }]}
      hint={t("ethicsHint")}
      id="grc-ethics"
      onSubmit={(values) => send("/api/v1/ext/grc/ethics-cases", { title: values.title })}
      requiredMessage={required}
      submitLabel={t("addCase")}
      title={t("newCase")}
    />
  );
}

function QuestionUpload({
  onChanged,
  onNotice,
  requiredMessage,
}: {
  onChanged: () => Promise<void>;
  onNotice: (message: string) => void;
  requiredMessage: (label: string) => string;
}) {
  const t = useTranslations("grc");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function upload(file: File | undefined) {
    if (!file) {
      setError(requiredMessage(t("questionnaireFile")));
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.set("upload", file);
      body.set("mime_type", file.type || "text/plain");
      const uploaded = await api<{ id: string }>("/api/v1/files:upload", { method: "POST", body });
      await api("/api/v1/ext/grc/questionnaires:draft", {
        method: "POST",
        body: JSON.stringify({ fileId: uploaded.id }),
      });
      onNotice(t("drafted"));
      await onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
      onSubmit={(event) => {
        event.preventDefault();
        const input = event.currentTarget.elements.namedItem("questions");
        const file = input instanceof HTMLInputElement ? input.files?.[0] : undefined;
        void upload(file);
      }}
    >
      <h2 className="text-base font-semibold">{t("uploadQuestions")}</h2>
      <p className="text-sm text-[var(--muted-foreground)]">{t("uploadQuestionsHint")}</p>
      <label className="block text-sm" htmlFor="grc-questions-file">
        {t("questionnaireFile")}
        <input
          accept="text/plain,.txt,.csv"
          className="mt-1 block w-full text-sm"
          id="grc-questions-file"
          name="questions"
          type="file"
        />
      </label>
      {error ? (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {error}
        </p>
      ) : null}
      <Button disabled={busy} type="submit">
        {t("draftAnswers")}
      </Button>
    </form>
  );
}

function PolicyReview({
  rows,
  onChanged,
  onNotice,
}: {
  rows: Row[];
  onChanged: () => Promise<void>;
  onNotice: (message: string) => void;
}) {
  const t = useTranslations("grc");
  const [policyId, setPolicyId] = useState(rows[0]?.id ?? "");
  const [error, setError] = useState("");

  useEffect(() => {
    setPolicyId((current) => current || rows[0]?.id || "");
  }, [rows]);

  async function submitReview() {
    setError("");
    if (!policyId) {
      setError(t("fieldRequired", { label: t("policy") }));
      return;
    }
    try {
      await api(`/api/v1/ext/grc/policies/${policyId}:submit-review`, { method: "POST" });
      onNotice(t("reviewOpened"));
      await onChanged();
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : t("error");
      setError(message === "review_required" ? t("reviewRequired") : message);
    }
  }

  return (
    <form
      className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
      onSubmit={(event) => {
        event.preventDefault();
        void submitReview();
      }}
    >
      <h2 className="text-base font-semibold">{t("submitReview")}</h2>
      <p className="text-sm text-[var(--muted-foreground)]">{t("submitReviewHint")}</p>
      <label className="block text-sm" htmlFor="grc-review-policy">
        {t("policy")}
        <select
          className="mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm"
          id="grc-review-policy"
          onChange={(event) => setPolicyId(event.target.value)}
          value={policyId}
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
      <Button type="submit">{t("submitReview")}</Button>
    </form>
  );
}

function ExceptionForm({
  onSend,
  requiredMessage,
}: {
  onSend: (path: string, body: unknown) => Promise<void>;
  requiredMessage: (label: string) => string;
}) {
  const t = useTranslations("grc");
  const [controls, setControls] = useState<{ id: string; title: string }[]>([]);

  useEffect(() => {
    void api<{ items?: { id: string; key?: string; title?: string }[] }>("/api/v1/ext/grc/controls")
      .then((page) =>
        setControls(
          (page.items ?? []).map((item) => ({
            id: item.id,
            title: item.title || item.key || item.id,
          })),
        ),
      )
      .catch(() => setControls([]));
  }, []);

  const options = controls.map((item) => ({ value: item.id, label: item.title }));
  const fields: Field[] = [
    {
      name: "kind",
      label: t("exceptionKind"),
      required: true,
      type: "select",
      options: [
        { value: "exception", label: t("exception") },
        { value: "waiver", label: t("waiver") },
      ],
    },
    { name: "controlId", label: t("control"), required: true, type: "select", options },
    { name: "compensatingControlId", label: t("compensatingControl"), type: "select", options },
    { name: "rationale", label: t("rationale"), required: true, type: "textarea" },
    { name: "expiresAt", label: t("expiresAt"), required: true, type: "datetime" },
  ];

  return (
    <RecordForm
      fields={fields}
      hint={controls.length === 0 ? t("controlFirst") : t("exceptionsHint")}
      id="grc-exception"
      onSubmit={async (values) => {
        if (values.kind === "waiver" && !values.compensatingControlId) {
          throw new Error(requiredMessage(t("compensatingControl")));
        }
        await onSend("/api/v1/ext/grc/exceptions", {
          kind: values.kind,
          controlId: values.controlId,
          ...(values.compensatingControlId
            ? { compensatingControlId: values.compensatingControlId }
            : {}),
          rationale: values.rationale,
          expiresAt: localIso(values.expiresAt),
        });
      }}
      requiredMessage={requiredMessage}
      submitLabel={t("addException")}
      title={t("newException")}
    />
  );
}

function EditSelect({
  rows,
  label,
  titleField,
  bodyField,
  onSubmit,
}: {
  rows: Row[];
  label: string;
  titleField: string;
  bodyField: string;
  onSubmit: (id: string, values: Record<string, string>) => Promise<void>;
}) {
  const t = useTranslations("grc");
  if (rows.length === 0) return null;
  return (
    <RecordForm
      fields={[
        {
          name: "id",
          label,
          required: true,
          type: "select",
          options: rows.map((row) => ({ value: row.id, label: row.title })),
        },
        { name: "question", label: titleField, required: true },
        { name: "answer", label: bodyField, type: "textarea" },
      ]}
      id={`edit-${label}`}
      onSubmit={(values) => onSubmit(values.id ?? "", values)}
      requiredMessage={(name) => t("fieldRequired", { label: name })}
      submitLabel={t("saveChanges")}
      title={label}
    />
  );
}
