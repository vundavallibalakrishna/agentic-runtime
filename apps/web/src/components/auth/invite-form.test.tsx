import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { InviteForm } from "@/components/auth/invite-form";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

function known() {
  server.use(
    http.post("*/api/v1/auth/invitation", () =>
      HttpResponse.json({ email: "new.person@example.test", tenantName: "Acme" }),
    ),
  );
}

describe("accept an invitation", () => {
  afterEach(() => {
    cleanup();
  });

  it("asks for the link when the page is opened without one", () => {
    render(wrap(<InviteForm token="" />));
    expect(screen.getByRole("alert").textContent).toContain(
      "This page needs the link from your invitation mail.",
    );
  });

  it("says why an invitation cannot be used", async () => {
    server.use(
      http.post("*/api/v1/auth/invitation", () =>
        HttpResponse.json(
          { detail: "This invitation has expired. Ask the person who invited you for a new one." },
          { status: 422 },
        ),
      ),
    );
    render(wrap(<InviteForm token="old" />));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "This invitation has expired.",
    );
    expect(screen.queryByLabelText("Your name")).toBeNull();
  });

  it("shows who is joining what, and makes the account", async () => {
    known();
    let sent: unknown = null;
    server.use(
      http.post("*/api/v1/auth/invitation/accept", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ accepted: true, email: "new.person@example.test" });
      }),
    );
    render(wrap(<InviteForm token="tok-9" />));
    expect(await screen.findByText("Choose your name and a password to join Acme.")).toBeTruthy();
    const email = screen.getByLabelText("Email") as HTMLInputElement;
    expect(email.value).toBe("new.person@example.test");
    expect(email.readOnly).toBe(true);
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "New Person" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a-good-password" } });
    fireEvent.change(screen.getByLabelText("Password again"), {
      target: { value: "a-good-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create my account" }));
    expect((await screen.findByRole("status")).textContent).toContain("Your account is ready.");
    expect(sent).toEqual({
      token: "tok-9",
      displayName: "New Person",
      password: "a-good-password",
    });
  });

  it("does not send two passwords that differ, and shows a refusal", async () => {
    known();
    let calls = 0;
    server.use(
      http.post("*/api/v1/auth/invitation/accept", () => {
        calls += 1;
        return HttpResponse.json(
          { detail: "This address already has an account. Sign in, or reset the password." },
          { status: 409 },
        );
      }),
    );
    render(wrap(<InviteForm token="tok" />));
    fireEvent.change(await screen.findByLabelText("Your name"), { target: { value: "N" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a-good-password" } });
    fireEvent.change(screen.getByLabelText("Password again"), { target: { value: "different-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create my account" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "The two passwords are not the same.",
    );
    expect(calls).toBe(0);
    fireEvent.change(screen.getByLabelText("Password again"), {
      target: { value: "a-good-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create my account" }));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain("already has an account"),
    );
    expect(calls).toBe(1);
  });
});
