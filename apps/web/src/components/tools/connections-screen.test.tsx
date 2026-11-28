import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { ConnectionsScreen } from "@/components/tools/connections-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => children,
}));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/connections");
});
beforeEach(() => {
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ permissions: ["connections:manage_own", "tools:read", "tools:create"] }),
    ),
  );
  for (const endpoint of [
    "connections",
    "credential-providers",
    "service-connections",
    "data-connections",
  ]) {
    server.use(http.get(`*/api/v1/${endpoint}`, () => HttpResponse.json({ items: [] })));
  }
});
function view() {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <ConnectionsScreen />
    </NextIntlClientProvider>
  );
}
function tab(name: string) {
  fireEvent.mouseDown(screen.getByRole("tab", { name }), { button: 0, ctrlKey: false });
}
function row(name: string) {
  const node = screen.getByText(name, { exact: true }).closest("li");
  if (!node) throw new Error("Saved connection needs its existing row");
  return within(node);
}

it("shows only the selected authentication fields and omits stale OAuth settings on save", async () => {
  let saved: Record<string, unknown> | undefined;
  for (const path of [
    "connections",
    "credential-providers",
    "data-connections",
    "service-connections",
  ]) {
    server.use(http.get(`*/api/v1/${path}`, () => HttpResponse.json({ items: [] })));
  }
  server.use(
    http.post("*/api/v1/service-connections", async ({ request }) => {
      saved = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ id: "connection-1" });
    }),
  );
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ConnectionsScreen />
    </NextIntlClientProvider>,
  );
  await screen.findByText("No saved connections yet.");
  fireEvent.click(screen.getByText("Add a service connection"));
  expect(screen.queryByLabelText("Username")).toBeNull();
  const method = screen.getByLabelText("Authentication method");
  fireEvent.change(method, { target: { value: "oauth_client_credentials" } });
  fireEvent.change(screen.getByLabelText("Token URL"), {
    target: { value: "https://service.example/token" },
  });
  fireEvent.change(method, { target: { value: "basic" } });
  expect(screen.queryByLabelText("Token URL")).toBeNull();
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Work service" } });
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: "operator" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "test-only-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Save connection" }));
  await waitFor(() => expect(saved?.kind).toBe("basic"));
  expect(saved?.username).toBe("operator");
  expect(saved).not.toHaveProperty("tokenUrl");
  expect(saved).not.toHaveProperty("clientId");
  expect(saved).not.toHaveProperty("headerName");
});

it.each([
  { endpoint: "service-connections", tabName: "Service credentials", label: "Saved connections" },
  { endpoint: "credential-providers", tabName: "Personal accounts", label: "Personal accounts" },
  { endpoint: "data-connections", tabName: "Database connections", label: "Data connections" },
])(
  "bounds 100,000 $endpoint rows and filters the complete loaded catalogue",
  async ({ endpoint, tabName, label }) => {
    server.use(
      http.get(`*/api/v1/${endpoint}`, () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, index) => ({
            id: `record-${index}`,
            name: `Saved ${index}`,
            slug: `slug-${index}`,
            kind: "bearer",
            engine: "postgres",
            status: index === 99_999 ? "expired" : "active",
          })),
        }),
      ),
    );
    if (endpoint === "credential-providers")
      server.use(
        http.get("*/api/v1/connections", () =>
          HttpResponse.json({
            items: Array.from({ length: 100_000 }, (_, index) => ({
              id: `grant-${index}`,
              providerId: `record-${index}`,
              status: index === 99_999 ? "active" : "revoked",
            })),
          }),
        ),
      );
    render(view());
    await screen.findByRole("tab", { name: tabName });
    await waitFor(() => expect(screen.queryByText(messages.connections.loading)).toBeNull());
    if (tabName !== "Service credentials") tab(tabName);
    const list = within(await screen.findByRole("region", { name: label }));
    await list.findByText("Saved 0", { exact: true });
    expect(list.getAllByRole("listitem")).toHaveLength(25);
    expect(list.getByText("1–25 of 100,000")).toBeTruthy();
    fireEvent.click(list.getByRole("button", { name: "Next" }));
    expect(list.getByText("Saved 25", { exact: true })).toBeTruthy();
    fireEvent.change(list.getByRole("searchbox"), { target: { value: "record-99999" } });
    expect(list.getAllByRole("listitem")).toHaveLength(1);
    expect(list.getByText("Saved 99999", { exact: true })).toBeTruthy();
    fireEvent.change(list.getByRole("combobox", { name: "Status" }), {
      target: { value: endpoint === "credential-providers" ? "unconnected" : "active" },
    });
    expect(list.getByText(messages.connections.noMatches)).toBeTruthy();
    fireEvent.click(list.getByRole("button", { name: "Clear filters" }));
    expect(list.getAllByRole("listitem")).toHaveLength(25);
    expect(list.getByText("Saved 0", { exact: true })).toBeTruthy();
  },
);

it("keeps a service-list failure distinct from empty while other permitted lists remain usable", async () => {
  let reads = 0;
  server.use(
    http.get("*/api/v1/service-connections", () =>
      ++reads === 1
        ? HttpResponse.json({ detail: "Saved services unavailable" }, { status: 503 })
        : HttpResponse.json({ items: [] }),
    ),
    http.get("*/api/v1/data-connections", () =>
      HttpResponse.json({ items: [{ id: "db", name: "Saved database", engine: "postgres" }] }),
    ),
  );
  render(view());
  await screen.findByText("Saved services unavailable");
  expect(screen.queryByText(messages.connections.serviceEmpty)).toBeNull();
  tab("Database connections");
  expect(screen.getByText("Saved database")).toBeTruthy();
  tab("Service credentials");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByText(messages.connections.serviceEmpty);
  expect(reads).toBe(2);
});

it.each([
  { permissions: [] as string[], allowed: [] as string[] },
  { permissions: ["tools:read"], allowed: ["data-connections"] },
  { permissions: ["connections:manage_own"], allowed: ["service-connections"] },
])("requests only the catalogues allowed by $permissions", async ({ permissions, allowed }) => {
  server.use(http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions })));
  const reads: string[] = [];
  for (const endpoint of [
    "connections",
    "credential-providers",
    "service-connections",
    "data-connections",
  ]) {
    server.use(
      http.get(`*/api/v1/${endpoint}`, () => {
        reads.push(endpoint);
        return HttpResponse.json({ items: [] });
      }),
    );
  }
  render(view());
  await screen.findByRole("tab", { name: "Service credentials" });
  await waitFor(() => expect(screen.queryByText(messages.detail.working)).toBeNull());
  expect(reads.sort()).toEqual(allowed.sort());
  tab("Database connections");
  expect(screen.queryByText("Add a database connection")).toBeNull();
  expect(screen.queryByRole("button", { name: "Test connection" })).toBeNull();
});

it("uses a row-specific replacement secret and preserves the separate creation draft", async () => {
  server.use(
    http.get("*/api/v1/service-connections", () =>
      HttpResponse.json({
        items: [
          { id: "a", name: "Alpha", kind: "bearer", status: "active" },
          { id: "b", name: "Beta", kind: "bearer", status: "active" },
        ],
      }),
    ),
  );
  const writes: { id: unknown; body: unknown }[] = [];
  server.use(
    http.post("*/api/v1/service-connections/:id:rotate", async ({ request, params }) => {
      writes.push({ id: params.id, body: await request.json() });
      return HttpResponse.json({});
    }),
  );
  render(view());
  await screen.findByText("Alpha", { exact: true });
  fireEvent.click(screen.getByText("Add a service connection"));
  fireEvent.change(screen.getByLabelText("Bearer token"), {
    target: { value: "test-only-create-secret" },
  });
  fireEvent.click(row("Alpha").getByRole("button", { name: "Rotate secret" }));
  fireEvent.change(row("Alpha").getByLabelText("New secret"), {
    target: { value: "test-only-alpha-secret" },
  });
  fireEvent.click(row("Alpha").getByRole("button", { name: "Cancel" }));
  fireEvent.click(row("Beta").getByRole("button", { name: "Rotate secret" }));
  expect((row("Beta").getByLabelText("New secret") as HTMLInputElement).value).toBe("");
  const field = row("Beta").getByLabelText("New secret");
  fireEvent.change(field, { target: { value: "test-only-beta-secret" } });
  const form = field.closest("form");
  if (!form) throw new Error("Replacement needs a form");
  act(() => {
    fireEvent.submit(form);
    fireEvent.submit(form);
  });
  await waitFor(() =>
    expect(writes).toEqual([{ id: "b", body: { secret: "test-only-beta-secret" } }]),
  );
  await waitFor(() => expect(row("Beta").queryByLabelText("New secret")).toBeNull());
  expect((screen.getByLabelText("Bearer token") as HTMLInputElement).value).toBe(
    "test-only-create-secret",
  );
});

it("uses the selected connection's test URL and keeps refused tests local and retryable", async () => {
  server.use(
    http.get("*/api/v1/service-connections", () =>
      HttpResponse.json({
        items: [
          { id: "a", name: "Alpha", probeUrl: "https://alpha.example/check", kind: "bearer" },
        ],
      }),
    ),
  );
  let body: unknown;
  server.use(
    http.post("*/api/v1/service-connections/a:test", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json({ ok: false, error: "Target refused this test" });
    }),
  );
  render(view());
  await screen.findByText("Alpha", { exact: true });
  fireEvent.click(screen.getByText("Add a service connection"));
  fireEvent.change(screen.getByLabelText("Test URL"), {
    target: { value: "https://new-connection.example/check" },
  });
  fireEvent.click(row("Alpha").getByRole("button", { name: "Test" }));
  const url = row("Alpha").getByLabelText("Test URL");
  expect((url as HTMLInputElement).value).toBe("https://alpha.example/check");
  fireEvent.change(url, { target: { value: "https://override.example/check" } });
  const form = url.closest("form");
  if (!form) throw new Error("Test needs a form");
  fireEvent.submit(form);
  await row("Alpha").findByText("Target refused this test");
  expect(body).toEqual({ url: "https://override.example/check" });
  expect(screen.getAllByRole("alert")).toHaveLength(1);
  expect((row("Alpha").getByLabelText("Test URL") as HTMLInputElement).value).toBe(
    "https://override.example/check",
  );
});

it.each(["https://identity.example/authorize?state=returned", "javascript:alert(1)"])(
  "uses only a confirmed web authorization address: %s",
  async (authorizeUrl) => {
    server.use(
      http.get("*/api/v1/service-connections", () =>
        HttpResponse.json({
          items: [{ id: "oauth", name: "Saved OAuth", kind: "oauth_authorization_code" }],
        }),
      ),
      http.post("*/api/v1/service-connections/oauth:authorize", () =>
        HttpResponse.json({ authorizeUrl }),
      ),
    );
    render(view());
    fireEvent.click(await screen.findByRole("button", { name: "Authorise" }));
    if (authorizeUrl.startsWith("https:")) {
      expect(
        (
          await screen.findByRole("link", { name: "Continue sign-in for Saved OAuth" })
        ).getAttribute("href"),
      ).toBe(authorizeUrl);
    } else {
      await screen.findByText(messages.connections.authorizationUnconfirmed);
      expect(screen.queryByRole("link", { name: "Continue sign-in for Saved OAuth" })).toBeNull();
    }
  },
);

it("serializes a local expiry as an actual instant and clears only acknowledged secrets", async () => {
  let saved: Record<string, unknown> | undefined;
  server.use(
    http.post("*/api/v1/service-connections", async ({ request }) => {
      saved = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ id: "saved" });
    }),
  );
  render(view());
  await screen.findByText(messages.connections.serviceEmpty);
  fireEvent.click(screen.getByText("Add a service connection"));
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Saved service" } });
  fireEvent.change(screen.getByLabelText("Bearer token"), {
    target: { value: "test-only-secret" },
  });
  fireEvent.change(screen.getByLabelText("Expires"), { target: { value: "2026-12-01T09:30" } });
  fireEvent.click(screen.getByRole("button", { name: "Save connection" }));
  await waitFor(() => expect(saved?.expiresAt).toBe(new Date("2026-12-01T09:30").toISOString()));
  expect((screen.getByLabelText("Bearer token") as HTMLInputElement).value).toBe("");
});

it("allows clearing number fields and validates the database form without silently replacing their values", async () => {
  let writes = 0;
  let saved: Record<string, unknown> | undefined;
  server.use(
    http.post("*/api/v1/data-connections", async ({ request }) => {
      writes += 1;
      saved = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ id: "db" });
    }),
    http.post("*/api/v1/data-connections/db:test", () => HttpResponse.json({ ok: true })),
  );
  render(view());
  await screen.findByRole("tab", { name: "Database connections" });
  await waitFor(() => expect(screen.queryByText(messages.detail.working)).toBeNull());
  tab("Database connections");
  fireEvent.click(screen.getByText("Add a database connection"));
  fireEvent.change(screen.getByLabelText("Database name"), { target: { value: "My database" } });
  fireEvent.change(screen.getByLabelText("Connection string"), {
    target: { value: "test-only-input" },
  });
  const input = screen.getByLabelText("Row limit") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "" } });
  expect(input.value).toBe("");
  const form = input.closest("form");
  if (!form) throw new Error("Database controls need a form");
  fireEvent.submit(form);
  expect(writes).toBe(0);
  fireEvent.change(input, { target: { value: "12.5" } });
  fireEvent.submit(form);
  expect(writes).toBe(0);
  fireEvent.change(input, { target: { value: "10000" } });
  fireEvent.change(screen.getByLabelText("Timeout (seconds)"), { target: { value: "300" } });
  fireEvent.submit(form);
  await waitFor(() => expect(writes).toBe(1));
  expect(saved?.rowLimit).toBe(10000);
  expect(saved?.statementTimeoutS).toBe(300);
});

it("honours a provider deep link using the actual saved catalogue without starting sign-in", async () => {
  window.history.replaceState(null, "", "/connections?provider=second-provider");
  server.use(
    http.get("*/api/v1/credential-providers", () =>
      HttpResponse.json({
        items: [
          { id: "a", name: "First provider", slug: "first-provider" },
          { id: "b", name: "Second provider", slug: "second-provider" },
        ],
      }),
    ),
  );
  render(view());
  await screen.findByText("Second provider", { exact: true });
  expect(screen.getByRole("tab", { name: "Personal accounts" }).getAttribute("aria-selected")).toBe(
    "true",
  );
  expect(screen.queryByText("First provider", { exact: true })).toBeNull();
  expect(screen.queryByRole("link", { name: /Continue sign-in/ })).toBeNull();
});

it("keeps an acknowledged database saved when its test fails and refreshes only through reads", async () => {
  let creates = 0;
  let tests = 0;
  let reads = 0;
  const databases: Record<string, unknown>[] = [];
  server.use(
    http.get("*/api/v1/data-connections", () => {
      reads += 1;
      return HttpResponse.json({ items: databases });
    }),
    http.post("*/api/v1/data-connections", () => {
      creates += 1;
      databases.push({ id: "saved-db", name: "Saved database", engine: "postgres" });
      return HttpResponse.json({ id: "saved-db" });
    }),
    http.post("*/api/v1/data-connections/saved-db:test", () => {
      tests += 1;
      return HttpResponse.json({ ok: false, error: "Database password rejected" });
    }),
  );
  render(view());
  await screen.findByText(messages.connections.serviceEmpty);
  tab("Database connections");
  fireEvent.click(screen.getByText("Add a database connection"));
  fireEvent.change(screen.getByLabelText("Database name"), { target: { value: "Saved database" } });
  fireEvent.change(screen.getByLabelText("Connection string"), {
    target: { value: "test-only-connection-string" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save database" }));
  await screen.findByText("Database password rejected");
  expect(screen.getByText(messages.connections.databaseSaved)).toBeTruthy();
  expect(screen.queryByText(messages.connections.databaseTested)).toBeNull();
  expect((screen.getByLabelText("Connection string") as HTMLInputElement).value).toBe("");
  const previousReads = reads;
  fireEvent.click(screen.getByRole("button", { name: "Refresh lists" }));
  await waitFor(() => expect(reads).toBeGreaterThan(previousReads));
  expect(creates).toBe(1);
  expect(tests).toBe(1);
});

it("aborts a pending database creation on unmount and never tests its late receipt", async () => {
  let release = (_value: Response) => {};
  const pending = new Promise<Response>((resolve) => {
    release = resolve;
  });
  let signal: AbortSignal | null | undefined;
  const originalFetch = globalThis.fetch;
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    if (String(input) === "/api/v1/data-connections" && init?.method === "POST") {
      signal = init.signal;
      return pending;
    }
    return originalFetch(input, init);
  });
  let tests = 0;
  server.use(
    http.post("*/api/v1/data-connections/old-db:test", () => {
      tests += 1;
      return HttpResponse.json({ ok: true });
    }),
  );
  const rendered = render(view());
  await screen.findByText(messages.connections.serviceEmpty);
  tab("Database connections");
  fireEvent.click(screen.getByText("Add a database connection"));
  fireEvent.change(screen.getByLabelText("Database name"), { target: { value: "Old draft" } });
  fireEvent.change(screen.getByLabelText("Connection string"), {
    target: { value: "test-only-old-connection-string" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save database" }));
  await waitFor(() => expect(signal).toBeDefined());
  rendered.unmount();
  expect(signal?.aborted).toBe(true);
  render(view());
  await screen.findByText(messages.connections.serviceEmpty);
  await act(async () => {
    release(HttpResponse.json({ id: "old-db" }));
    await pending;
  });
  expect(tests).toBe(0);
  expect(screen.queryByText(messages.connections.databaseSaved)).toBeNull();
});

it("shows loading instead of an empty catalogue before the initial reads settle", async () => {
  let finish = () => {};
  let started = false;
  const pending = new Promise<void>((resolve) => {
    finish = resolve;
  });
  server.use(
    http.get("*/api/v1/service-connections", async () => {
      started = true;
      await pending;
      return HttpResponse.json({ items: [] });
    }),
  );
  render(view());
  await waitFor(() => expect(started).toBe(true));
  expect(screen.getByText(messages.detail.loading)).toBeTruthy();
  expect(screen.queryByText(messages.connections.serviceEmpty)).toBeNull();
  finish();
  await screen.findByText(messages.connections.serviceEmpty);
  expect(screen.queryByText(messages.detail.loading)).toBeNull();
});
