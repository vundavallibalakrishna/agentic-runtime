import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import { OrganisationMemorySettings } from "@/components/memory/organisation-settings";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

describe("organisation memory settings", () => {
  afterEach(cleanup);

  it("shows what is set and saves the switch and the guidance together", async () => {
    const saved: unknown[] = [];
    server.use(
      http.get("*/api/v1/tenant", () =>
        HttpResponse.json({
          settings: {
            memory: { enabled: true, extraction: true, extractionInstructions: "Keep it short." },
          },
        }),
      ),
      http.patch("*/api/v1/tenant", async ({ request }) => {
        saved.push(await request.json());
        return HttpResponse.json({ id: "t-1" });
      }),
    );
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <OrganisationMemorySettings />
      </NextIntlClientProvider>,
    );

    const guidance = (await screen.findByLabelText(
      "What to keep and what to leave out",
    )) as HTMLTextAreaElement;
    await waitFor(() => expect(guidance.value).toBe("Keep it short."));
    const remember = screen.getByRole("checkbox") as HTMLInputElement;
    expect(remember.checked).toBe(true);

    fireEvent.change(guidance, { target: { value: " Never keep anything about salaries. " } });
    fireEvent.click(remember);
    fireEvent.click(screen.getByRole("button", { name: "Save for everyone" }));

    expect(await screen.findByText("Saved. It applies from the next answer.")).toBeTruthy();
    // The whole section is sent, so the part this card does not show is not lost.
    expect(saved).toEqual([
      {
        settings: {
          memory: {
            enabled: true,
            extraction: false,
            extractionInstructions: "Never keep anything about salaries.",
          },
        },
      },
    ]);
  });

  it("says why when the settings cannot be saved", async () => {
    server.use(
      http.get("*/api/v1/tenant", () => HttpResponse.json({ settings: {} })),
      http.patch("*/api/v1/tenant", () =>
        HttpResponse.json({ detail: "You may not change this organisation." }, { status: 403 }),
      ),
    );
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <OrganisationMemorySettings />
      </NextIntlClientProvider>,
    );
    const button = await screen.findByRole("button", { name: "Save for everyone" });
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button);
    expect((await screen.findByRole("alert")).textContent).toBe(
      "You may not change this organisation.",
    );
  });
});
