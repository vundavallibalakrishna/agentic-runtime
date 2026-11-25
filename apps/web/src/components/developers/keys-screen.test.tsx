import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KeysScreen } from "@/components/developers/keys-screen";
import { clearCachedSession } from "@/lib/session";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/developers/keys",
  useRouter: () => ({ push: () => undefined, replace: () => undefined }),
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

function workspace(permissions: string[], accounts: object[] = []) {
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ permissions, user: { displayName: "Ada", email: "ada@acme.example" } }),
    ),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/service-accounts", () => HttpResponse.json({ items: accounts })),
    http.get("*/api/v1/service-accounts:capabilities", () =>
      HttpResponse.json({
        items: [
          { key: "chat", role: "member", permissions: ["chat:use", "agents:read"] },
          {
            key: "knowledge_manage",
            role: "knowledge_manager",
            permissions: ["knowledge:read", "knowledge:manage", "chat:use"],
          },
        ],
      }),
    ),
    http.get("*/api/v1/roles", () =>
      HttpResponse.json({
        items: [
          { id: "role-member", key: "member", name: "Member", permissions: [] },
          { id: "role-km", key: "knowledge_manager", name: "Knowledge manager", permissions: [] },
        ],
      }),
    ),
  );
}

const ALL = ["service_accounts:manage", "roles:manage", "users:read", "api_keys:manage_own"];

describe("service accounts and keys", () => {
  afterEach(() => {
    cleanup();
    clearCachedSession();
  });

  it("creates the account, gives it the roles for what it will do, and shows the key once", async () => {
    workspace(ALL);
    const calls: { path: string; body: Record<string, unknown> }[] = [];
    server.use(
      http.post("*/api/v1/service-accounts", async ({ request }) => {
        calls.push({ path: "account", body: (await request.json()) as Record<string, unknown> });
        return HttpResponse.json({ id: "sa-1", name: "Billing sync", status: "active" });
      }),
      http.post("*/api/v1/role-assignments", async ({ request }) => {
        calls.push({ path: "role", body: (await request.json()) as Record<string, unknown> });
        return HttpResponse.json({ id: "assignment" });
      }),
      http.post("*/api/v1/api-keys", async ({ request }) => {
        calls.push({ path: "key", body: (await request.json()) as Record<string, unknown> });
        return HttpResponse.json({ id: "key-1", prefix: "ak_abc", key: "ak_abc.sk_secret" });
      }),
      http.get("*/api/v1/api-keys", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<KeysScreen />));
    const create = await screen.findByRole("button", { name: "Create account and key" });
    // Nothing to create until it has a name and something to do.
    expect((create as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Billing sync" } });
    fireEvent.click(screen.getByLabelText("Chat with agents and send them files"));
    fireEvent.click(screen.getByLabelText("Create knowledge bases and add documents"));
    // The person is told exactly what the key will be allowed before they confirm.
    expect(screen.getByTestId("grants").textContent).toContain(
      "chat:use, agents:read, knowledge:read, knowledge:manage",
    );
    fireEvent.click(create);
    const shown = await screen.findByTestId("new-secret");
    expect(shown.textContent).toContain("ak_abc.sk_secret");
    expect(shown.textContent).toContain("This is the only time the key is shown.");
    expect(calls.map((call) => call.path)).toEqual(["account", "role", "role", "key"]);
    expect(calls[1]?.body).toEqual({
      roleId: "role-member",
      principalType: "service_account",
      principalId: "sa-1",
    });
    expect(calls[2]?.body.roleId).toBe("role-km");
    expect(calls[3]?.body).toMatchObject({
      serviceAccountId: "sa-1",
      scopes: ["chat:use", "agents:read", "knowledge:read", "knowledge:manage"],
      expiresInDays: 90,
    });
  });

  it("lists accounts with their keys and asks before revoking one", async () => {
    workspace(ALL, [{ id: "sa-1", name: "Billing sync", status: "active" }]);
    let revoked = 0;
    server.use(
      http.get("*/api/v1/api-keys", () =>
        HttpResponse.json({
          items: [{ id: "key-1", prefix: "ak_abc", scopes: [], lastUsedAt: null, revokedAt: null }],
        }),
      ),
      http.delete("*/api/v1/api-keys/key-1", () => {
        revoked += 1;
        return HttpResponse.json({ revoked: true });
      }),
    );
    render(wrap(<KeysScreen />));
    expect(await screen.findByText("Billing sync")).toBeTruthy();
    expect(screen.getByText(/never used/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Revoke ak_abc" }));
    expect(revoked).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "Revoke ak_abc now?" }));
    await waitFor(() => expect(revoked).toBe(1));
  });

  it("says so when there are none, and when the person may not manage them", async () => {
    workspace(ALL);
    render(wrap(<KeysScreen />));
    expect(
      await screen.findByText(
        "No service accounts yet. Create one to let a program call this workspace.",
      ),
    ).toBeTruthy();
    cleanup();
    clearCachedSession();
    workspace(["chat:use"]);
    render(wrap(<KeysScreen />));
    expect(await screen.findByText("You do not have permission to view this page.")).toBeTruthy();
  });
});
