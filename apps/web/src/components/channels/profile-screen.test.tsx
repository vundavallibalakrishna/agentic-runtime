import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfileScreen } from "@/components/channels/profile-screen";
import { formatDateTime } from "@/lib/format";
import { clearCachedSession } from "@/lib/session";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/settings/profile",
  useParams: () => ({}),
  useRouter: () => ({ push: vi.fn() }),
}));
const t = messages.profile;
const identity = (i: number) => ({
  id: `identity-${i}`,
  integrationId: `service-${i}`,
  externalUserId: `External ${i}`,
  userId: "owner",
  matchMethod: i % 2 ? "email" : "manual_link",
  verifiedAt: "2026-11-20T10:00:00Z",
});
const quota = (i: number) => ({
  id: `quota-${i}`,
  metric: "runs",
  period: i % 2 ? "month" : "day",
  used: 2,
  limit: 10,
  resetsAt: "2026-12-01T00:00:00Z",
});
function registry() {
  const state = {
    rows: [] as ReturnType<typeof identity>[],
    quotas: [] as ReturnType<typeof quota>[],
    permissions: ["chat:use"],
    linkReads: 0,
    usageReads: 0,
    writes: [] as string[],
    linkFail: false,
    usageFail: false,
  };
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({
        permissions: state.permissions,
        user: { id: "owner", displayName: "Ada", email: "ada@example.test" },
      }),
    ),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/me/channel-identities", () => {
      state.linkReads += 1;
      return state.linkFail
        ? HttpResponse.json({ detail: "Links unavailable" }, { status: 503 })
        : HttpResponse.json({ items: state.rows });
    }),
    http.get("*/api/v1/me/usage", () => {
      state.usageReads += 1;
      return state.usageFail
        ? HttpResponse.json({ detail: "Usage unavailable" }, { status: 503 })
        : HttpResponse.json({
            currency: "USD",
            totals: { quantity: 3, costMicros: 1_000_000 },
            quotas: state.quotas,
          });
    }),
    http.post("*/api/v1/me/channel-identities:link", async ({ request }) => {
      state.writes.push(`POST ${((await request.json()) as { token: string }).token}`);
      const row = identity(1);
      state.rows = [row];
      return HttpResponse.json(row);
    }),
    http.delete("*/api/v1/me/channel-identities/:id", ({ params }) => {
      state.writes.push(`DELETE ${params.id}`);
      state.rows = state.rows.filter((row) => row.id !== params.id);
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return state;
}
const links = () => within(screen.getByRole("region", { name: t.linksTitle }));
const usage = () => within(screen.getByRole("region", { name: t.usageTitle }));
const show = () =>
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ProfileScreen />
    </NextIntlClientProvider>,
  );
const code = () => screen.getByLabelText(t.code) as HTMLInputElement;
async function ready() {
  await screen.findByLabelText(t.code);
}
async function submit(value = "connect-token") {
  fireEvent.change(code(), { target: { value } });
  fireEvent.submit(code().closest("form") as HTMLFormElement);
}
afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/settings/profile");
});

describe("profile workspace", () => {
  it("shows independent empty links and named usage facts, and conceals a supplied code while removing it from the URL", async () => {
    registry();
    window.history.replaceState(null, "", "/settings/profile?link=signed-code&tab=accounts#links");
    show();
    await ready();
    expect(code().type).toBe("password");
    expect(code().value).toBe("signed-code");
    expect(code().autocomplete).toBe("off");
    expect(window.location.search).toBe("?tab=accounts");
    expect(window.location.hash).toBe("#links");
    expect(links().getByText(t.empty)).toBeTruthy();
    await usage().findByText("$1.00");
    expect(usage().getByText(t.quantity)).toBeTruthy();
    expect(usage().getByText(t.noLimits)).toBeTruthy();
  });

  it.each(["links", "usage"] as const)(
    "keeps the other section available when %s cannot load",
    async (section) => {
      const state = registry();
      state.linkFail = section === "links";
      state.usageFail = section === "usage";
      show();
      if (section === "links") {
        await links().findByText("Links unavailable");
        await usage().findByText("$1.00");
        expect(screen.queryByLabelText(t.code)).toBeNull();
        state.linkFail = false;
        fireEvent.click(links().getByRole("button", { name: t.refreshLinks }));
        await ready();
      } else {
        await ready();
        await usage().findByText("Usage unavailable");
        expect(links().getByRole("button", { name: t.link }).matches(":disabled")).toBe(true);
        state.usageFail = false;
        fireEvent.click(usage().getByRole("button", { name: t.refreshUsage }));
        await usage().findByText("$1.00");
      }
    },
  );

  it("verifies a linked receipt and saved list, then clears the consumed code", async () => {
    const state = registry();
    show();
    await ready();
    await submit("  connect-token  ");
    await links().findByText(t.linked);
    expect(code().value).toBe("");
    expect(links().getByText("External 1")).toBeTruthy();
    expect(state.writes).toEqual(["POST connect-token"]);
    expect(state.linkReads).toBe(2);
    expect(state.usageReads).toBe(1);
  });

  it.each([{}, { ...identity(1), userId: "someone-else" }])(
    "holds an unconfirmed/wrong-owner link response and retains the code through read-only recovery",
    async (receipt) => {
      const state = registry();
      let writes = 0;
      server.use(
        http.post("*/api/v1/me/channel-identities:link", () => {
          writes += 1;
          return HttpResponse.json(receipt);
        }),
      );
      show();
      await ready();
      await submit();
      await links().findByText(t.linkUnconfirmed);
      expect(code().value).toBe("connect-token");
      expect(links().queryByText(t.linked)).toBeNull();
      expect(code().matches(":disabled")).toBe(true);
      fireEvent.click(links().getByRole("button", { name: t.refreshLinks }));
      await links().findByText(t.linksRefreshed);
      expect(code().value).toBe("connect-token");
      expect(code().matches(":disabled")).toBe(false);
      expect(writes).toBe(1);
      expect(state.usageReads).toBe(1);
    },
  );

  it("keeps an acknowledged link distinct from a failed saved-list read and never reposts it on refresh", async () => {
    const state = registry();
    server.use(
      http.post("*/api/v1/me/channel-identities:link", () => {
        state.writes.push("POST");
        state.rows = [identity(1)];
        state.linkFail = true;
        return HttpResponse.json(identity(1));
      }),
    );
    show();
    await ready();
    await submit();
    await links().findByText("Links unavailable");
    expect(links().getByText(t.linkRecorded)).toBeTruthy();
    expect(links().queryByText(t.linked)).toBeNull();
    expect(code().value).toBe("");
    state.linkFail = false;
    fireEvent.click(links().getByRole("button", { name: t.refreshLinks }));
    await links().findByText(t.linked);
    expect(state.writes).toEqual(["POST"]);
  });

  it("refreshes actual state without claiming a link when an acknowledged identity is no longer listed", async () => {
    const state = registry();
    server.use(
      http.post("*/api/v1/me/channel-identities:link", () => {
        state.writes.push("POST");
        return HttpResponse.json(identity(1));
      }),
    );
    show();
    await ready();
    await submit();
    await links().findByText(t.linkUnconfirmed);
    expect(links().queryByText(t.linked)).toBeNull();
    fireEvent.click(links().getByRole("button", { name: t.refreshLinks }));
    await links().findByText(t.linksRefreshed);
    expect(links().queryByText(t.linked)).toBeNull();
    expect(state.writes).toEqual(["POST"]);
    expect(code().matches(":disabled")).toBe(false);
  });

  it("removes protected rows if the follow-up read loses access after an acknowledged link", async () => {
    const state = registry();
    state.rows = [identity(2)];
    let acknowledged = false;
    server.use(
      http.post("*/api/v1/me/channel-identities:link", () => {
        acknowledged = true;
        return HttpResponse.json(identity(1));
      }),
      http.get("*/api/v1/me/channel-identities", () =>
        acknowledged
          ? HttpResponse.json({ detail: "Read access removed" }, { status: 403 })
          : HttpResponse.json({ items: state.rows }),
      ),
    );
    show();
    await ready();
    await submit();
    await links().findByText("Read access removed");
    expect(links().queryByText("External 2")).toBeNull();
    expect(screen.queryByLabelText(t.code)).toBeNull();
    expect(links().queryByText(t.linked)).toBeNull();
    await usage().findByText("$1.00");
  });

  it("does not render a returned identity owned by another user", async () => {
    registry();
    server.use(
      http.get("*/api/v1/me/channel-identities", () =>
        HttpResponse.json({ items: [{ ...identity(1), userId: "someone-else" }] }),
      ),
    );
    show();
    await links().findByText(t.linksMetadataError);
    expect(links().queryByText("External 1")).toBeNull();
    expect(screen.queryByLabelText(t.code)).toBeNull();
  });

  it("explains a real-code refusal without hiding the form or losing its code", async () => {
    const state = registry();
    server.use(
      http.post("*/api/v1/me/channel-identities:link", () => {
        state.writes.push("POST");
        return HttpResponse.json(
          { code: "csrf_failed", detail: "CSRF check failed" },
          { status: 403 },
        );
      }),
    );
    show();
    await ready();
    await submit();
    await links().findByText(messages.apiErrors.csrf);
    await waitFor(() => expect(links().getByRole("alert")).toBe(document.activeElement));
    expect(code().value).toBe("connect-token");
    expect(links().queryByText("CSRF check failed")).toBeNull();
    expect(usage().getByText("$1.00")).toBeTruthy();
    fireEvent.click(links().getByRole("button", { name: t.refreshLinks }));
    await links().findByText(t.linksRefreshed);
    expect(state.writes).toEqual(["POST"]);
    expect(code().value).toBe("connect-token");
  });

  it("confirms unlinking through the saved list and names the affected account", async () => {
    const state = registry();
    state.rows = [identity(1), identity(2)];
    show();
    await ready();
    fireEvent.click(links().getByRole("button", { name: "Unlink External 1 (service-1)" }));
    await links().findByText(t.unlinked);
    expect(links().queryByText("External 1")).toBeNull();
    expect(links().getByText("External 2")).toBeTruthy();
    expect(state.writes).toEqual(["DELETE identity-1"]);
  });

  it("distinguishes the same external id in different integrations and unlinks the exact saved row", async () => {
    const state = registry();
    state.rows = [identity(1), { ...identity(2), externalUserId: "External 1" }];
    show();
    await ready();
    expect(links().getByRole("button", { name: "Unlink External 1 (service-1)" })).toBeTruthy();
    fireEvent.click(links().getByRole("button", { name: "Unlink External 1 (service-2)" }));
    await links().findByText(t.unlinked);
    expect(state.writes).toEqual(["DELETE identity-2"]);
    expect(state.rows.map((row) => row.id)).toEqual(["identity-1"]);
  });

  it("does not claim unlink success when the saved row remains, and refresh never deletes again", async () => {
    const state = registry();
    state.rows = [identity(1)];
    let deletes = 0;
    server.use(
      http.delete("*/api/v1/me/channel-identities/:id", () => {
        deletes += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    show();
    await ready();
    fireEvent.click(links().getByRole("button", { name: "Unlink External 1 (service-1)" }));
    await links().findByText(t.unlinkUnconfirmed);
    expect(links().queryByText(t.unlinked)).toBeNull();
    fireEvent.click(links().getByRole("button", { name: t.refreshLinks }));
    await links().findByText(t.linksRefreshed);
    expect(links().getByText("External 1")).toBeTruthy();
    expect(deletes).toBe(1);
  });

  it("bounds/searches 100,000 linked accounts, filters methods and clears filters together", async () => {
    const state = registry();
    state.rows = Array.from({ length: 100_000 }, (_, i) => identity(i));
    show();
    await ready();
    const list = within(links().getByRole("region", { name: t.savedLinks }));
    expect(list.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.change(list.getByRole("searchbox"), { target: { value: "External 99999" } });
    expect(list.getByText("External 99999")).toBeTruthy();
    expect(list.getAllByRole("listitem")).toHaveLength(1);
    fireEvent.change(list.getByRole("combobox", { name: /^Connection method/ }), {
      target: { value: "manual_link" },
    });
    expect(list.getByText(t.noLinkMatches)).toBeTruthy();
    fireEvent.click(list.getByRole("button", { name: t.clear }));
    expect(list.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.click(list.getByRole("button", { name: "Next" }));
    expect(list.getByText("External 25")).toBeTruthy();
  });

  it("bounds/searches 100,000 quotas and uses period/metric context with zone-labelled resets", async () => {
    const state = registry();
    state.quotas = Array.from({ length: 100_000 }, (_, i) => quota(i));
    show();
    const list = within(await usage().findByRole("region", { name: t.myLimits }));
    expect(list.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.change(list.getByRole("searchbox"), { target: { value: "quota-99999" } });
    expect(list.getAllByRole("listitem")).toHaveLength(1);
    expect(
      list.getByRole("progressbar", { name: "Agent runs (Month): 2 used of 10" }),
    ).toBeTruthy();
    expect(list.getByText(`Resets ${formatDateTime(quota(1).resetsAt)}`)).toBeTruthy();
    fireEvent.change(list.getByRole("combobox", { name: /^Period/ }), { target: { value: "day" } });
    expect(list.getByText(t.noLimitMatches)).toBeTruthy();
    fireEvent.click(list.getByRole("button", { name: t.clear }));
    expect(list.getAllByRole("listitem")).toHaveLength(25);
  });

  it("formats spend quotas as workspace currency without calling their values token counts", async () => {
    const state = registry();
    state.quotas = [{ ...quota(1), metric: "cost_micros", used: 2_000_000, limit: 5_000_000 }];
    show();
    await usage().findByRole("progressbar", { name: "Spend (Month): $2.00 used of $5.00" });
    expect(usage().getByText("Month · $2.00 used / $5.00 limit")).toBeTruthy();
  });

  it("shows personal usage without making account reads when chat permission is absent", async () => {
    const state = registry();
    state.permissions = [];
    show();
    await links().findByText(t.linkPermission);
    await usage().findByText("$1.00");
    expect(state.linkReads).toBe(0);
    expect(screen.queryByLabelText(t.code)).toBeNull();
  });

  it("clears protected accounts on an explicit read failure and rechecks permissions on retry", async () => {
    const state = registry();
    state.rows = [identity(1)];
    show();
    await ready();
    server.use(
      http.get("*/api/v1/me/channel-identities", () =>
        HttpResponse.json({ detail: "Read access removed" }, { status: 403 }),
      ),
    );
    fireEvent.click(links().getByRole("button", { name: t.refreshLinks }));
    await links().findByText("Read access removed");
    expect(links().queryByText("External 1")).toBeNull();
    expect(screen.queryByLabelText(t.code)).toBeNull();
    clearCachedSession();
    state.permissions = [];
    fireEvent.click(links().getByRole("button", { name: t.refreshLinks }));
    await links().findByText(t.linkPermission);
    expect(state.linkReads).toBe(1);
  });

  it.each(["links", "usage"] as const)(
    "does not replace malformed %s metadata with empty or zero data",
    async (section) => {
      registry();
      if (section === "links")
        server.use(http.get("*/api/v1/me/channel-identities", () => HttpResponse.json({})));
      else
        server.use(
          http.get("*/api/v1/me/usage", () => HttpResponse.json({ totals: {}, quotas: [] })),
        );
      show();
      await screen.findByText(section === "links" ? t.linksMetadataError : t.usageMetadataError);
      if (section === "usage") expect(usage().queryByText("$0.00")).toBeNull();
    },
  );

  it("guards same-frame submissions and discards a late result after navigation", async () => {
    registry();
    const original = globalThis.fetch;
    let writes = 0;
    let signal: AbortSignal | null = null;
    let finish: (response: Response) => void = () => undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (init?.method === "POST") {
        writes += 1;
        signal = init.signal as AbortSignal;
        return new Promise<Response>((resolve) => {
          finish = resolve;
        });
      }
      return original(input, init);
    });
    const view = show();
    await ready();
    fireEvent.change(code(), { target: { value: "connect-token" } });
    const form = code().closest("form") as HTMLFormElement;
    act(() => {
      fireEvent.submit(form);
      fireEvent.submit(form);
    });
    expect(writes).toBe(1);
    view.unmount();
    expect((signal as AbortSignal | null)?.aborted).toBe(true);
    await act(async () => {
      finish(new Response(JSON.stringify(identity(1))));
    });
    expect(screen.queryByText(t.linked)).toBeNull();
  });
});
