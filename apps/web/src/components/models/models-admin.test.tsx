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

  it("shows an incompatible existing assignment without hiding the assigned model", async () => {
    const state = registry();
    state.models.push({ id: "chat-1", name: "Text model", kind: "chat", capabilities: [] });
    state.aliases.push({ id: "vision-1", alias: "vision", primaryModelId: "chat-1" });
    render(wrap(<ModelsAdmin />));

    expect(await screen.findByText("Needs attention")).toBeTruthy();
    const selector = screen.getByRole("button", { name: /^Model for Images:/ });
    expect(selector.textContent).toContain("Text model");
    expect(selector.hasAttribute("disabled")).toBe(true);
    expect(screen.getByText(/The assigned model does not meet/)).toBeTruthy();
    expect(state.calls).toEqual([]);
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

  it("distinguishes a refused test request from an actual model result", async () => {
    const state = registry();
    state.providers.push({
      id: "prov-1",
      name: "Main",
      kind: "openai_compatible",
      baseUrl: "https://model.example/v1",
      hasApiKey: true,
      platform: false,
    });
    state.models.push({
      id: "model-1",
      providerId: "prov-1",
      name: "Chat",
      upstreamModel: "chat",
      kind: "chat",
    });
    state.aliases.push({
      id: "alias-1",
      alias: "reasoning",
      kind: "chat",
      primaryModelId: "model-1",
    });
    let writes = 0;
    server.use(
      http.post("*/api/v1/model-aliases/:id\\:test", () => {
        writes += 1;
        return HttpResponse.json(
          { detail: "Origin rejected", code: "csrf_failed" },
          { status: 403 },
        );
      }),
    );
    render(wrap(<ModelsAdmin />));
    fireEvent.click(await screen.findByRole("button", { name: "Test Answers" }));
    await screen.findByText(messages.models.testUnavailable);
    expect(screen.getByText(messages.apiErrors.csrf)).toBeTruthy();
    expect(screen.queryByText(messages.models.testFailed)).toBeNull();
    expect(screen.queryByText("Origin rejected")).toBeNull();
    const details = screen
      .getByText(messages.apiErrors.details)
      .closest("details") as HTMLDetailsElement;
    details.open = true;
    fireEvent(details, new Event("toggle"));
    expect(screen.getByText("Origin rejected")).toBeTruthy();
    expect(writes).toBe(1);
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

    const images = await screen.findByRole("button", { name: /^Model for Images:/ });
    expect(screen.getByText("Reads images")).toBeTruthy();
    fireEvent.click(images);
    let picker = within(screen.getByRole("dialog", { name: "Model for Images" }));
    expect(picker.getByText("Eyes · Main")).toBeTruthy();
    expect(picker.queryByText("Plain · Main")).toBeNull();
    fireEvent.click(picker.getByRole("button", { name: "Cancel" }));
    fireEvent.click(screen.getByRole("button", { name: /^Model for Answers:/ }));
    picker = within(screen.getByRole("dialog", { name: "Model for Answers" }));
    expect(picker.getByText("Plain · Main")).toBeTruthy();
    expect(picker.getByText("Eyes · Main")).toBeTruthy();
    fireEvent.click(picker.getByRole("button", { name: "Cancel" }));
    fireEvent.click(images);
    picker = within(screen.getByRole("dialog", { name: "Model for Images" }));
    fireEvent.click(picker.getByText("Eyes · Main"));
    await waitFor(() =>
      expect(state.calls.at(-1)).toMatchObject({
        path: "/api/v1/model-aliases",
        body: { alias: "vision", kind: "chat", primaryModelId: "m-2" },
      }),
    );
  });

  it("sends the request options a person writes for a chat model, and refuses text that is not an object", async () => {
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
    fireEvent.click(await screen.findByRole("button", { name: "Advanced" }));
    fireEvent.click(await screen.findByRole("button", { name: "Add model to Main" }));

    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Model id"), {
      target: { value: "vendor/chat-large" },
    });
    const options = within(dialog).getByLabelText("Request options (JSON)") as HTMLTextAreaElement;
    // A new model starts with none, whatever it is called.
    expect(options.value).toBe("");
    fireEvent.change(options, { target: { value: "[1, 2]" } });
    expect(
      within(dialog).getByText(/Request options must be a JSON object/, {
        selector: "[role=alert]",
      }),
    ).toBeTruthy();
    fireEvent.change(options, {
      target: { value: '{"chat_template_kwargs": {"enable_thinking": false}}' },
    });
    expect(within(dialog).queryByRole("alert")).toBeNull();
    fireEvent.click(within(dialog).getByRole("button", { name: "Add model" }));

    await waitFor(() =>
      expect(state.calls.find((call) => call.path === "/api/v1/models")).toMatchObject({
        method: "POST",
        body: {
          upstreamModel: "vendor/chat-large",
          kind: "chat",
          requestOptions: { chat_template_kwargs: { enable_thinking: false } },
        },
      }),
    );
  });

  it("lets a rerank model say where it is called and how, and sends that with the model", async () => {
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
    fireEvent.click(await screen.findByRole("button", { name: "Advanced" }));
    fireEvent.click(await screen.findByRole("button", { name: "Add model to Main" }));

    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Model id"), {
      target: { value: "vendor/rerank-1" },
    });
    fireEvent.change(within(dialog).getByLabelText("Kind"), { target: { value: "rerank" } });
    // The route starts at the usual values; the customer changes both.
    const path = within(dialog).getByLabelText("Rerank path") as HTMLInputElement;
    expect(path.value).toBe("/rerank");
    fireEvent.change(path, { target: { value: "/inference/vendor/rerank-1" } });
    fireEvent.change(within(dialog).getByLabelText("Request body"), {
      target: { value: "queries" },
    });
    // Each model scores on its own scale, so the bar a score must clear is the model's.
    const floor = within(dialog).getByLabelText("Lowest score that counts") as HTMLInputElement;
    expect(floor.value).toBe("0.2");
    fireEvent.change(floor, { target: { value: "0.02" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add model" }));

    await waitFor(() =>
      expect(state.calls.find((call) => call.path === "/api/v1/models")).toMatchObject({
        method: "POST",
        body: {
          upstreamModel: "vendor/rerank-1",
          kind: "rerank",
          requestOptions: {
            rerank: { path: "/inference/vendor/rerank-1", body: "queries", min_score: 0.02 },
          },
        },
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
    expect(
      screen.getByRole("button", { name: /^Model for Answers:/ }).hasAttribute("disabled"),
    ).toBe(true);
  });
  it("keeps an acknowledged provider save distinct from a failed refresh, and retries reads only", async () => {
    const state = registry();
    render(wrap(<ModelsAdmin />));
    await screen.findByText(/No provider yet/);
    let failRead = true;
    server.use(
      http.get("*/api/v1/models", () =>
        failRead
          ? HttpResponse.json({ detail: "Registry offline" }, { status: 503 })
          : HttpResponse.json({ items: state.models }),
      ),
    );
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Saved provider" } });
    fireEvent.change(screen.getByLabelText("Base URL"), {
      target: { value: "https://models.example.com/v1" },
    });
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "submitted-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Add provider" }));
    expect(await screen.findByText(messages.models.savedRefreshFailed)).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect((screen.getByLabelText("API key") as HTMLInputElement).value).toBe("");
    expect(screen.getByRole("button", { name: "Add provider" }).matches(":disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Refresh registry" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Refresh registry" }).matches(":disabled")).toBe(
        false,
      ),
    );
    expect(screen.getByText(messages.models.savedRefreshFailed)).toBeTruthy();
    failRead = false;
    fireEvent.click(screen.getByRole("button", { name: "Refresh registry" }));
    expect(await screen.findByRole("heading", { name: "Saved provider" })).toBeTruthy();
    expect(screen.queryByText(messages.models.savedRefreshFailed)).toBeNull();
    expect(state.calls).toHaveLength(1);
  });

  it("freezes conflicting page controls and guards duplicate provider submission while a request is pending", async () => {
    registry();
    render(wrap(<ModelsAdmin />));
    await screen.findByText(/No provider yet/);
    let release = () => {};
    const waiting = new Promise<void>((resolve) => {
      release = resolve;
    });
    let writes = 0;
    server.use(
      http.post("*/api/v1/model-providers", async () => {
        writes += 1;
        await waiting;
        return HttpResponse.json({ detail: "Connection unavailable" }, { status: 503 });
      }),
    );
    const button = screen.getByRole("button", { name: "Add provider" });
    const form = button.closest("form");
    if (!form) throw new Error("Provider form missing");
    fireEvent.submit(form);
    fireEvent.submit(form);
    await waitFor(() => expect(writes).toBe(1));
    expect(button.matches(":disabled")).toBe(true);
    expect(screen.getByLabelText("Name").matches(":disabled")).toBe(true);
    release();
    expect(await screen.findByText("Connection unavailable")).toBeTruthy();
    await waitFor(() => expect(button.matches(":disabled")).toBe(false));
  });

  it("closes a saved model form when a default assignment fails, without offering to create it twice", async () => {
    const state = registry();
    state.providers.push({
      id: "prov-1",
      name: "Main",
      kind: "openai_compatible",
      baseUrl: "https://models.example.com/v1",
      platform: false,
    });
    server.use(
      http.post("*/api/v1/model-aliases", () =>
        HttpResponse.json({ detail: "Assignment unavailable" }, { status: 503 }),
      ),
    );
    render(wrap(<ModelsAdmin />));
    fireEvent.click(await screen.findByRole("button", { name: "Add model to Main" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Model id"), {
      target: { value: "saved-model" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add model" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(
      screen.getByText(
        /The model was saved, but these default assignments could not be confirmed: Answers/,
      ),
    ).toBeTruthy();
    expect(state.models).toHaveLength(1);
    expect(state.aliases).toHaveLength(0);
    expect(state.calls.filter((call) => call.path === "/api/v1/models")).toHaveLength(1);
    expect(screen.getAllByText("saved-model").length).toBeGreaterThan(0);
  });

  it("blocks a failed dialog submission after refresh also fails until a read recovers", async () => {
    const state = registry();
    state.providers.push({
      id: "prov-1",
      name: "Main",
      kind: "openai_compatible",
      baseUrl: "https://models.example.com/v1",
      platform: false,
    });
    render(wrap(<ModelsAdmin />));
    fireEvent.click(await screen.findByRole("button", { name: "Remove Main" }));
    server.use(
      http.get("*/api/v1/models", () =>
        HttpResponse.json({ detail: "Read unavailable" }, { status: 503 }),
      ),
    );
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
    expect(await within(dialog).findByText(messages.models.refreshRequired)).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Remove" }).matches(":disabled")).toBe(true);
    const form = within(dialog).getByRole("button", { name: "Remove" }).closest("form");
    if (!form) throw new Error("Removal form missing");
    fireEvent.submit(form);
    expect(state.calls).toHaveLength(1);
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(await screen.findByText(messages.models.unconfirmedRefreshFailed)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Refresh registry" }).matches(":disabled")).toBe(
      false,
    );
  });
  it("closes an acknowledged dialog save even when its metadata refresh fails", async () => {
    const state = registry();
    state.providers.push({
      id: "prov-1",
      name: "Main",
      kind: "openai_compatible",
      baseUrl: "https://models.example.com/v1",
      platform: false,
    });
    render(wrap(<ModelsAdmin />));
    fireEvent.click(await screen.findByRole("button", { name: "Add model to Main" }));
    const dialog = await screen.findByRole("dialog");
    server.use(
      http.get("*/api/v1/models", () =>
        HttpResponse.json({ detail: "Read unavailable" }, { status: 503 }),
      ),
    );
    fireEvent.change(within(dialog).getByLabelText("Model id"), {
      target: { value: "saved-model" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add model" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByText(messages.models.savedRefreshFailed)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add model to Main" }).matches(":disabled")).toBe(
      true,
    );
    expect(state.models).toHaveLength(1);
    expect(state.aliases).toHaveLength(1);
  });
});
