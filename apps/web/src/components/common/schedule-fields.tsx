"use client";

import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import { Input } from "@/components/ui/input";

type Repeat = "daily" | "weekdays" | "weekly" | "custom";

function readSchedule(cron: string) {
  const fields = cron.trim().split(/\s+/);
  const [minute, hour, date, month, day] = fields;
  const simple =
    fields.length === 5 &&
    /^\d+$/.test(minute ?? "") &&
    /^\d+$/.test(hour ?? "") &&
    Number(minute) < 60 &&
    Number(hour) < 24 &&
    date === "*" &&
    month === "*";
  const repeat: Repeat = !simple
    ? "custom"
    : day === "*"
      ? "daily"
      : day === "1-5"
        ? "weekdays"
        : /^[0-6]$/.test(day ?? "")
          ? "weekly"
          : "custom";
  return {
    repeat,
    time: simple ? `${hour?.padStart(2, "0")}:${minute?.padStart(2, "0")}` : "09:00",
    day: /^[0-6]$/.test(day ?? "") ? (day as string) : "1",
  };
}

/** One schedule editor for routine and schedule creation. The API still receives cron. */
export function ScheduleFields({
  cron,
  timezone,
  onCronChange,
  onTimezoneChange,
}: {
  cron: string;
  timezone: string;
  onCronChange: (value: string) => void;
  onTimezoneChange: (value: string) => void;
}) {
  const t = useTranslations("scheduleFields");
  const id = useId();
  const [repeat, setRepeat] = useState<Repeat>(() => readSchedule(cron).repeat);
  const [time, setTime] = useState(() => readSchedule(cron).time);
  const [day, setDay] = useState(() => readSchedule(cron).day);
  const [zones, setZones] = useState<string[]>([]);
  const selectClass =
    "mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm";

  function change(nextRepeat: Repeat, nextTime = time, nextDay = day) {
    setRepeat(nextRepeat);
    setTime(nextTime);
    setDay(nextDay);
    if (nextRepeat === "custom") return;
    const [hour, minute] = nextTime.split(":").map(Number);
    onCronChange(
      `${minute} ${hour} * * ${nextRepeat === "daily" ? "*" : nextRepeat === "weekdays" ? "1-5" : nextDay}`,
    );
  }

  return (
    <fieldset className="min-w-0">
      <legend className="mb-2 text-sm font-medium">{t("title")}</legend>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm" htmlFor={`${id}-repeat`}>
          {t("repeat")}
          <select
            className={selectClass}
            id={`${id}-repeat`}
            value={repeat}
            onChange={(event) => change(event.target.value as Repeat)}
          >
            {(["daily", "weekdays", "weekly", "custom"] as const).map((value) => (
              <option value={value} key={value}>
                {t(value)}
              </option>
            ))}
          </select>
        </label>
        {repeat === "weekly" ? (
          <label className="text-sm" htmlFor={`${id}-day`}>
            {t("day")}
            <select
              className={selectClass}
              id={`${id}-day`}
              value={day}
              onChange={(event) => change(repeat, time, event.target.value)}
            >
              {["0", "1", "2", "3", "4", "5", "6"].map((index) => (
                <option value={index} key={index}>
                  {t(`days.${index}`)}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {repeat !== "custom" ? (
          <label className="text-sm" htmlFor={`${id}-time`}>
            {t("time")}
            <Input
              className="mt-1"
              id={`${id}-time`}
              type="time"
              value={time}
              onChange={(event) => {
                if (/^\d{2}:\d{2}$/.test(event.target.value)) change(repeat, event.target.value);
              }}
            />
          </label>
        ) : (
          <label className="text-sm" htmlFor={`${id}-cron`}>
            {t("cron")}
            <Input
              className="mt-1 font-mono"
              id={`${id}-cron`}
              aria-label={t("cron")}
              value={cron}
              onChange={(event) => onCronChange(event.target.value)}
              aria-describedby={`${id}-cron-help`}
            />
            <span
              className="mt-1 block text-xs text-[var(--muted-foreground)]"
              id={`${id}-cron-help`}
            >
              {t("cronHelp")}
            </span>
          </label>
        )}
        <label className="text-sm" htmlFor={`${id}-zone`}>
          {t("timezone")}
          <Input
            className="mt-1"
            id={`${id}-zone`}
            aria-label={t("timezone")}
            value={timezone}
            list={`${id}-zones`}
            onChange={(event) => onTimezoneChange(event.target.value)}
            onFocus={() => {
              if (!zones.length) setZones(Intl.supportedValuesOf("timeZone"));
            }}
            aria-describedby={`${id}-zone-help`}
          />
          <datalist id={`${id}-zones`}>
            {zones.map((zone) => (
              <option key={zone} value={zone} />
            ))}
          </datalist>
          <span
            className="mt-1 block text-xs text-[var(--muted-foreground)]"
            id={`${id}-zone-help`}
          >
            {t("timezoneHelp")}
          </span>
        </label>
      </div>
    </fieldset>
  );
}
