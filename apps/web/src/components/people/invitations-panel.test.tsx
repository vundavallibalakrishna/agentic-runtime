import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { addressesOf, InvitationsPanel } from "@/components/people/invitations-panel";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

function admin(pending: object[] = []) {
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ permissions: ["users:read", "users:manage"] }),
    ),
    http.get("*/api/v1/roles", () =>
      HttpResponse.json({
        items: [
          { key: "builder", name: "Builder" },
          { key: "member", name: "Member" },
        ],
      }),
    ),
    http.get("*/api/v1/invitations", () => HttpResponse.json({ items: pending })),
  );
}

describe("inviting people", () => {
  afterEach(() => {
    cleanup();
  });

  it("reads addresses separated by commas, spaces or new lines, once each", () => {
    expect(addressesOf(" A@x.test, b@x.test\nb@x.test ;c@x.test  not-an-address")).toEqual([
      "a@x.test",
      "b@x.test",
      "c@x.test",
    ]);
    expect(addressesOf("")).toEqual([]);
  });

  it("is not shown to someone who may only read the list", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["users:read"] })),
    );
    const { container } = render(wrap(<InvitationsPanel />));
    await waitFor(() => expect(container.textContent).toBe(""));
  });

  it("invites the typed addresses with the chosen role and says whose mail went out", async () => {
    admin();
    let body: unknown = null;
    server.use(
      http.post("*/api/v1/invitations", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json([
          { id: "1", email: "a@x.test", token: "tok-a", mail: { result: "sent" } },
          {
            id: "2",
            email: "b@x.test",
            token: "tok-b",
            mail: { result: "failed", reason: "No mail server is set." },
          },
        ]);
      }),
    );
    render(wrap(<InvitationsPanel />));
    expect(await screen.findByText("Nobody is waiting to accept an invitation.")).toBeTruthy();
    const button = screen.getByRole("button", { name: "Invite" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Email addresses"), {
      target: { value: "a@x.test, b@x.test" },
    });
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "builder" } });
    fireEvent.click(screen.getByRole("button", { name: "Invite 2 people" }));
    expect(await screen.findByText("Mail sent")).toBeTruthy();
    expect(body).toEqual({ emails: ["a@x.test", "b@x.test"], roleKeys: ["builder"] });
    expect(screen.getByText("Mail not sent")).toBeTruthy();
    // The person who invited can pass a link on when its mail did not go out.
    expect(screen.getByText(/\/invite\?token=tok-b$/)).toBeTruthy();
    expect(screen.queryByText(/tok-a/)).toBeNull();
  });

  it("lists who has not accepted yet and revokes one", async () => {
    admin([
      {
        id: "9",
        email: "waiting@x.test",
        roleKeys: ["member"],
        expiresAt: "2026-12-01T00:00:00Z",
        status: "pending",
      },
      { id: "8", email: "joined@x.test", roleKeys: ["member"], status: "accepted" },
      { id: "7", email: "withdrawn@x.test", roleKeys: ["member"], status: "revoked" },
      { id: "6", email: "late@x.test", roleKeys: ["member"], status: "expired" },
    ]);
    let revoked = "";
    server.use(
      http.delete("*/api/v1/invitations/:id", ({ params }) => {
        revoked = String(params.id);
        return HttpResponse.json({ revoked: true });
      }),
    );
    render(wrap(<InvitationsPanel />));
    expect(await screen.findByText("waiting@x.test")).toBeTruthy();
    for (const gone of ["joined@x.test", "withdrawn@x.test", "late@x.test"]) {
      expect(screen.queryByText(gone)).toBeNull();
    }
    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(revoked).toBe("9"));
  });

  it("shows why an invitation was refused", async () => {
    admin();
    server.use(
      http.post("*/api/v1/invitations", () =>
        HttpResponse.json({ detail: "The plan's user limit is reached." }, { status: 403 }),
      ),
    );
    render(wrap(<InvitationsPanel />));
    fireEvent.change(await screen.findByLabelText("Email addresses"), {
      target: { value: "a@x.test" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Invite 1 person" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "The plan's user limit is reached.",
    );
  });
});
