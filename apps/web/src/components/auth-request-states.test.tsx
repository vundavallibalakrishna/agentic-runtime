import { fireEvent, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import ForgotPasswordPage from "@/app/(auth)/forgot-password/page";
import GuestPortalPage from "@/app/guest/page";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

function show(children: ReactNode) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>,
  );
}

describe("authentication request states", () => {
  it("retains the reset email after an error and reports success only after a successful retry", async () => {
    let attempts = 0;
    server.use(
      http.post("*/api/v1/auth/password-reset", () =>
        ++attempts === 1
          ? HttpResponse.json({ detail: "Reset unavailable" }, { status: 503 })
          : new HttpResponse(null, { status: 202 }),
      ),
    );
    show(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "person@workspace.invalid" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send reset" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText(messages.auth.forgotSent)).toBeNull();
    expect((screen.getByLabelText("Email") as HTMLInputElement).value).toBe(
      "person@workspace.invalid",
    );
    fireEvent.click(screen.getByRole("button", { name: "Send reset" }));
    expect(await screen.findByText(messages.auth.forgotSent)).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("handles a failed guest-link request then an empty 202 response", async () => {
    let attempts = 0;
    server.use(
      http.post("*/api/v1/auth/guest/request-link", () =>
        ++attempts === 1
          ? HttpResponse.json({ detail: "Links unavailable" }, { status: 503 })
          : new HttpResponse(null, { status: 202 }),
      ),
    );
    show(<GuestPortalPage />);
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "guest@workspace.invalid" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Email me a link" }));
    expect(await screen.findByText(messages.guestAccess.requestError)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Email me a link" }));
    expect(await screen.findByText(messages.guestAccess.requested)).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("keeps guest credentials editable after rejection and clears them after success", async () => {
    let attempts = 0;
    server.use(
      http.post("*/api/v1/auth/guest/session", () =>
        ++attempts === 1
          ? HttpResponse.json({ detail: "Rejected" }, { status: 401 })
          : HttpResponse.json({ sessionId: "session" }),
      ),
    );
    show(<GuestPortalPage />);
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Use a link" }), {
      button: 0,
      ctrlKey: false,
    });
    const token = screen.getByLabelText("Link token") as HTMLInputElement;
    expect(token.type).toBe("password");
    expect(token.required).toBe(true);
    const code = screen.getByLabelText("Authenticator code (if set up)") as HTMLInputElement;
    expect(code.inputMode).toBe("numeric");
    expect(code.maxLength).toBe(6);
    fireEvent.change(token, { target: { value: "test-token" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText(messages.guestAccess.signInError)).toBeTruthy();
    expect(token.value).toBe("test-token");
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText(messages.guestAccess.signedIn)).toBeTruthy();
    expect(token.value).toBe("");
    expect(code.value).toBe("");
  });
  it("shows one guest task at a time and keeps entered values when switching", () => {
    show(<GuestPortalPage />);
    expect(screen.getByLabelText("Email")).toBeTruthy();
    expect(screen.queryByLabelText("Link token")).toBeNull();
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "guest@workspace.invalid" },
    });
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Use a link" }), {
      button: 0,
      ctrlKey: false,
    });
    expect(screen.queryByLabelText("Email")).toBeNull();
    fireEvent.change(screen.getByLabelText("Link token"), { target: { value: "private-token" } });
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Request a link" }), {
      button: 0,
      ctrlKey: false,
    });
    expect((screen.getByLabelText("Email") as HTMLInputElement).value).toBe(
      "guest@workspace.invalid",
    );
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Use a link" }), {
      button: 0,
      ctrlKey: false,
    });
    expect((screen.getByLabelText("Link token") as HTMLInputElement).value).toBe("private-token");
  });

  it("clears the previous task's request status when switching guest tasks", async () => {
    server.use(
      http.post("*/api/v1/auth/guest/request-link", () => new HttpResponse(null, { status: 202 })),
    );
    show(<GuestPortalPage />);
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "guest@workspace.invalid" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Email me a link" }));
    expect(await screen.findByText(messages.guestAccess.requested)).toBeTruthy();
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Use a link" }), {
      button: 0,
      ctrlKey: false,
    });
    expect(screen.queryByText(messages.guestAccess.requested)).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
