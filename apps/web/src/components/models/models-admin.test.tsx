import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ModelsAdmin } from "@/components/models/models-admin";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const navigation = vi.hoisted(() => ({
  replace: vi.fn(),
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/models",
  useRouter: () => navigation,
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("Models admin", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
  });

  it("registers an OpenAI-compatible provider without showing the key again", async () => {
    const posted: { path: string; body: Record<string, unknown> }[] = [];
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["models:manage"],
          user: { displayName: "Admin", email: "admin@dev.local" },
        }),
      ),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/model-providers", () =>
        HttpResponse.json({
          items: [
            {
              id: "prov-1",
              name: "fake-llm",
              kind: "fake",
              baseUrl: "http://127.0.0.1:8099/v1",
              platform: true,
              hasApiKey: false,
            },
          ],
        }),
      ),
      http.get("*/api/v1/models", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/model-aliases", () =>
        HttpResponse.json({ items: [{ id: "alias-1", alias: "reasoning", platform: true }] }),
      ),
      http.post("*/api/v1/model-providers", async ({ request }) => {
        posted.push({ path: "provider", body: (await request.json()) as Record<string, unknown> });
        return HttpResponse.json({ id: "prov-2", name: "DeepInfra" });
      }),
      http.post("*/api/v1/models", async ({ request }) => {
        posted.push({ path: "model", body: (await request.json()) as Record<string, unknown> });
        return HttpResponse.json({ id: "model-2" });
      }),
      http.post("*/api/v1/model-aliases", async ({ request }) => {
        posted.push({ path: "alias", body: (await request.json()) as Record<string, unknown> });
        return HttpResponse.json({ id: "alias-2" });
      }),
      http.post("*/api/v1/model-providers/prov-2:test", () =>
        HttpResponse.json({ output: "pong", latencyMs: 12 }),
      ),
    );

    render(wrap(<ModelsAdmin />));
    expect((await screen.findAllByText("fake-llm")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    fireEvent.click(screen.getByRole("button", { name: "OpenAI-compatible" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "DeepInfra" } });
    fireEvent.change(await screen.findByLabelText("API key"), {
      target: { value: "sk-cert-secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Register and test" }));

    await waitFor(() => {
      expect(screen.getByText(/pong/)).toBeTruthy();
    });
    expect(posted[0]?.body).toMatchObject({
      name: "DeepInfra",
      kind: "openai_compatible",
      baseUrl: "https://api.deepinfra.com/v1/openai",
      apiKey: "sk-cert-secret",
    });
    expect(posted[1]?.body).toMatchObject({ upstreamModel: "Qwen/Qwen3-32B" });
    expect((screen.getByLabelText("API key") as HTMLInputElement).value).toBe("");
    expect(screen.queryByText("sk-cert-secret")).toBeNull();
  });
});
