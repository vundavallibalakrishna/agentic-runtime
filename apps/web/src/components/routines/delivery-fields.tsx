"use client";

import { useTranslations } from "next-intl";

import { Input } from "@/components/ui/input";

/** Where a routine's result goes besides its owner's conversation. */
export type DeliveryChoice = { email: string; onlyReports: boolean };

export const NO_DELIVERY: DeliveryChoice = { email: "", onlyReports: false };

export type DeliveryTarget = {
  type: string;
  channel?: string | null;
  when?: string;
  config?: Record<string, string>;
};

/** The delivery list a new routine is created with. The conversation is always first. */
export function deliveryTargets(choice: DeliveryChoice): DeliveryTarget[] {
  const to = choice.email.trim();
  const targets: DeliveryTarget[] = [{ type: "conversation" }];
  if (to) {
    targets.push({
      type: "email",
      channel: to,
      when: choice.onlyReports ? "something_to_report" : "always",
    });
  }
  return targets;
}

export function DeliveryFields({
  idPrefix,
  onChange,
  value,
}: {
  idPrefix: string;
  onChange: (next: DeliveryChoice) => void;
  value: DeliveryChoice;
}) {
  const t = useTranslations("delivery");
  const hasEmail = value.email.trim().length > 0;
  return (
    <div className="mt-3 space-y-2">
      <label className="block text-sm" htmlFor={`${idPrefix}-delivery-email`}>
        {t("email")}
      </label>
      <Input
        className="max-w-md"
        id={`${idPrefix}-delivery-email`}
        onChange={(event) => onChange({ ...value, email: event.target.value })}
        placeholder={t("emailPlaceholder")}
        type="email"
        value={value.email}
      />
      <p className="text-xs text-[var(--muted-foreground)]">{t("emailHint")}</p>
      <label className="flex items-start gap-2 text-sm">
        <input
          checked={value.onlyReports}
          className="mt-1"
          disabled={!hasEmail}
          onChange={(event) => onChange({ ...value, onlyReports: event.target.checked })}
          type="checkbox"
        />
        <span>
          {t("onlyReports")}{" "}
          <span className="text-[var(--muted-foreground)]">{t("onlyReportsHint")}</span>
        </span>
      </label>
    </div>
  );
}

/** One line for each place a routine's result goes, for the detail screen. */
export function DeliveryList({ targets }: { targets: DeliveryTarget[] }) {
  const t = useTranslations("delivery");
  return (
    <ul className="space-y-1">
      {targets.map((target, index) => {
        const to = target.channel || target.config?.to || target.config?.url || "";
        const known = ["conversation", "email", "webhook"].includes(target.type);
        const label = known ? t(`to.${target.type}`, { to }) : target.type;
        return (
          // A routine's delivery list has no ids; its order is fixed, so the place is the key.
          // biome-ignore lint/suspicious/noArrayIndexKey: the list is not reordered
          <li key={`${target.type}-${index}`}>
            {label}
            {target.when === "something_to_report" ? (
              <span className="text-[var(--muted-foreground)]"> · {t("whenReports")}</span>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
