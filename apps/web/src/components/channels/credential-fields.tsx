"use client";

import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/input";
import type { CredentialsBody } from "../../../../../packages/api-client/src/gen/types.gen";

export const channelKinds = ["slack", "teams", "email", "widget"] as const;
export type ChannelKind = (typeof channelKinds)[number];
export type CredentialValues = Partial<Record<keyof CredentialsBody, string>>;
type Field = {
  key: keyof CredentialsBody;
  type?: "password" | "number" | "email";
  optional?: boolean;
};
// Controls for the existing generated credential contract; values always come from the person.
const fields: Record<ChannelKind, Field[]> = {
  slack: [
    { key: "botToken", type: "password" },
    { key: "signingSecret", type: "password" },
    { key: "appToken", type: "password", optional: true },
  ],
  teams: [
    { key: "appId" },
    { key: "appPassword", type: "password" },
    { key: "tenantId", optional: true },
  ],
  email: [
    { key: "address", type: "email" },
    { key: "username" },
    { key: "password", type: "password" },
    { key: "imapHost" },
    { key: "imapPort", type: "number" },
    { key: "smtpHost" },
    { key: "smtpPort", type: "number" },
  ],
  widget: [{ key: "widgetSecret", type: "password" }],
};

export function credentialsValid(kind: ChannelKind, values: CredentialValues) {
  return fields[kind].every(({ key, optional, type }) => {
    const value = values[key] ?? "";
    if (!value.trim()) return Boolean(optional);
    return (
      type !== "number" ||
      (Number.isInteger(Number(value)) && Number(value) >= 1 && Number(value) <= 65535)
    );
  });
}
export function credentialBody(kind: ChannelKind, values: CredentialValues): CredentialsBody {
  return Object.fromEntries(
    fields[kind].flatMap(({ key, type }) => {
      const value = values[key] ?? "";
      if (!value.trim()) return [];
      return [
        [key, type === "number" ? Number(value) : type === "password" ? value : value.trim()],
      ];
    }),
  );
}
export function CredentialFields({
  kind,
  values,
  advanced,
  onChange,
}: {
  kind: ChannelKind;
  values: CredentialValues;
  advanced: boolean;
  onChange: (values: CredentialValues) => void;
}) {
  const t = useTranslations("channels");
  return (
    <fieldset className="grid min-w-0 gap-3">
      <legend className="mb-3 text-sm font-medium">{t("credentials")}</legend>
      <p className="text-xs text-[var(--muted-foreground)]">{t("credentialsHelp")}</p>
      {fields[kind]
        .filter(({ optional, key }) => !optional || advanced || values[key])
        .map(({ key, type = "text", optional }) => (
          <label key={key} className="text-sm" htmlFor={`channel-${key}`}>
            {t(`credentialLabels.${key}`)}
            {optional ? ` · ${t("optional")}` : ""}
            <Input
              className="mt-1"
              id={`channel-${key}`}
              type={type}
              required={!optional}
              min={type === "number" ? 1 : undefined}
              max={type === "number" ? 65535 : undefined}
              step={type === "number" ? 1 : undefined}
              autoComplete={type === "password" ? "new-password" : "off"}
              value={values[key] ?? ""}
              onChange={(event) => onChange({ ...values, [key]: event.target.value })}
            />
          </label>
        ))}
    </fieldset>
  );
}
