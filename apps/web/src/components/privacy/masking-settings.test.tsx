import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MaskingSettings } from "@/components/privacy/masking-settings";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

type Body = { settings: { features: Record<string, unknown>; privacy: Record<string, unknown> } };

const DEFAULTS = ["email_address", "credit_card"];
const KINDS = [
  { name: "credit_card", source: "format" },
  { name: "email_address", source: "format" },
  { name: "us_passport", source: "format" },
  { name: "person", source: "language" },
  { name: "brand_new_kind", source: "format" },
];

/** The API as the page uses it: one tenant's masking, read and changed. */
function tenant(permissions: string[] = ["tenant:read", "tenant:manage"]) {
  const state = {
    enabled: true,
    entities: null as string[] | null,
    score: null as number | null,
    patches: [] as Body[],
  };
  const view = () => {
    const masked = state.entities ?? DEFAULTS;
    return {
      enabled: state.enabled,
      usesDefault: state.entities === null,
      minScore: state.score ?? 0.6,
      defaultMinScore: 0.6,
      kinds: KINDS.map((kind) => ({
        ...kind,
        masked: masked.includes(kind.name),
        default: DEFAULTS.includes(kind.name),
      })),
    };
  };
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions })),
    http.get("*/api/v1/tenant/masking", () => HttpResponse.json(view())),
    http.patch("*/api/v1/tenant", async ({ request }) => {
      const body = (await request.json()) as Body;
      state.patches.push(body);
      const privacy = body.settings.privacy;
      if ("redactionEntities" in privacy) {
        state.entities = privacy.redactionEntities as string[] | null;
      }
      if ("redactionMinScore" in privacy) state.score = privacy.redactionMinScore as number | null;
      state.enabled = body.settings.features.piiRedaction !== false;
      return HttpResponse.json({
        settings: {
          features: { piiRedaction: state.enabled },
          privacy: { redactionEntities: state.entities, redactionMinScore: state.score },
        },
      });
    }),
  );
  return Object.assign(state, { view });
}

describe("Masking settings", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("says in Simple mode how many kinds are masked, and saves only the switch", async () => {
    const state = tenant();
    render(wrap(<MaskingSettings advanced={false} />));

    expect(
      await screen.findByText(/The default list is selected. 2 kinds are masked/),
    ).toBeTruthy();
    expect(screen.queryByLabelText("Person's name")).toBeNull();
    fireEvent.click(screen.getByLabelText(/Mask personal data in tool results/));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText(messages.masking.saved)).toBeTruthy();
    // The list is not on the page in Simple mode, so it is not sent and stays the default.
    expect(state.patches).toEqual([
      { settings: { features: { piiRedaction: false }, privacy: {} } },
    ]);
    expect(state.entities).toBeNull();
  });

  it("lets an administrator choose the kinds and the bar in Advanced mode", async () => {
    const state = tenant();
    render(wrap(<MaskingSettings advanced />));

    const card = (await screen.findByLabelText("Payment card number")) as HTMLInputElement;
    expect(card.checked).toBe(true);
    const name = screen.getByLabelText("Person's name") as HTMLInputElement;
    expect(name.checked).toBe(false);
    // A kind the page has no words for is still offered, under its own name.
    expect(screen.getByLabelText("brand_new_kind")).toBeTruthy();
    expect(screen.getByText("Guessed from the sentence")).toBeTruthy();

    fireEvent.click(name);
    fireEvent.click(card);
    fireEvent.change(screen.getByLabelText("How sure a match must be"), {
      target: { value: "0.8" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(state.patches).toHaveLength(1));
    expect(state.patches[0]).toEqual({
      settings: {
        features: { piiRedaction: true },
        privacy: { redactionEntities: ["email_address", "person"], redactionMinScore: 0.8 },
      },
    });

    // With its own list saved, the organisation can go back to the product default.
    fireEvent.click(await screen.findByRole("button", { name: messages.masking.useDefault }));
    expect(await screen.findByText(messages.masking.defaultRestored)).toBeTruthy();
    expect(state.patches[1]?.settings.privacy).toEqual({
      redactionEntities: null,
      redactionMinScore: null,
    });
    expect(screen.queryByRole("button", { name: messages.masking.useDefault })).toBeNull();
  });

  it("shows the settings without controls to someone who cannot manage the organisation", async () => {
    tenant(["tenant:read"]);
    render(wrap(<MaskingSettings advanced />));

    const card = (await screen.findByLabelText("Payment card number")) as HTMLInputElement;
    expect(card.closest("fieldset")?.disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
    expect(screen.getByText(/needs the permission to manage the organisation/)).toBeTruthy();
  });

  it("says so when the settings cannot be loaded, and tries again", async () => {
    let calls = 0;
    tenant();
    server.use(
      http.get("*/api/v1/tenant/masking", () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json(
              { detail: "The masking settings are not available." },
              { status: 503 },
            )
          : HttpResponse.json({
              enabled: true,
              usesDefault: true,
              minScore: 0.6,
              defaultMinScore: 0.6,
              kinds: [],
            });
      }),
    );
    render(wrap(<MaskingSettings advanced={false} />));

    expect(await screen.findByRole("alert")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/0 kinds are masked/)).toBeTruthy();
  });

  it("keeps a refusal on the page in the words the API gave", async () => {
    tenant();
    server.use(
      http.patch("*/api/v1/tenant", () =>
        HttpResponse.json(
          { detail: "These kinds of personal data are not recognised: shoe_size." },
          { status: 422 },
        ),
      ),
    );
    render(wrap(<MaskingSettings advanced />));

    fireEvent.click(await screen.findByRole("button", { name: "Save" }));
    expect(
      await screen.findByText("These kinds of personal data are not recognised: shoe_size."),
    ).toBeTruthy();
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

describe("masking draft and save states", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });
  it("accepts arbitrary supported confidence precision and sends a cleared value as null, not zero", async () => {
    const state = tenant();
    render(wrap(<MaskingSettings advanced />));
    const field = await screen.findByLabelText(messages.masking.score);
    expect(field.getAttribute("step")).toBe("any");
    fireEvent.change(field, { target: { value: "0.67" } });
    expect((field as HTMLInputElement).checkValidity()).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(state.score).toBe(0.67));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save" }).matches(":disabled")).toBe(false),
    );
    fireEvent.change(field, { target: { value: "" } });
    expect(screen.queryByText(messages.masking.saved)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(state.patches).toHaveLength(2));
    expect(state.patches[1]?.settings.privacy.redactionMinScore).toBeNull();
  });
  it("refuses out-of-range advanced confidence before a patch", async () => {
    const state = tenant();
    render(wrap(<MaskingSettings advanced />));
    const field = await screen.findByLabelText(messages.masking.score);
    fireEvent.change(field, { target: { value: "1.1" } });
    const form = screen.getByRole("button", { name: "Save" }).closest("form");
    if (!form) throw new Error("Masking form is required");
    fireEvent.submit(form);
    await screen.findByText(messages.masking.scoreInvalid);
    expect(state.patches).toEqual([]);
  });
  it("preserves hidden advanced drafts when Simple mode saves only the switch", async () => {
    const state = tenant();
    const rendered = render(wrap(<MaskingSettings advanced />));
    fireEvent.click(await screen.findByLabelText("Person's name"));
    rendered.rerender(wrap(<MaskingSettings advanced={false} />));
    fireEvent.click(screen.getByRole("checkbox", { name: /^Mask personal/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText(messages.masking.summaryOff);
    expect(state.patches[0]?.settings.privacy).toEqual({});
    expect(state.entities).toBeNull();
    rendered.rerender(wrap(<MaskingSettings advanced />));
    expect((screen.getByLabelText("Person's name") as HTMLInputElement).checked).toBe(true);
    expect(screen.getByText(messages.masking.unsaved)).toBeTruthy();
  });
  it("holds saving after an incomplete acknowledgement, refreshes without replay and retains choices until explicitly reset", async () => {
    const state = tenant();
    let writes = 0;
    server.use(
      http.patch("*/api/v1/tenant", () => {
        writes++;
        return HttpResponse.json({});
      }),
    );
    render(wrap(<MaskingSettings advanced />));
    fireEvent.click(await screen.findByLabelText("Person's name"));
    fireEvent.change(screen.getByLabelText(messages.masking.score), { target: { value: "0.67" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText(messages.masking.saveUnconfirmed);
    expect(screen.queryByText(messages.masking.saved)).toBeNull();
    expect(screen.getByRole("button", { name: "Save" }).matches(":disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: messages.masking.refresh }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save" }).matches(":disabled")).toBe(false),
    );
    expect((screen.getByLabelText("Person's name") as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText(messages.masking.score) as HTMLInputElement).value).toBe("0.67");
    expect(writes).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: messages.masking.useSaved }));
    expect((screen.getByLabelText("Person's name") as HTMLInputElement).checked).toBe(false);
    expect((screen.getByLabelText(messages.masking.score) as HTMLInputElement).value).toBe("0.6");
    expect(state.patches).toEqual([]);
  });
  it("retains a verified save receipt when reading its effective settings fails", async () => {
    const state = tenant();
    let fail = true;
    server.use(
      http.get("*/api/v1/tenant/masking", () =>
        state.patches.length && fail
          ? HttpResponse.json({ detail: "effective settings unavailable" }, { status: 503 })
          : HttpResponse.json(state.view()),
      ),
    );
    render(wrap(<MaskingSettings advanced />));
    fireEvent.click(await screen.findByLabelText("Person's name"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("effective settings unavailable");
    expect(screen.getByText(messages.masking.saved)).toBeTruthy();
    expect(screen.getByText(messages.masking.acceptedRecovery)).toBeTruthy();
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: messages.masking.refresh }));
    await waitFor(() => expect(screen.queryByText("effective settings unavailable")).toBeNull());
    expect(state.patches).toHaveLength(1);
    expect((screen.getByLabelText("Person's name") as HTMLInputElement).checked).toBe(true);
  });
  it("offers default restoration when only the confidence differs from the default", async () => {
    const state = tenant();
    state.score = 0.67;
    render(wrap(<MaskingSettings advanced />));
    fireEvent.click(await screen.findByRole("button", { name: messages.masking.useDefault }));
    await screen.findByText(messages.masking.defaultRestored);
    expect(state.patches[0]?.settings.privacy).toEqual({
      redactionEntities: null,
      redactionMinScore: null,
    });
  });
  it("guards same-frame save/default requests and cancels a pending patch on unmount", async () => {
    const state = tenant();
    state.entities = ["person"];
    const pending = deferred<Response>();
    const nativeFetch = globalThis.fetch;
    let writes = 0;
    let signal: AbortSignal | null | undefined;
    let reads = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PATCH") {
          writes++;
          signal = init.signal;
          return pending.promise;
        }
        if (String(input).endsWith("/masking")) reads++;
        return nativeFetch(input, init);
      }),
    );
    const rendered = render(wrap(<MaskingSettings advanced />));
    const save = await screen.findByRole("button", { name: "Save" });
    const form = save.closest("form");
    if (!form) throw new Error("Masking form is required");
    act(() => {
      fireEvent.submit(form);
      fireEvent.submit(form);
      fireEvent.click(screen.getByRole("button", { name: messages.masking.useDefault }));
    });
    expect(writes).toBe(1);
    rendered.unmount();
    expect(signal?.aborted).toBe(true);
    const beforeReads = reads;
    await act(async () =>
      pending.resolve(
        answer({
          settings: {
            features: { piiRedaction: true },
            privacy: { redactionEntities: ["person"], redactionMinScore: 0.6 },
          },
        }),
      ),
    );
    expect(reads).toBe(beforeReads);
  });
  it("searches 100,000 returned kinds, includes new detection methods and preserves off-page choices", async () => {
    const state = tenant();
    server.use(
      http.get("*/api/v1/tenant/masking", () => {
        const selected = state.entities ? new Set(state.entities) : null;
        return HttpResponse.json({
          ...state.view(),
          usesDefault: false,
          kinds: Array.from({ length: 100_000 }, (_, n) => ({
            name: `kind_${n}`,
            source: n === 99999 ? "plugin" : n % 2 ? "language" : "format",
            masked: selected ? selected.has(`kind_${n}`) : n % 2 === 0,
            default: false,
          })),
        });
      }),
    );
    render(wrap(<MaskingSettings advanced />));
    await screen.findByLabelText("kind_0");
    expect(screen.getAllByRole("checkbox")).toHaveLength(26);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "kind_99999" } });
    expect(screen.getByRole("group", { name: "plugin" })).toBeTruthy();
    fireEvent.click(screen.getByLabelText("kind_99999"));
    fireEvent.click(screen.getByRole("button", { name: messages.masking.clearFilters }));
    expect(screen.getAllByRole("checkbox")).toHaveLength(26);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "kind_99999" } });
    expect((screen.getByLabelText("kind_99999") as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(state.patches).toHaveLength(1));
    expect(state.patches[0]?.settings.privacy.redactionEntities).toContain("kind_99999");
  });
  it("does not request masking without permission to read tenant settings", async () => {
    tenant(["policies:read"]);
    let reads = 0;
    server.use(
      http.get("*/api/v1/tenant/masking", () => {
        reads++;
        return HttpResponse.json({});
      }),
    );
    render(wrap(<MaskingSettings advanced />));
    await screen.findByText(messages.masking.readDenied);
    expect(reads).toBe(0);
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  });
  it("does not display stale protected controls after access is removed on refresh", async () => {
    const state = tenant();
    let denied = false;
    server.use(
      http.get("*/api/v1/tenant/masking", () =>
        denied
          ? HttpResponse.json({ detail: "masking access removed" }, { status: 403 })
          : HttpResponse.json(state.view()),
      ),
    );
    render(wrap(<MaskingSettings advanced />));
    await screen.findByLabelText("Person's name");
    denied = true;
    fireEvent.click(screen.getByRole("button", { name: messages.masking.refresh }));
    await screen.findByText("masking access removed");
    expect(screen.queryByLabelText("Person's name")).toBeNull();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  });
});

describe("masking partial-setting intent", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });
  it("preserves default-following list and confidence when Advanced saves unchanged fields", async () => {
    const state = tenant();
    render(wrap(<MaskingSettings advanced />));
    fireEvent.click(await screen.findByRole("button", { name: "Save" }));
    await screen.findByText(messages.masking.saved);
    expect(state.patches[0]?.settings.privacy).toEqual({});
    expect(state.entities).toBeNull();
    expect(state.score).toBeNull();
  });
  it("honours an explicit fixed confidence choice even when it equals the effective default", async () => {
    const state = tenant();
    render(wrap(<MaskingSettings advanced />));
    fireEvent.change(await screen.findByLabelText(messages.masking.score), {
      target: { value: "0.60" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText(messages.masking.saved);
    expect(state.patches[0]?.settings.privacy).toEqual({ redactionMinScore: 0.6 });
    expect(state.entities).toBeNull();
  });
  it("distinguishes acknowledged selection storage from a differing effective projection", async () => {
    const state = tenant();
    server.use(
      http.get("*/api/v1/tenant/masking", () =>
        HttpResponse.json({
          ...state.view(),
          kinds: state
            .view()
            .kinds.map((kind) => (kind.name === "credit_card" ? { ...kind, masked: false } : kind)),
        }),
      ),
    );
    render(wrap(<MaskingSettings advanced />));
    fireEvent.click(await screen.findByLabelText("Payment card number"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText(messages.masking.effectiveDifference);
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByText(messages.masking.effectiveDifference)),
    );
    expect(screen.getByText(messages.masking.saved)).toBeTruthy();
    expect((screen.getByLabelText("Payment card number") as HTMLInputElement).checked).toBe(false);
    expect(state.patches[0]?.settings.privacy.redactionEntities).toContain("credit_card");
  });
});
