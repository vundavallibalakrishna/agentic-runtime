import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

type Body = Record<string, unknown>;
type Call = { method: string; path: string; body: Body };

const STANDARD = [
  { alias: "reasoning", kind: "chat", required: true, capability: null },
  { alias: "vision", kind: "chat", required: false, capability: "vision" },
  { alias: "embed", kind: "embedding", required: true, capability: null },
  { alias: "rerank", kind: "rerank", required: false, capability: null },
];

/** A registry the page reads and changes, as the API would hold it. */
function registry(permissions: string[] = ["models:read", "models:manage"]) {
  const state = {
    providers: [] as Body[],
    models: [] as Body[],
    aliases: [] as Body[],
    calls: [] as Call[],
  };
  const record = async (request: Request): Promise<Body> => {
    const body = request.method === "DELETE" ? {} : ((await request.json()) as Body);
    state.calls.push({ method: request.method, path: new URL(request.url).pathname, body });
    return body;
  };
  const standard = () =>
    STANDARD.map((item) => {
      const alias = state.aliases.find((row) => row.alias === item.alias);
      const model = state.models.find((row) => row.id === alias?.primaryModelId);
      return {
        ...item,
        set: Boolean(model),
        aliasId: alias?.id ?? null,
        platform: false,
        modelId: model?.id ?? null,
        modelName: model?.name ?? null,
      };
    });
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ permissions, user: { displayName: "Ada", email: "ada@acme.example" } }),
    ),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/model-providers", () => HttpResponse.json({ items: state.providers })),
    http.get("*/api/v1/models", () => HttpResponse.json({ items: state.models })),
    http.get("*/api/v1/model-aliases", () =>
      HttpResponse.json({ items: state.aliases, standard: standard() }),
    ),
    http.post("*/api/v1/model-providers", async ({ request }) => {
      const body = await record(request);
      const row = {
        id: `prov-${state.providers.length + 1}`,
        name: body.name,
        kind: body.kind,
        baseUrl: body.baseUrl,
        hasApiKey: Boolean(body.apiKey),
        platform: false,
      };
      state.providers.push(row);
      return HttpResponse.json(row);
    }),
    http.post("*/api/v1/models", async ({ request }) => {
      const body = await record(request);
      const row = { ...body, id: `model-${state.models.length + 1}`, platform: false };
      state.models.push(row);
      return HttpResponse.json(row);
    }),
    http.post("*/api/v1/model-aliases", async ({ request }) => {
      const body = await record(request);
      const row = { ...body, id: `alias-${state.aliases.length + 1}`, platform: false };
      state.aliases.push(row);
      return HttpResponse.json(row);
    }),
    http.post("*/api/v1/model-aliases/:id\\:test", async ({ request }) => {
      state.calls.push({ method: "POST", path: new URL(request.url).pathname, body: {} });
      return HttpResponse.json({ ok: true, output: "pong", latencyMs: 12 });
    }),
    http.delete("*/api/v1/model-providers/:id", async ({ request }) => {
      await record(request);
      return HttpResponse.json(
        { detail: "This provider still has models: Chat. Remove them first." },
        { status: 409 },
      );
    }),
  );
  return state;
}

describe("Models admin", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
  });

  it("starts empty: no provider, nothing set, and no value filled in for the person", async () => {
    registry();
    render(wrap(<ModelsAdmin />));

    expect(await screen.findByText(/No provider yet/)).toBeTruthy();
    // The two names the product cannot work without say so.
    expect(screen.getAllByText("Not set, needed")).toHaveLength(2);
    expect(screen.getAllByText("Not set")).toHaveLength(2);
    // No vendor address, model id or name is typed in for the person.
    for (const label of ["Name", "Base URL", "API key"]) {
      expect((screen.getByLabelText(label) as HTMLInputElement).value).toBe("");
    }
    expect(document.body.textContent).not.toMatch(/deepinfra|qwen|fake|127\.0\.0\.1/i);
  });

  it("adds a provider and its first chat model, and points the answers name at it", async () => {
    const state = registry();
    render(wrap(<ModelsAdmin />));
    await screen.findByText(/No provider yet/);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Main" } });
    fireEvent.change(screen.getByLabelText("Base URL"), {
      target: { value: "https://models.example.com/v1" },
    });
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Add provider" }));

    // The next step is a model, so its dialog opens by itself.
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Model id"), {
      target: { value: "vendor/chat-large" },
    });
    // The name the product needs is offered, and ticked because it is required.
    const answers = within(dialog).getByRole("checkbox", { name: /Answers/ }) as HTMLInputElement;
    expect(answers.checked).toBe(true);
    fireEvent.click(within(dialog).getByRole("button", { name: "Add model" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const posts = state.calls.filter((call) => call.method === "POST");
    expect(posts[0]).toMatchObject({
      path: "/api/v1/model-providers",
      body: {
        name: "Main",
        kind: "openai_compatible",
        baseUrl: "https://models.example.com/v1",
        apiKey: "sk-secret",
      },
    });
    expect(posts[1]).toMatchObject({
      path: "/api/v1/models",
      body: { providerId: "prov-1", upstreamModel: "vendor/chat-large", kind: "chat" },
    });
    expect(posts[2]).toMatchObject({
      path: "/api/v1/model-aliases",
      body: { alias: "reasoning", kind: "chat", primaryModelId: "model-1" },
    });
    // The key is sent once and never shown again.
    expect((screen.getByLabelText("API key") as HTMLInputElement).value).toBe("");
    expect(document.body.textContent).not.toContain("sk-secret");
    expect(await screen.findByText("Set")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Test Answers" }));
    expect(await screen.findByText("It answered.")).toBeTruthy();
    expect(screen.getByText("pong (12 ms)")).toBeTruthy();
  });

  it("offers the images name only to a chat model marked as able to read images", async () => {
    const state = registry();
    state.providers.push({
      id: "prov-1",
      name: "Main",
      kind: "openai_compatible",
      baseUrl: "https://models.example.com/v1",
      hasApiKey: true,
      platform: false,
    });
    state.models.push(
      { id: "m-1", providerId: "prov-1", name: "Plain", upstreamModel: "a", kind: "chat" },
      {
        id: "m-2",
        providerId: "prov-1",
        name: "Eyes",
        upstreamModel: "b",
        kind: "chat",
        capabilities: ["vision"],
      },
    );
    render(wrap(<ModelsAdmin />));

    const images = (await screen.findByLabelText("Model for Images")) as HTMLSelectElement;
    expect(Array.from(images.options).map((option) => option.text)).toEqual([
      "Choose a model",
      "Eyes",
    ]);
    const answers = screen.getByLabelText("Model for Answers") as HTMLSelectElement;
    expect(Array.from(answers.options).map((option) => option.text)).toEqual([
      "Choose a model",
      "Plain",
      "Eyes",
    ]);
    expect(screen.getByText("Reads images")).toBeTruthy();
    fireEvent.change(images, { target: { value: "m-2" } });
    await waitFor(() =>
      expect(state.calls.at(-1)).toMatchObject({
        path: "/api/v1/model-aliases",
        body: { alias: "vision", kind: "chat", primaryModelId: "m-2" },
      }),
    );
  });

  it("keeps a refusal in the dialog, in the words the API gave", async () => {
    const state = registry();
    state.providers.push({
      id: "prov-1",
      name: "Main",
      kind: "openai_compatible",
      baseUrl: "https://models.example.com/v1",
      hasApiKey: true,
      platform: false,
    });
    render(wrap(<ModelsAdmin />));

    fireEvent.click(await screen.findByRole("button", { name: "Remove Main" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
    expect(
      await within(dialog).findByText("This provider still has models: Chat. Remove them first."),
    ).toBeTruthy();
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("shows the registry without controls to someone who cannot manage models", async () => {
    const state = registry(["models:read"]);
    state.providers.push({
      id: "prov-1",
      name: "Main",
      kind: "openai_compatible",
      baseUrl: "https://models.example.com/v1",
      hasApiKey: true,
      platform: false,
    });
    render(wrap(<ModelsAdmin />));

    expect(await screen.findByRole("heading", { name: "Main" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Add provider" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove Main" })).toBeNull();
    expect(screen.getByText(/Changing them needs the permission/)).toBeTruthy();
    expect((screen.getByLabelText("Model for Answers") as HTMLSelectElement).disabled).toBe(true);
  });
});
