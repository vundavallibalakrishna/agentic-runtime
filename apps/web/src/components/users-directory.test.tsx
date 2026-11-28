import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { UsersDirectory } from "@/components/users-directory";
import { formatDateTime } from "@/lib/format";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const person = {
  id: "user-1",
  email: "alex@example.test",
  displayName: "Alex Example",
  status: "active",
  lastLoginAt: null,
};
function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <UsersDirectory />
    </NextIntlClientProvider>,
  );
}
function refresh() {
  fireEvent.click(screen.getByRole("button", { name: "Refresh users" }));
}
beforeEach(() => {
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["users:read"] })),
    http.get("*/api/v1/users", () => HttpResponse.json({ items: [person] })),
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("workspace users directory", () => {
  it("shows supplied status and distinguishes an absent sign-in record", async () => {
    show();
    await screen.findByRole("cell", { name: person.displayName });
    expect(screen.getByRole("cell", { name: "Active" })).toBeTruthy();
    expect(screen.getByText(messages.directory.noSignIn)).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Account status" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Users" })).toBeTruthy();
  });
  it("lets a manager suspend someone else, then reloads, and never offers it on their own row", async () => {
    const other = { ...person, id: "user-2", email: "mo@example.test", displayName: "Mo Member" };
    let rows = [person, other];
    const patch = vi.fn(async ({ request }: { request: Request }) => {
      const body = (await request.json()) as { status: string };
      rows = rows.map((row) => (row.id === "user-2" ? { ...row, status: body.status } : row));
      return HttpResponse.json({ ...other, status: body.status });
    });
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ user: { id: "user-1" }, permissions: ["users:read", "users:manage"] }),
      ),
      http.get("*/api/v1/users", () => HttpResponse.json({ items: rows })),
      http.patch("*/api/v1/users/user-2", patch),
    );
    show();
    await screen.findByRole("cell", { name: "Mo Member" });
    expect(screen.queryByRole("button", { name: "Suspend Alex Example" })).toBeNull();
    expect(screen.getByText("(You)")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Suspend Mo Member" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, suspend" }));
    await screen.findByRole("button", { name: "Let Mo Member back in" });
    expect(patch).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("cell", { name: "Suspended" })).toBeTruthy();
  });
  it("shows real instants in the viewer zone and uses the email for an empty display name", async () => {
    const instant = "2026-11-01T05:30:00+05:30";
    server.use(
      http.get("*/api/v1/users", () =>
        HttpResponse.json({ items: [{ ...person, displayName: "", lastLoginAt: instant }] }),
      ),
    );
    show();
    await screen.findByRole("cell", { name: formatDateTime(instant, "en") });
    expect(screen.getAllByRole("cell", { name: person.email })).toHaveLength(2);
    expect(screen.getByText(formatDateTime(instant, "en")).getAttribute("datetime")).toBe(instant);
  });
  it("does not request private users without permission", async () => {
    const read = vi.fn(() => HttpResponse.json({ items: [person] }));
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: [] })),
      http.get("*/api/v1/users", read),
    );
    show();
    await screen.findByText(messages.admin.forbidden);
    expect(read).not.toHaveBeenCalled();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByText(messages.admin.empty)).toBeNull();
  });
  it("provides retry for an initial failure without claiming the directory is empty", async () => {
    server.use(
      http.get("*/api/v1/users", () =>
        HttpResponse.json({ detail: "Directory unavailable" }, { status: 503 }),
      ),
    );
    show();
    await screen.findByText("Directory unavailable");
    expect(screen.queryByText(messages.admin.empty)).toBeNull();
    server.use(http.get("*/api/v1/users", () => HttpResponse.json({ items: [person] })));
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("cell", { name: person.email });
    expect(screen.queryByRole("alert")).toBeNull();
  });
  it("retains filters and the last directory after a failed read-only refresh", async () => {
    show();
    await screen.findByRole("cell", { name: person.email });
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Alex" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Account status" }), {
      target: { value: "active" },
    });
    server.use(
      http.get("*/api/v1/users", () => HttpResponse.json({ detail: "Try later" }, { status: 503 })),
    );
    refresh();
    await screen.findByText("Try later");
    expect(screen.getByRole("cell", { name: person.email })).toBeTruthy();
    expect(screen.getByText(messages.directory.retained)).toBeTruthy();
    expect((screen.getByRole("searchbox") as HTMLInputElement).value).toBe("Alex");
    expect(
      (screen.getByRole("combobox", { name: "Account status" }) as HTMLSelectElement).value,
    ).toBe("active");
  });
  it.each([401, 403])("clears stale private rows on HTTP %s", async (status) => {
    show();
    await screen.findByRole("cell", { name: person.email });
    server.use(
      http.get("*/api/v1/users", () => HttpResponse.json({ detail: "Access refused" }, { status })),
    );
    refresh();
    await screen.findByText(messages.admin.forbidden);
    expect(screen.queryByRole("cell", { name: person.email })).toBeNull();
    expect(screen.queryByRole("searchbox")).toBeNull();
  });
  it.each([
    {},
    [person],
    { items: [{ ...person, displayName: undefined, display_name: "Unsupported property" }] },
    { items: [{ ...person, lastLoginAt: "2026-11-01T12:00:00" }] },
    { items: [{ ...person, status: undefined }] },
  ])(
    "rejects incomplete account metadata without accepting an empty fallback: %j",
    async (body) => {
      server.use(http.get("*/api/v1/users", () => HttpResponse.json(body)));
      show();
      await screen.findByText(messages.directory.metadataError);
      expect(screen.queryByText(messages.admin.empty)).toBeNull();
      expect(screen.queryByRole("table")).toBeNull();
    },
  );
  it("shows a truthful empty state with a working refresh action", async () => {
    server.use(http.get("*/api/v1/users", () => HttpResponse.json({ items: [] })));
    show();
    await screen.findByText(messages.admin.empty);
    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    server.use(http.get("*/api/v1/users", () => HttpResponse.json({ items: [person] })));
    refresh();
    await screen.findByRole("cell", { name: person.email });
  });
  it("retains a selected returned status when a refresh removes all accounts with it", async () => {
    server.use(
      http.get("*/api/v1/users", () =>
        HttpResponse.json({ items: [{ ...person, status: "awaiting_review" }] }),
      ),
    );
    show();
    await screen.findByRole("cell", { name: person.email });
    fireEvent.change(screen.getByRole("combobox", { name: "Account status" }), {
      target: { value: "awaiting_review" },
    });
    server.use(http.get("*/api/v1/users", () => HttpResponse.json({ items: [person] })));
    refresh();
    await screen.findByText(messages.directory.noMatches);
    expect(
      (screen.getByRole("combobox", { name: "Account status" }) as HTMLSelectElement).value,
    ).toBe("awaiting_review");
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByRole("cell", { name: person.email })).toBeTruthy();
  });
  it("bounds 100,000 loaded users, searches the whole result and resets filters to page one", async () => {
    server.use(
      http.get("*/api/v1/users", () =>
        HttpResponse.json({
          items: Array.from({ length: 100000 }, (_, index) => ({
            ...person,
            id: `user-${index}`,
            displayName: `Person ${index}`,
            email: `person-${index}@example.test`,
            status: index === 99999 ? "suspended" : "active",
          })),
        }),
      ),
    );
    show();
    await screen.findByRole("cell", { name: "Person 0" });
    expect(screen.getAllByRole("row")).toHaveLength(26);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("cell", { name: "Person 25" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Rows per page"), { target: { value: "100" } });
    expect(screen.getAllByRole("row")).toHaveLength(101);
    expect(screen.getByRole("cell", { name: "Person 0" })).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: "Account status" }), {
      target: { value: "suspended" },
    });
    expect(screen.getByRole("cell", { name: "Person 99999" })).toBeTruthy();
    expect(screen.getAllByRole("row")).toHaveLength(2);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Not a person" } });
    expect(screen.getByText(messages.directory.noMatches)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByRole("cell", { name: "Person 0" })).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole("searchbox"));
    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "PERSON-99999@EXAMPLE.TEST" },
    });
    expect(screen.getByRole("cell", { name: "Person 99999" })).toBeTruthy();
  }, 15000);
  it("shows scoped loading, guards repeated refreshes and aborts pending reads on unmount", async () => {
    const nativeFetch = globalThis.fetch;
    const signals: (AbortSignal | null | undefined)[] = [];
    const resolvers: ((response: Response) => void)[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input) === "/api/v1/users") {
        signals.push(init?.signal);
        return new Promise((resolve) => resolvers.push(resolve));
      }
      return nativeFetch(input, init);
    });
    const view = show();
    await waitFor(() => expect(signals).toHaveLength(1));
    expect(document.querySelector('[aria-busy="true"]')).toBeTruthy();
    resolvers[0]?.(Response.json({ items: [person] }));
    await screen.findByRole("cell", { name: person.email });
    refresh();
    refresh();
    await waitFor(() => expect(signals).toHaveLength(2));
    expect(screen.getByText(messages.directory.refreshing)).toBeTruthy();
    expect(screen.getByRole("cell", { name: person.email })).toBeTruthy();
    view.unmount();
    expect(signals[1]?.aborted).toBe(true);
    resolvers[1]?.(Response.json({ items: [] }));
  });
});
