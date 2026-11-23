import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import {
  type DeliveryChoice,
  DeliveryFields,
  DeliveryList,
  deliveryTargets,
  NO_DELIVERY,
} from "@/components/routines/delivery-fields";
import messages from "@/messages/en.json";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

function Form({ seen }: { seen: (value: DeliveryChoice) => void }) {
  const [value, setValue] = useState<DeliveryChoice>(NO_DELIVERY);
  return (
    <DeliveryFields
      idPrefix="test"
      onChange={(next) => {
        setValue(next);
        seen(next);
      }}
      value={value}
    />
  );
}

describe("routine delivery", () => {
  afterEach(() => {
    cleanup();
  });

  it("sends to the conversation only when no address is given", () => {
    expect(deliveryTargets(NO_DELIVERY)).toEqual([{ type: "conversation" }]);
    expect(deliveryTargets({ email: "   ", onlyReports: true })).toEqual([
      { type: "conversation" },
    ]);
  });

  it("adds an email that is sent every time, or only when there is something to report", () => {
    expect(deliveryTargets({ email: " lead@example.org ", onlyReports: false })).toEqual([
      { type: "conversation" },
      { type: "email", channel: "lead@example.org", when: "always" },
    ]);
    expect(deliveryTargets({ email: "lead@example.org", onlyReports: true })[1]).toEqual({
      type: "email",
      channel: "lead@example.org",
      when: "something_to_report",
    });
  });

  it("lets the choice be made only once an address is typed", () => {
    let last: DeliveryChoice = NO_DELIVERY;
    render(
      wrap(
        <Form
          seen={(value) => {
            last = value;
          }}
        />,
      ),
    );
    const only = screen.getByRole("checkbox", {
      name: /Only when there is something to report/,
    }) as HTMLInputElement;
    expect(only.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Email the result to (optional)"), {
      target: { value: "lead@example.org" },
    });
    expect(only.disabled).toBe(false);
    fireEvent.click(only);
    expect(last).toEqual({ email: "lead@example.org", onlyReports: true });
  });

  it("says where a routine's result goes and when", () => {
    render(
      wrap(
        <DeliveryList
          targets={[
            { type: "conversation" },
            { type: "email", channel: "lead@example.org", when: "something_to_report" },
            { type: "webhook", config: { url: "https://hooks.example.org/in" }, when: "always" },
            { type: "slack", channel: "#ops" },
          ]}
        />,
      ),
    );
    expect(screen.getByText("Your conversation")).toBeTruthy();
    expect(screen.getByText("Email to lead@example.org")).toBeTruthy();
    expect(screen.getAllByText(/only when there is something to report/)).toHaveLength(1);
    expect(screen.getByText("Webhook at https://hooks.example.org/in")).toBeTruthy();
    expect(screen.getByText("slack")).toBeTruthy();
  });
});
