import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FailedReply } from "@/components/chat/failed-reply";
import messages from "@/messages/en.json";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("Failed reply", () => {
  afterEach(() => cleanup());

  it("is drawn as a failure with the reason the run gave, and tries again", () => {
    const retry = vi.fn();
    render(
      wrap(
        <FailedReply
          busy={false}
          onRetry={retry}
          reason="The model provider did not answer."
          said=""
        />,
      ),
    );
    const box = screen.getByRole("alert");
    expect(box.textContent).toContain("This reply could not be made.");
    expect(box.textContent).toContain("The model provider did not answer.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("keeps what the reply had already said above the failure", () => {
    render(
      wrap(<FailedReply busy={false} reason="The run was stopped." said="The first point is" />),
    );
    expect(screen.getByText("The first point is")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("The run was stopped.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("falls back to a plain sentence when no reason was given, and waits while a run streams", () => {
    render(wrap(<FailedReply busy onRetry={() => undefined} reason="" said="" />));
    expect(screen.getByRole("alert").textContent).toContain("The run failed.");
    expect((screen.getByRole("button", { name: "Try again" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
  });
});
