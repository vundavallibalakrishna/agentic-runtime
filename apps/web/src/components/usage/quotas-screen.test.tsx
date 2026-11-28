import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { QuotasScreen } from "@/components/usage/quotas-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/quotas",
  useRouter: () => ({ push: () => undefined }),
}));
afterEach(() => window.localStorage.clear());
const rule = (id = "rule", extra: Record<string, unknown> = {}) => ({
  id,
  metric: "runs",
  period: "day",
  scopeType: "tenant",
  scope: null,
  limitValue: 10,
  used: 3,
  action: "block",
  warnAtPct: 80,
  implicit: false,
  ...extra,
});
const show = () =>
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <QuotasScreen />
    </NextIntlClientProvider>,
  );
const form = () => within(within(screen.getByRole("main")).getByRole("complementary"));
function setup(
  items: object[] = [],
  permissions = ["usage:read", "quotas:manage", "users:read", "agents:read"],
) {
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions })),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/quotas", () => HttpResponse.json({ items })),
    http.get("*/api/v1/teams", () =>
      HttpResponse.json({ data: [{ id: "team-id", name: "Product team" }], nextCursor: null }),
    ),
    http.get("*/api/v1/agents", () =>
      HttpResponse.json({ items: [{ id: "agent-id", name: "Workspace assistant" }] }),
    ),
    http.get("*/api/v1/users", () =>
      HttpResponse.json({
        data: [
          { id: "person-id", displayName: "Workspace member", email: "member@workspace.invalid" },
        ],
        nextCursor: null,
      }),
    ),
  );
}

describe("quota controls", () => {
  it("bounds a long list, searches named targets and combines filters before paging", async () => {
    setup(
      Array.from({ length: 30 }, (_, i) =>
        rule(`rule-${i}`, {
          scopeType: "agent",
          scope: { id: `agent-${i}`, name: `Target ${i}` },
          metric: i % 2 ? "runs" : "tool_calls",
          period: i % 3 ? "day" : "month",
          action: i % 4 ? "block" : "warn",
        }),
      ),
    );
    show();
    await screen.findByText("Target 0");
    const main = within(screen.getByRole("main"));
    expect(main.getAllByRole("listitem")).toHaveLength(25);
    expect(screen.queryByText("Target 29")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Target 29")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.quotas.search }), {
      target: { value: "agent-29" },
    });
    expect(main.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByText("1–1 of 1")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "" } });
    fireEvent.change(
      within(screen.getByRole("group", { name: "Quota filters" })).getByRole("combobox", {
        name: "What to limit",
      }),
      {
        target: { value: "runs" },
      },
    );
    expect(main.getAllByRole("listitem")).toHaveLength(15);
    fireEvent.change(
      within(screen.getByRole("group", { name: "Quota filters" })).getByRole("combobox", {
        name: "Period",
      }),
      {
        target: { value: "month" },
      },
    );
    expect(main.getAllByRole("listitem")).toHaveLength(5);
    fireEvent.change(
      within(screen.getByRole("group", { name: "Quota filters" })).getByRole("combobox", {
        name: "When full",
      }),
      {
        target: { value: "warn" },
      },
    );
    expect(screen.getByText(messages.quotas.noMatches)).toBeTruthy();
  });

  it("sends named team, agent and person targets and clears them for a workspace rule", async () => {
    setup();
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/v1/quotas", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        bodies.push(body);
        return HttpResponse.json(
          rule(`saved-${bodies.length}`, {
            ...body,
            scope: body.scopeId ? { id: body.scopeId } : null,
          }),
          { status: 201 },
        );
      }),
    );
    show();
    await screen.findByText(messages.quotas.empty);
    for (const [scope, label, name, id, type] of [
      ["team", "Team", "Product team", "team-id", "team"],
      ["agent", "Agent", "Workspace assistant", "agent-id", "agent"],
      ["person", "One person", "Workspace member", "person-id", "user"],
    ] as const) {
      fireEvent.change(form().getByRole("combobox", { name: "Applies to" }), {
        target: { value: scope },
      });
      expect(
        (form().getByRole("button", { name: "Save quota" }) as HTMLButtonElement).disabled,
      ).toBe(true);
      fireEvent.click(form().getByRole("button", { name: `${label}: Choose existing` }));
      const picker = within(screen.getByRole("dialog"));
      if (scope === "person")
        fireEvent.change(picker.getByRole("searchbox"), {
          target: { value: "member@workspace.invalid" },
        });
      fireEvent.click(await picker.findByText(name));
      fireEvent.change(form().getByLabelText("Limit"), { target: { value: "10000" } });
      fireEvent.click(form().getByRole("button", { name: "Save quota" }));
      await waitFor(() =>
        expect(bodies).toHaveLength(scope === "team" ? 1 : scope === "agent" ? 2 : 3),
      );
      await waitFor(() =>
        expect(form().getByRole("combobox", { name: "Applies to" })).toHaveProperty(
          "value",
          "user",
        ),
      );
      expect(bodies.at(-1)).toEqual({
        scopeType: type,
        scopeId: id,
        metric: "model_tokens",
        period: "day",
        limitValue: 10000,
      });
    }
    fireEvent.change(form().getByRole("combobox", { name: "Applies to" }), {
      target: { value: "agent" },
    });
    fireEvent.click(form().getByRole("button", { name: "Agent: Choose existing" }));
    fireEvent.click(await within(screen.getByRole("dialog")).findByText("Workspace assistant"));
    fireEvent.change(form().getByRole("combobox", { name: "Applies to" }), {
      target: { value: "tenant" },
    });
    expect(form().queryByRole("button", { name: /^Agent:/ })).toBeNull();
    fireEvent.change(form().getByLabelText("Limit"), { target: { value: "10000" } });
    fireEvent.click(form().getByRole("button", { name: "Save quota" }));
    await waitFor(() => expect(bodies).toHaveLength(4));
    expect(bodies.at(-1)).toMatchObject({ scopeType: "tenant", scopeId: null });
  });

  it("edits only supported fields, moves focus to the form and retains a failed edit", async () => {
    setup([rule("existing", { action: "warn", warnAtPct: 70 })]);
    const changes: unknown[] = [];
    server.use(
      http.patch("*/api/v1/quotas/existing", async ({ request }) => {
        changes.push(await request.json());
        return changes.length === 1
          ? HttpResponse.json({ detail: "Save unavailable" }, { status: 503 })
          : HttpResponse.json(rule("existing", { limitValue: 25, action: "warn", warnAtPct: 70 }));
      }),
    );
    show();
    const editButton = await screen.findByRole("button", { name: /^Edit quota / });
    fireEvent.click(editButton);
    fireEvent.click(form().getByRole("button", { name: "Cancel edit" }));
    expect(document.activeElement).toBe(editButton);
    expect(changes).toHaveLength(0);
    fireEvent.click(editButton);
    expect(document.activeElement).toBe(form().getByLabelText("Limit"));
    expect(
      (form().getByRole("combobox", { name: "What to limit" }) as HTMLSelectElement).disabled,
    ).toBe(true);
    expect(form().getByText("When full: Warn only. Warn at 70%.")).toBeTruthy();
    fireEvent.change(form().getByLabelText("Limit"), { target: { value: "25" } });
    fireEvent.click(form().getByRole("button", { name: "Save changes" }));
    await form().findByText("Save unavailable");
    expect((form().getByLabelText("Limit") as HTMLInputElement).value).toBe("25");
    fireEvent.click(
      screen.getAllByRole("button", { name: messages.quotas.refresh })[0] as HTMLElement,
    );
    await screen.findByText(messages.quotas.checked);
    fireEvent.click(form().getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(changes).toHaveLength(2));
    expect(changes).toEqual(Array(2).fill({ limitValue: 25 }));
    await screen.findByRole("heading", { name: "Add a quota" });
  });

  it("rejects blank, fractional and unsafe limits and invalid hidden warnings", async () => {
    setup();
    let writes = 0;
    server.use(
      http.post("*/api/v1/quotas", () => {
        writes++;
        return HttpResponse.json(rule());
      }),
    );
    show();
    await screen.findByText(messages.quotas.empty);
    const input = form().getByLabelText("Limit") as HTMLInputElement;
    const formElement = input.closest("form");
    if (!formElement) throw new Error("Quota input is missing its form");
    for (const value of ["", "-1", "0.5", "9007199254740992"]) {
      fireEvent.change(input, { target: { value } });
      expect(input.checkValidity()).toBe(false);
      fireEvent.submit(formElement);
      expect(screen.getByText(messages.quotas.invalidLimit)).toBeTruthy();
    }
    fireEvent.change(input, { target: { value: "0" } });
    expect(form().getByText(/A zero limit blocks immediately/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    fireEvent.change(form().getByLabelText("Warn at percent"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Simple" }));
    fireEvent.submit(formElement);
    expect(screen.getByText(messages.quotas.invalidWarn)).toBeTruthy();
    expect(writes).toBe(0);
  });

  it("keeps plan quotas immutable and hides all management controls for a reader", async () => {
    setup(
      [rule("plan", { implicit: true }), rule("custom", { scopeType: "user" })],
      ["usage:read"],
    );
    show();
    await screen.findByText(/Included with the plan/);
    expect(screen.queryByRole("button", { name: /^Edit quota / })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Remove quota / })).toBeNull();
    expect(within(screen.getByRole("main")).queryByRole("complementary")).toBeNull();
    expect(screen.getByText(messages.quotas.eachPersonUsage)).toBeTruthy();
    expect(screen.getByRole("option", { name: "People" })).toBeTruthy();
    expect(screen.getByText(messages.quotas.readOnly)).toBeTruthy();
  });

  it("guards duplicate removals and keeps the rule when removal fails", async () => {
    setup([rule()]);
    let attempts = 0;
    server.use(
      http.delete("*/api/v1/quotas/rule", () => {
        attempts++;
        return HttpResponse.json({ detail: "Removal unavailable" }, { status: 503 });
      }),
    );
    show();
    fireEvent.click(await screen.findByRole("button", { name: /^Remove quota / }));
    const dialog = within(screen.getByRole("dialog"));
    const confirm = dialog.getByRole("button", { name: messages.quotas.removeConfirm });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    await dialog.findByText("Removal unavailable");
    expect(dialog.getByText("rule", { exact: true })).toBeTruthy();
    expect(attempts).toBe(1);
    fireEvent.click(dialog.getByRole("button", { name: messages.quotas.cancelRemove }));
    expect(screen.getByRole("heading", { name: "Agent runs · Day" })).toBeTruthy();
  });

  it("does not request quotas without usage-read permission", async () => {
    setup([], ["chat:use"]);
    let reads = 0;
    server.use(
      http.get("*/api/v1/quotas", () => {
        reads++;
        return HttpResponse.json({ items: [] });
      }),
    );
    show();
    await screen.findByText(messages.quotas.denied);
    expect(reads).toBe(0);
    expect(screen.queryByRole("button", { name: "Save quota" })).toBeNull();
  });
  it("never offers edit or remove for an included plan rule", async () => {
    setup([rule("included", { implicit: true })]);
    show();
    await screen.findByText(/Included with the plan/);
    expect(screen.queryByRole("button", { name: /^Edit quota / })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Remove quota / })).toBeNull();
    expect(screen.getByRole("button", { name: "Save quota" })).toBeTruthy();
  });
  it("explains a spend limit in currency units without changing its wire units", async () => {
    setup();
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/v1/quotas", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        bodies.push(body);
        return HttpResponse.json(
          rule(`saved-${bodies.length}`, {
            ...body,
            scope: body.scopeId ? { id: body.scopeId } : null,
          }),
          { status: 201 },
        );
      }),
    );
    show();
    await screen.findByText(messages.quotas.empty);
    fireEvent.change(form().getByRole("combobox", { name: "What to limit" }), {
      target: { value: "cost_micros" },
    });
    fireEvent.change(form().getByLabelText(messages.quotas.spendLimit), { target: { value: "1" } });
    expect(form().getByText(messages.quotas.limitHelp.cost_micros)).toBeTruthy();
    fireEvent.click(form().getByRole("button", { name: "Save quota" }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toMatchObject({ metric: "cost_micros", limitValue: 1000000 });
  });
});
