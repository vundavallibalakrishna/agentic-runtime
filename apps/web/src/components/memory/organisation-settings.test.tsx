import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OrganisationMemorySettings } from "@/components/memory/organisation-settings";
import { clearCachedSession } from "@/lib/session";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const t = messages.memory;
type Settings = { enabled: boolean; extraction: boolean; extractionInstructions: string };
function registry(values: Partial<Settings> = {}) {
  const state = {
    settings: {
      enabled: true,
      extraction: true,
      extractionInstructions: "Keep it short.",
      ...values,
    },
    permissions: ["tenant:read", "tenant:manage"],
    reads: 0,
    writes: [] as unknown[],
    failRead: false,
  };
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: state.permissions })),
    http.get("*/api/v1/tenant", () => {
      state.reads += 1;
      return state.failRead
        ? HttpResponse.json({ detail: "Settings unavailable" }, { status: 503 })
        : HttpResponse.json({ settings: { memory: state.settings } });
    }),
    http.patch("*/api/v1/tenant", async ({ request }) => {
      const body = (await request.json()) as { settings: { memory: Partial<Settings> } };
      state.writes.push(body);
      state.settings = { ...state.settings, ...body.settings.memory };
      return HttpResponse.json({ settings: { memory: state.settings } });
    }),
  );
  return state;
}
function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <OrganisationMemorySettings />
    </NextIntlClientProvider>,
  );
}
const guidance = () => screen.getByLabelText(t.orgInstructions) as HTMLTextAreaElement;
const save = () => screen.getByRole("button", { name: t.orgSave });
const extraction = () =>
  screen.getByRole("checkbox", { name: new RegExp(`^${t.orgExtraction}`) }) as HTMLInputElement;
const master = () =>
  screen.getByRole("checkbox", { name: new RegExp(`^${t.orgEnabled}`) }) as HTMLInputElement;
async function ready() {
  await screen.findByLabelText(t.orgInstructions);
}
afterEach(() => vi.restoreAllMocks());

describe("organisation memory settings", () => {
  it("shows saved preferences and saves changed guidance/automatic remembering without resending the master switch", async () => {
    const state = registry();
    show();
    await ready();
    expect(guidance().value).toBe("Keep it short.");
    expect(master().checked).toBe(true);
    expect(extraction().checked).toBe(true);
    expect(save().matches(":disabled")).toBe(true);
    fireEvent.change(guidance(), { target: { value: " Avoid personal details. " } });
    fireEvent.click(extraction());
    fireEvent.click(save());
    await screen.findByText(t.orgSaved);
    expect(state.writes).toEqual([
      {
        settings: {
          memory: { extraction: false, extractionInstructions: "Avoid personal details." },
        },
      },
    ]);
    expect(guidance().value).toBe("Avoid personal details.");
    expect(save().matches(":disabled")).toBe(true);
  });

  it("distinguishes the master switch from the automatic preference and retains the preference while disabled", async () => {
    const state = registry();
    show();
    await ready();
    fireEvent.click(master());
    expect(extraction().checked).toBe(true);
    expect(extraction().matches(":disabled")).toBe(true);
    expect(screen.getByText(t.orgPaused)).toBeTruthy();
    fireEvent.click(save());
    await screen.findByText(t.orgSaved);
    expect(state.writes).toEqual([{ settings: { memory: { enabled: false } } }]);
    expect(state.settings.extraction).toBe(true);
    fireEvent.click(master());
    expect(extraction().checked).toBe(true);
    expect(extraction().matches(":disabled")).toBe(false);
    expect(screen.queryByText(t.orgSaved)).toBeNull();
  });

  it("clears instructions explicitly, preserves untouched concurrent settings and resets local drafts without a write", async () => {
    const state = registry();
    show();
    await ready();
    state.settings.enabled = false;
    fireEvent.change(guidance(), { target: { value: "" } });
    fireEvent.click(save());
    await screen.findByText(t.orgSaved);
    expect(state.writes).toEqual([{ settings: { memory: { extractionInstructions: "" } } }]);
    expect(master().checked).toBe(false);
    expect(state.settings.enabled).toBe(false);
    fireEvent.change(guidance(), { target: { value: "Next draft" } });
    fireEvent.click(screen.getByRole("button", { name: t.orgUseSaved }));
    expect(guidance().value).toBe("");
    expect(state.writes).toHaveLength(1);
  });

  it.each([
    undefined,
    { settings: { memory: { enabled: true, extraction: true, extractionInstructions: "Other" } } },
  ])(
    "holds an incomplete/mismatched acknowledgement and recovers without replaying the save",
    async (receipt) => {
      const state = registry();
      let writes = 0;
      server.use(
        http.patch("*/api/v1/tenant", () => {
          writes += 1;
          return receipt === undefined
            ? new HttpResponse(null, { status: 204 })
            : HttpResponse.json(receipt);
        }),
      );
      show();
      await ready();
      fireEvent.change(guidance(), { target: { value: "Kept draft" } });
      fireEvent.click(save());
      await screen.findByText(t.orgUnconfirmed);
      await waitFor(() => expect(screen.getByRole("alert")).toBe(document.activeElement));
      expect(screen.queryByText(t.orgSaved)).toBeNull();
      expect(guidance().value).toBe("Kept draft");
      expect(save().matches(":disabled")).toBe(true);
      state.failRead = true;
      fireEvent.click(screen.getByRole("button", { name: t.orgRefresh }));
      await screen.findByText("Settings unavailable");
      expect(save().matches(":disabled")).toBe(true);
      state.failRead = false;
      fireEvent.click(screen.getByRole("button", { name: t.orgRefresh }));
      await waitFor(() => expect(screen.queryByText(t.orgRecovery)).toBeNull());
      expect(guidance().value).toBe("Kept draft");
      expect(writes).toBe(1);
      expect(save().matches(":disabled")).toBe(false);
    },
  );

  it("presents a server refusal with retained edits and read-only refresh", async () => {
    registry();
    let writes = 0;
    server.use(
      http.patch("*/api/v1/tenant", () => {
        writes += 1;
        return HttpResponse.json(
          { detail: "CSRF check failed", code: "csrf_failed" },
          { status: 403 },
        );
      }),
    );
    show();
    await ready();
    fireEvent.change(guidance(), { target: { value: "Kept draft" } });
    fireEvent.click(save());
    await screen.findByText(messages.apiErrors.csrf);
    expect(screen.queryByText("CSRF check failed")).toBeNull();
    expect(guidance().value).toBe("Kept draft");
    expect(guidance().matches(":disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: t.orgRefresh }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(guidance().value).toBe("Kept draft");
    expect(writes).toBe(1);
  });

  it("withholds controls on initial failure and retries real metadata without assuming On", async () => {
    const state = registry({ enabled: false });
    state.failRead = true;
    show();
    await screen.findByText("Settings unavailable");
    expect(screen.queryByLabelText(t.orgInstructions)).toBeNull();
    state.failRead = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await ready();
    expect(master().checked).toBe(false);
    expect(extraction().matches(":disabled")).toBe(true);
  });

  it.each([
    {},
    { memory: {} },
    { memory: { enabled: true, extraction: "false", extractionInstructions: "" } },
    { memory: { enabled: true, extraction: true, extractionInstructions: "x".repeat(2001) } },
  ])("rejects missing/malformed settings without invented defaults", async (settings) => {
    registry();
    server.use(http.get("*/api/v1/tenant", () => HttpResponse.json({ settings })));
    show();
    await screen.findByText(t.orgMetadataError);
    expect(screen.queryByLabelText(t.orgInstructions)).toBeNull();
  });

  it.each([["tenant:manage"], ["tenant:read"], []])(
    "gates private reads on permissions %j",
    async (...permissions) => {
      const state = registry();
      state.permissions = permissions;
      show();
      await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
      expect(state.reads).toBe(0);
      expect(screen.queryByLabelText(t.orgInstructions)).toBeNull();
    },
  );

  it("removes protected controls after explicit read access loss and rechecks permissions on refresh", async () => {
    const state = registry();
    show();
    await ready();
    server.use(
      http.get("*/api/v1/tenant", () =>
        HttpResponse.json({ detail: "Access removed" }, { status: 403 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: t.orgRefresh }));
    await screen.findByText("Access removed");
    expect(screen.queryByLabelText(t.orgInstructions)).toBeNull();
    clearCachedSession();
    state.permissions = [];
    fireEvent.click(screen.getByRole("button", { name: t.orgRefresh }));
    await waitFor(() => expect(screen.queryByRole("button", { name: t.orgRefresh })).toBeNull());
    expect(state.reads).toBe(1);
  });

  it("accepts the 2,000-character limit, shows its count and refuses an oversized programmatic submit", async () => {
    const state = registry();
    show();
    await ready();
    expect(guidance().maxLength).toBe(4000);
    fireEvent.change(guidance(), { target: { value: "x".repeat(2000) } });
    expect(screen.getByText("2,000 / 2,000 characters")).toBeTruthy();
    fireEvent.click(save());
    await screen.findByText(t.orgSaved);
    expect(state.settings.extractionInstructions).toHaveLength(2000);
    fireEvent.change(guidance(), { target: { value: "x".repeat(2001) } });
    fireEvent.submit(save().closest("form") as HTMLFormElement);
    expect(state.writes).toHaveLength(1);
  });

  it("counts non-BMP characters using the API character limit", async () => {
    const state = registry();
    show();
    await ready();
    fireEvent.change(guidance(), { target: { value: "🌱".repeat(2000) } });
    expect(screen.getByText("2,000 / 2,000 characters")).toBeTruthy();
    fireEvent.click(save());
    await screen.findByText(t.orgSaved);
    expect(Array.from(state.settings.extractionInstructions)).toHaveLength(2000);
    fireEvent.change(guidance(), { target: { value: "🌱".repeat(2001) } });
    expect(guidance().getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText("Use 2,000 characters or fewer.")).toBeTruthy();
    expect(save().matches(":disabled")).toBe(true);
  });

  it("coordinates same-frame submissions and aborts a pending save on unmount", async () => {
    registry();
    const original = globalThis.fetch;
    let writes = 0;
    let signal: AbortSignal | null = null;
    let finish: (response: Response) => void = () => undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (init?.method === "PATCH") {
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
    fireEvent.change(guidance(), { target: { value: "Draft" } });
    const form = save().closest("form") as HTMLFormElement;
    act(() => {
      fireEvent.submit(form);
      fireEvent.submit(form);
    });
    expect(writes).toBe(1);
    expect(guidance().matches(":disabled")).toBe(true);
    view.unmount();
    expect((signal as AbortSignal | null)?.aborted).toBe(true);
    await act(async () => {
      finish(
        new Response(
          JSON.stringify({
            settings: {
              memory: { enabled: true, extraction: true, extractionInstructions: "Draft" },
            },
          }),
        ),
      );
    });
    expect(screen.queryByText(t.orgSaved)).toBeNull();
  });
});
