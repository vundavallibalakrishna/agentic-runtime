import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

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
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

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

    expect(await screen.findByText("Host added to the saved allowlist: *.acme.org.")).toBeTruthy();
    expect(state.patches[0]).toEqual({
      settings: { egressAllowlist: ["example.com", "*.acme.org"] },
    });
    expect((screen.getByLabelText("Host") as HTMLInputElement).value).toBe("");

    fireEvent.click(screen.getByRole("button", { name: "Remove example.com" }));
    expect(await screen.findByText("example.com removed from the saved allowlist.")).toBeTruthy();
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

  it("explains a verification refusal, keeps the host draft and never replays the write on refresh", async () => {
    tenant([]);
    let writes = 0;
    server.use(
      http.patch("*/api/v1/tenant", () => {
        writes += 1;
        return HttpResponse.json(
          { detail: "Origin rejected", code: "csrf_failed" },
          { status: 403 },
        );
      }),
    );
    render(wrap(<WebAccess />));
    await screen.findByText(/No host is listed/);
    fireEvent.change(screen.getByLabelText("Host"), { target: { value: "work.example" } });
    fireEvent.click(screen.getByRole("button", { name: "Add host" }));
    await screen.findByText(messages.apiErrors.csrf);
    expect(screen.queryByText("Origin rejected")).toBeNull();
    expect((screen.getByLabelText("Host") as HTMLInputElement).value).toBe("work.example");
    const details = screen
      .getByText(messages.apiErrors.details)
      .closest("details") as HTMLDetailsElement;
    details.open = true;
    fireEvent(details, new Event("toggle"));
    expect(screen.getByText("Origin rejected")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: messages.webAccess.refresh }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect((screen.getByLabelText("Host") as HTMLInputElement).value).toBe("work.example");
    expect(writes).toBe(1);
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
function answer(body: unknown) {
  return new Response(JSON.stringify(body), { headers: { "content-type": "application/json" } });
}

describe("web access request states", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });
  it("guards same-frame additions/removals and does not erase a newer host draft", async () => {
    const state = tenant(["saved.example.org"]);
    const pending = deferred<Response>();
    const nativeFetch = globalThis.fetch;
    let writes = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PATCH") {
          writes++;
          return pending.promise;
        }
        return nativeFetch(input, init);
      }),
    );
    render(wrap(<WebAccess />));
    await screen.findByText("saved.example.org");
    const field = screen.getByLabelText("Host");
    fireEvent.change(field, { target: { value: "new.example.org" } });
    const form = screen.getByRole("button", { name: "Add host" }).closest("form");
    if (!form) throw new Error("Host form is required");
    act(() => {
      fireEvent.submit(form);
      fireEvent.submit(form);
      fireEvent.click(screen.getByRole("button", { name: "Remove saved.example.org" }));
    });
    expect(writes).toBe(1);
    fireEvent.change(field, { target: { value: "later.example.org" } });
    await act(async () =>
      pending.resolve(
        answer({ settings: { egressAllowlist: [...state.hosts, "new.example.org"] } }),
      ),
    );
    await screen.findByText("new.example.org");
    expect((field as HTMLInputElement).value).toBe("later.example.org");
  });
  it.each([{}, { settings: { egressAllowlist: ["different.example.org"] } }])(
    "does not invent saved hosts from an incomplete or mismatched receipt %j",
    async (receipt) => {
      const state = tenant([]);
      let writes = 0;
      server.use(
        http.patch("*/api/v1/tenant", () => {
          writes++;
          return HttpResponse.json(receipt);
        }),
      );
      render(wrap(<WebAccess />));
      await screen.findByText(messages.webAccess.empty);
      fireEvent.change(screen.getByLabelText("Host"), { target: { value: "draft.example.org" } });
      fireEvent.click(screen.getByRole("button", { name: "Add host" }));
      await screen.findByText(messages.webAccess.unconfirmed);
      expect(screen.getByRole("button", { name: "Add host" }).matches(":disabled")).toBe(true);
      expect(screen.queryByRole("button", { name: "Remove draft.example.org" })).toBeNull();
      fireEvent.click(screen.getByRole("button", { name: messages.webAccess.refresh }));
      await waitFor(() =>
        expect(screen.getByRole("button", { name: "Add host" }).matches(":disabled")).toBe(false),
      );
      expect((screen.getByLabelText("Host") as HTMLInputElement).value).toBe("draft.example.org");
      expect(writes).toBe(1);
      expect(state.hosts).toEqual([]);
    },
  );
  it("keeps the recovery hold when the saved-list read also fails", async () => {
    tenant(["saved.example.org"]);
    let failed = false;
    server.use(
      http.patch("*/api/v1/tenant", () => {
        failed = true;
        return HttpResponse.json({ detail: "save unavailable" }, { status: 503 });
      }),
      http.get("*/api/v1/tenant", () =>
        failed
          ? HttpResponse.json({ detail: "read unavailable" }, { status: 503 })
          : HttpResponse.json({ settings: { egressAllowlist: ["saved.example.org"] } }),
      ),
    );
    render(wrap(<WebAccess />));
    await screen.findByText("saved.example.org");
    fireEvent.click(screen.getByRole("button", { name: "Remove saved.example.org" }));
    await screen.findByText("save unavailable");
    fireEvent.click(screen.getByRole("button", { name: messages.webAccess.refresh }));
    await screen.findByText("read unavailable");
    expect(screen.getByText("saved.example.org")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Remove saved.example.org" }).matches(":disabled"),
    ).toBe(true);
  });
  it("searches all 100,000 unique saved hosts before paging", async () => {
    tenant(Array.from({ length: 100_000 }, (_, n) => `host-${n}.example.org`));
    render(wrap(<WebAccess />));
    await screen.findByText("host-0.example.org");
    expect(screen.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "host-99999.example.org" },
    });
    expect(screen.getByText("host-99999.example.org")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: messages.webAccess.clearSearch }));
    expect(screen.getAllByRole("listitem")).toHaveLength(25);
  });
  it("does not turn an incomplete metadata response into an empty allowlist", async () => {
    tenant([]);
    server.use(http.get("*/api/v1/tenant", () => HttpResponse.json({ settings: {} })));
    render(wrap(<WebAccess />));
    await screen.findByText(messages.webAccess.unconfirmed);
    expect(screen.queryByText(messages.webAccess.empty)).toBeNull();
    expect(screen.queryByRole("button", { name: "Add host" })).toBeNull();
  });
  it("does not request protected settings without tenant read permission", async () => {
    tenant([], ["policies:read"]);
    let reads = 0;
    server.use(
      http.get("*/api/v1/tenant", () => {
        reads++;
        return HttpResponse.json({});
      }),
    );
    render(wrap(<WebAccess />));
    await screen.findByText(messages.webAccess.readDenied);
    expect(reads).toBe(0);
    expect(screen.queryByLabelText("Host")).toBeNull();
  });
  it("cancels a pending patch on unmount and discards a late acknowledgement", async () => {
    tenant([]);
    const pending = deferred<Response>();
    const nativeFetch = globalThis.fetch;
    let signal: AbortSignal | null | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PATCH") {
          signal = init.signal;
          return pending.promise;
        }
        return nativeFetch(input, init);
      }),
    );
    const rendered = render(wrap(<WebAccess />));
    await screen.findByText(messages.webAccess.empty);
    fireEvent.change(screen.getByLabelText("Host"), { target: { value: "draft.example.org" } });
    fireEvent.click(screen.getByRole("button", { name: "Add host" }));
    await waitFor(() => expect(signal).toBeTruthy());
    rendered.unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () =>
      pending.resolve(answer({ settings: { egressAllowlist: ["draft.example.org"] } })),
    );
    expect(screen.queryByText(/Host added/)).toBeNull();
  });
  it("accepts a confirmed allowlist with a different ordering", async () => {
    tenant(["saved.example.org"]);
    server.use(
      http.patch("*/api/v1/tenant", () =>
        HttpResponse.json({
          settings: { egressAllowlist: ["new.example.org", "saved.example.org"] },
        }),
      ),
    );
    render(wrap(<WebAccess />));
    await screen.findByText("saved.example.org");
    fireEvent.change(screen.getByLabelText("Host"), { target: { value: "new.example.org" } });
    fireEvent.click(screen.getByRole("button", { name: "Add host" }));
    await screen.findByText("Host added to the saved allowlist: new.example.org.");
    expect((screen.getByLabelText("Host") as HTMLInputElement).value).toBe("");
  });
  it("removes stale metadata and write controls when a refresh explicitly denies access", async () => {
    tenant(["saved.example.org"]);
    let denied = false;
    server.use(
      http.get("*/api/v1/tenant", () =>
        denied
          ? HttpResponse.json({ detail: "access removed" }, { status: 403 })
          : HttpResponse.json({ settings: { egressAllowlist: ["saved.example.org"] } }),
      ),
    );
    render(wrap(<WebAccess />));
    await screen.findByText("saved.example.org");
    denied = true;
    fireEvent.click(screen.getByRole("button", { name: messages.webAccess.refresh }));
    await screen.findByText("access removed");
    expect(screen.queryByText("saved.example.org")).toBeNull();
    expect(screen.queryByLabelText("Host")).toBeNull();
  });
});
