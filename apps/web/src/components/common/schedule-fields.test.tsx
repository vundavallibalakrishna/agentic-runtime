import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { useState } from "react";
import { afterEach, expect, it } from "vitest";

import { ScheduleFields } from "@/components/common/schedule-fields";
import messages from "@/messages/en.json";

afterEach(cleanup);
function Form({ initial = "0 9 * * 1" }: { initial?: string }) {
  const [cron, setCron] = useState(initial);
  const [zone, setZone] = useState("UTC");
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <ScheduleFields
        cron={cron}
        timezone={zone}
        onCronChange={setCron}
        onTimezoneChange={setZone}
      />
      <output aria-label="Saved schedule">
        {cron} | {zone}
      </output>
    </NextIntlClientProvider>
  );
}
it("edits a weekly schedule through day, time and repeat controls", () => {
  render(<Form />);
  expect((screen.getByLabelText("Repeat") as HTMLSelectElement).value).toBe("weekly");
  fireEvent.change(screen.getByLabelText("Day of the week"), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText("Time"), { target: { value: "14:35" } });
  expect(screen.getByLabelText("Saved schedule").textContent).toBe("35 14 * * 5 | UTC");
  fireEvent.change(screen.getByLabelText("Repeat"), { target: { value: "weekdays" } });
  expect(screen.queryByLabelText("Day of the week")).toBeNull();
  expect(screen.getByLabelText("Saved schedule").textContent).toBe("35 14 * * 1-5 | UTC");
  fireEvent.change(screen.getByLabelText("Repeat"), { target: { value: "daily" } });
  expect(screen.getByLabelText("Saved schedule").textContent).toBe("35 14 * * * | UTC");
});
it("preserves custom cron without rewriting it until the person chooses a simple repeat", () => {
  render(<Form initial="*/15 8-18 * * 1-5" />);
  expect((screen.getByLabelText("Cron expression") as HTMLInputElement).value).toBe(
    "*/15 8-18 * * 1-5",
  );
  fireEvent.change(screen.getByLabelText("Timezone"), { target: { value: "Asia/Kolkata" } });
  expect(screen.getByLabelText("Saved schedule").textContent).toBe(
    "*/15 8-18 * * 1-5 | Asia/Kolkata",
  );
});
