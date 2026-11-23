import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { ResetPasswordForm } from "@/components/auth/reset-password-form";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

function fill(first: string, second: string) {
  fireEvent.change(screen.getByLabelText("New password"), { target: { value: first } });
  fireEvent.change(screen.getByLabelText("New password again"), { target: { value: second } });
  fireEvent.click(screen.getByRole("button", { name: "Set password" }));
}

describe("choose a new password", () => {
  afterEach(() => {
    cleanup();
  });

  it("asks for the link when the page is opened without one", () => {
    render(wrap(<ResetPasswordForm token="" />));
    expect(screen.getByRole("alert").textContent).toContain(
      "This page needs the link from your reset mail.",
    );
    expect(screen.getByRole("link", { name: "Ask for a new link" }).getAttribute("href")).toBe(
      "/forgot-password",
    );
    expect(screen.queryByLabelText("New password")).toBeNull();
  });

  it("does not send two passwords that differ", async () => {
    let calls = 0;
    server.use(
      http.post("*/api/v1/auth/password-reset/confirm", () => {
        calls += 1;
        return HttpResponse.json({ reset: true });
      }),
    );
    render(wrap(<ResetPasswordForm token="tok" />));
    fill("a-new-password", "a-different-one");
    expect((await screen.findByRole("alert")).textContent).toContain(
      "The two passwords are not the same.",
    );
    expect(calls).toBe(0);
  });

  it("sends the token with the new password and says it is changed", async () => {
    let sent: unknown = null;
    server.use(
      http.post("*/api/v1/auth/password-reset/confirm", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ reset: true });
      }),
    );
    render(wrap(<ResetPasswordForm token="tok-123" />));
    fill("a-new-password", "a-new-password");
    expect((await screen.findByRole("status")).textContent).toContain(
      "Your password is changed. Sign in with the new one.",
    );
    expect(sent).toEqual({ token: "tok-123", password: "a-new-password" });
  });

  it("shows why the link was refused and offers a new one", async () => {
    server.use(
      http.post("*/api/v1/auth/password-reset/confirm", () =>
        HttpResponse.json(
          { detail: "This reset link has expired. Ask for a new one.", code: "validation_failed" },
          { status: 422 },
        ),
      ),
    );
    render(wrap(<ResetPasswordForm token="old" />));
    fill("a-new-password", "a-new-password");
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain("This reset link has expired."),
    );
    expect(screen.getByRole("link", { name: "Ask for a new link" })).toBeTruthy();
  });
});
