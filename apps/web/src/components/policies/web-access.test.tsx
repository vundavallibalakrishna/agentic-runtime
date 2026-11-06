import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { WebAccess } from "@/components/policies/web-access";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

type Body = { settings: { egressAllowlist: string[] } };

/** The API as the page uses it: one tenant's list of hosts, read and replaced. */
function tenant(hosts: string[], permissions: string[] = ["tenant:read", "tenant:manage"]) {
  const state = { hosts, patches: [] as Body[] };
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions })),
    http.get("*/api/v1/tenant", () =>
      HttpResponse.json({ settings: { egressAllowlist: state.hosts } }),
    ),
    http.patch("*/api/v1/tenant", async ({ request }) => {
      const body = (await request.json()) as Body;
      state.patches.push(body);
      state.hosts = body.settings.egressAllowlist;
      return HttpResponse.json({ settings: { egressAllowlist: state.hosts } });
    }),
  );
  return state;
}

describe("Web access", () => {
  afterEach(() => cleanup());

  it("starts with no host listed and nothing typed in", async () => {
    tenant([]);
    render(wrap(<WebAccess />));

    expect(
      await screen.findByText(/No host is listed, so tools cannot reach the web/),
    ).toBeTruthy();
    expect((screen.getByLabelText("Host") as HTMLInputElement).value).toBe("");
    expect((screen.getByRole("button", { name: "Add host" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("adds a host, and removes one", async () => {
    const state = tenant(["example.com"]);
    render(wrap(<WebAccess />));

    expect(await screen.findByText("example.com")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Host"), { target: { value: "  *.Acme.org " } });
    fireEvent.click(screen.getByRole("button", { name: "Add host" }));

    expect(await screen.findByText(/\*\.acme\.org can now be reached/)).toBeTruthy();
    expect(state.patches[0]).toEqual({
      settings: { egressAllowlist: ["example.com", "*.acme.org"] },
    });
    expect((screen.getByLabelText("Host") as HTMLInputElement).value).toBe("");

    fireEvent.click(screen.getByRole("button", { name: "Remove example.com" }));
    expect(await screen.findByText("example.com can no longer be reached.")).toBeTruthy();
    expect(state.patches[1]).toEqual({ settings: { egressAllowlist: ["*.acme.org"] } });
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Remove example.com" })).toBeNull(),
    );
  });

  it("does not send a host that is already listed", async () => {
    const state = tenant(["example.com"]);
    render(wrap(<WebAccess />));

    await screen.findByText("example.com");
    fireEvent.change(screen.getByLabelText("Host"), { target: { value: "Example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Add host" }));
    expect(await screen.findByText("example.com is already listed.")).toBeTruthy();
    expect(state.patches).toEqual([]);
  });

  it("keeps a refusal on the page in the words the API gave, and what was typed", async () => {
    tenant([]);
    server.use(
      http.patch("*/api/v1/tenant", () =>
        HttpResponse.json({ detail: "egress domain is invalid: not a host" }, { status: 422 }),
      ),
    );
    render(wrap(<WebAccess />));

    await screen.findByText(/No host is listed/);
    fireEvent.change(screen.getByLabelText("Host"), { target: { value: "not a host" } });
    fireEvent.click(screen.getByRole("button", { name: "Add host" }));
    expect(await screen.findByText("egress domain is invalid: not a host")).toBeTruthy();
    expect((screen.getByLabelText("Host") as HTMLInputElement).value).toBe("not a host");
  });

  it("shows the list without controls to someone who cannot manage the organisation", async () => {
    tenant(["example.com"], ["tenant:read"]);
    render(wrap(<WebAccess />));

    expect(await screen.findByText("example.com")).toBeTruthy();
    expect(screen.queryByLabelText("Host")).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove example.com" })).toBeNull();
    expect(screen.getByText(/needs the permission to manage the organisation/)).toBeTruthy();
  });

  it("says so when the list cannot be loaded, and tries again", async () => {
    let calls = 0;
    tenant(["example.com"]);
    server.use(
      http.get("*/api/v1/tenant", () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({ detail: "The organisation could not be read." }, { status: 503 })
          : HttpResponse.json({ settings: { egressAllowlist: ["example.com"] } });
      }),
    );
    render(wrap(<WebAccess />));

    expect(await screen.findByRole("alert")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("example.com")).toBeTruthy();
  });
});
