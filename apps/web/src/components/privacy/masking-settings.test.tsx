import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

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
      return HttpResponse.json({});
    }),
  );
  return state;
}

describe("Masking settings", () => {
  afterEach(() => cleanup());

  it("says in Simple mode how many kinds are masked, and saves only the switch", async () => {
    const state = tenant();
    render(wrap(<MaskingSettings advanced={false} />));

    expect(await screen.findByText(/2 kinds are masked: the product default/)).toBeTruthy();
    expect(screen.queryByLabelText("Person's name")).toBeNull();
    fireEvent.click(screen.getByLabelText(/Mask personal data in tool results/));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Saved. It applies to the next tool result.")).toBeTruthy();
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
    fireEvent.click(await screen.findByRole("button", { name: "Use the product default" }));
    expect(await screen.findByText("The product default is back.")).toBeTruthy();
    expect(state.patches[1]?.settings.privacy).toEqual({
      redactionEntities: null,
      redactionMinScore: null,
    });
    expect(screen.queryByRole("button", { name: "Use the product default" })).toBeNull();
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
