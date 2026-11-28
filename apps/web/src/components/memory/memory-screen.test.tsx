import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MemoryScreen } from "@/components/memory/memory-screen";
import { clearCachedSession } from "@/lib/session";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/memory",
  useParams: () => ({}),
  useRouter: () => ({ push: () => undefined }),
}));

function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <MemoryScreen />
    </NextIntlClientProvider>,
  );
}
const fact = (i: number) => ({
  id: `fact-${i}`,
  content: `Saved preference ${i}`,
  scope: "user",
  category: "preference",
  status: "active",
});

beforeEach(() => {
  window.localStorage.clear();
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["chat:use"] })),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
  );
});

describe("memory controls", () => {
  it("offers search in Simple mode and bounds personal and shared lists", async () => {
    server.use(
      http.get("*/api/v1/memory", ({ request }) => {
        const q = new URL(request.url).searchParams.get("q");
        return HttpResponse.json({
          items: Array.from({ length: 30 }, (_, i) => fact(i)).filter(
            (row) => !q || row.content.includes(q),
          ),
          teams: [
            {
              id: "team",
              name: "Workspace team",
              items: Array.from({ length: 30 }, (_, i) => ({
                ...fact(i),
                content: `Shared fact ${i}`,
              })),
            },
          ],
          memoryEnabled: true,
        });
      }),
    );
    show();
    await screen.findByText("Saved preference 0");
    expect(screen.queryByText("Saved preference 29")).toBeNull();
    const shared = within(screen.getByRole("region", { name: messages.memory.shared }));
    expect(shared.queryByText("Shared fact 29")).toBeNull();
    fireEvent.change(shared.getByRole("searchbox"), { target: { value: "Shared fact 29" } });
    expect(shared.getByText("Shared fact 29")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.memory.search }), {
      target: { value: "Saved preference 29" },
    });
    fireEvent.click(screen.getByRole("button", { name: messages.memory.searchAction }));
    expect(await screen.findByText("Saved preference 29")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.memory.search }), {
      target: { value: "missing" },
    });
    fireEvent.click(screen.getByRole("button", { name: messages.memory.searchAction }));
    expect(await screen.findByText(messages.memory.noMatches)).toBeTruthy();
  });

  it("does not use the scope filter as the destination for a new memory", async () => {
    const writes: unknown[] = [];
    server.use(
      http.get("*/api/v1/memory", () =>
        HttpResponse.json({ items: [], teams: [], memoryEnabled: true }),
      ),
      http.post("*/api/v1/memory", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json({ ...fact(0), content: "Use short replies" });
      }),
    );
    show();
    await screen.findByText(messages.memory.empty);
    const save = screen.getByRole("button", { name: "Remember this" });
    expect(save.hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    fireEvent.change(screen.getByLabelText("Scope"), { target: { value: "workspace" } });
    const input = screen.getByLabelText(messages.memory.content) as HTMLTextAreaElement;
    expect(input.tagName).toBe("TEXTAREA");
    expect(input.maxLength).toBe(1000);
    await waitFor(() => expect(input.matches(":disabled")).toBe(false));
    fireEvent.change(input, { target: { value: "Use short replies" } });
    fireEvent.click(save);
    await waitFor(() => expect(writes).toEqual([{ content: "Use short replies", scope: "user" }]));
    await waitFor(() => expect(input.value).toBe(""));
    fireEvent.click(screen.getByRole("button", { name: "Simple" }));
    expect(screen.queryByLabelText("Scope")).toBeNull();
  });

  it("loads organisation settings only after Advanced opens and keeps its draft across mode switches", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["chat:use", "tenant:read", "tenant:manage"] }),
      ),
      http.get("*/api/v1/memory", () =>
        HttpResponse.json({ items: [], teams: [], memoryEnabled: true }),
      ),
      http.get("*/api/v1/tenant", () => {
        reads += 1;
        return HttpResponse.json({
          settings: { memory: { enabled: true, extraction: true, extractionInstructions: "" } },
        });
      }),
    );
    show();
    await screen.findByText(messages.memory.empty);
    expect(reads).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    const input = (await screen.findByLabelText(
      messages.memory.orgInstructions,
    )) as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "Keep this guidance draft" } });
    fireEvent.click(screen.getByRole("button", { name: "Simple" }));
    expect(screen.queryByRole("region", { name: messages.memory.orgTitle })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    expect(
      (screen.getByLabelText(messages.memory.orgInstructions) as HTMLTextAreaElement).value,
    ).toBe("Keep this guidance draft");
    expect(reads).toBe(1);
  });

  it("allows cancelling edits without changing saved content", async () => {
    const writes: unknown[] = [];
    server.use(
      http.get("*/api/v1/memory", () =>
        HttpResponse.json({ items: [fact(0)], teams: [], memoryEnabled: true }),
      ),
      http.patch("*/api/v1/memory/fact-0", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json(fact(0));
      }),
    );
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Edit memory fact-0" }));
    const editors = screen.getAllByRole("textbox", { name: messages.memory.editContent });
    const editor = editors.find(
      (element) => (element as HTMLTextAreaElement).value === "Saved preference 0",
    );
    if (!editor) throw new Error("Missing active editor");
    fireEvent.change(editor, { target: { value: "Unsaved change" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByText("Saved preference 0")).toBeTruthy();
    expect(screen.queryByText("Unsaved change")).toBeNull();
    expect(writes).toEqual([]);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Edit memory fact-0" }));
  });
});

const t = messages.memory;
function registry(items = [fact(0)]) {
  const state = { items, enabled: true, reads: 0, writes: [] as string[], failRead: false };
  server.use(
    http.get("*/api/v1/memory", ({ request }) => {
      state.reads += 1;
      if (state.failRead) return HttpResponse.json({ detail: "Read unavailable" }, { status: 503 });
      const params = new URL(request.url).searchParams;
      return HttpResponse.json({
        items: state.items.filter(
          (row) =>
            (!params.get("q") || row.content.includes(params.get("q") as string)) &&
            (!params.get("scope") || row.scope === params.get("scope")),
        ),
        teams: [],
        memoryEnabled: state.enabled,
      });
    }),
    http.post("*/api/v1/memory", async ({ request }) => {
      const body = (await request.json()) as { content: string };
      state.writes.push("POST");
      const result = {
        ...fact(1),
        content: body.content.replace(/[\p{White_Space}]+/gu, " ").trim(),
      };
      state.items.push(result);
      return HttpResponse.json(result);
    }),
    http.patch("*/api/v1/memory/settings", async ({ request }) => {
      state.writes.push("PREFERENCE");
      state.enabled = ((await request.json()) as { enabled: boolean }).enabled;
      return HttpResponse.json({ memoryEnabled: state.enabled });
    }),
    http.patch("*/api/v1/memory/:id", async ({ params, request }) => {
      state.writes.push(`PATCH ${params.id}`);
      const content = ((await request.json()) as { content: string }).content;
      const row = state.items.find((item) => item.id === params.id);
      if (!row) return new HttpResponse(null, { status: 404 });
      row.content = content;
      return HttpResponse.json(row);
    }),
    http.delete("*/api/v1/memory/:id", ({ params }) => {
      state.writes.push(`DELETE ${params.id}`);
      state.items = state.items.filter((row) => row.id !== params.id);
      return HttpResponse.json({ deleted: true });
    }),
  );
  return state;
}
const create = () => screen.getByLabelText(t.content) as HTMLTextAreaElement;
const saveNew = () => screen.getByRole("button", { name: t.save });
async function ready() {
  await screen.findByLabelText(t.content);
}
async function add(value = "Keep this draft") {
  fireEvent.change(create(), { target: { value } });
  fireEvent.click(saveNew());
}
afterEach(() => vi.restoreAllMocks());

describe("personal memory action state", () => {
  it("accepts the service's whitespace-normalised receipt without changing the submitted text", async () => {
    const state = registry([]);
    let sent = "";
    server.use(
      http.post("*/api/v1/memory", async ({ request }) => {
        sent = ((await request.json()) as { content: string }).content;
        const row = { ...fact(1), content: "Keep work notes" };
        state.items = [row];
        return HttpResponse.json(row);
      }),
    );
    show();
    await ready();
    await add("  Keep\nwork\u001cnotes  ");
    await screen.findByText(t.saved);
    expect(sent).toBe("  Keep\nwork\u001cnotes  ");
    expect(create().value).toBe("");
    expect(screen.getByText("Keep work notes")).toBeTruthy();
  });

  it("retains an unconfirmed create draft and refreshes without posting it again", async () => {
    const state = registry([]);
    server.use(
      http.post("*/api/v1/memory", () => {
        state.writes.push("POST");
        return HttpResponse.json({});
      }),
    );
    show();
    await ready();
    await add();
    await screen.findByText(t.saveUnconfirmed);
    await waitFor(() => expect(screen.getByRole("alert")).toBe(document.activeElement));
    expect(create().value).toBe("Keep this draft");
    expect(screen.queryByText(t.saved)).toBeNull();
    expect(create().matches(":disabled")).toBe(true);
    state.failRead = true;
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await screen.findByText("Read unavailable");
    expect(saveNew().matches(":disabled")).toBe(true);
    state.failRead = false;
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await waitFor(() => expect(screen.queryByText(t.recovery)).toBeNull());
    expect(create().value).toBe("Keep this draft");
    expect(state.writes).toEqual(["POST"]);
  });

  it("keeps the acknowledged save separate from a failed refresh", async () => {
    const state = registry([]);
    server.use(
      http.post("*/api/v1/memory", async ({ request }) => {
        const body = (await request.json()) as { content: string };
        const row = { ...fact(1), content: body.content };
        state.items = [row];
        state.writes.push("POST");
        state.failRead = true;
        return HttpResponse.json(row);
      }),
    );
    show();
    await ready();
    await add();
    await screen.findByText(t.acceptedRecovery);
    expect(screen.getByText(t.saved)).toBeTruthy();
    expect(create().value).toBe("");
    state.failRead = false;
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await screen.findByText("Keep this draft");
    expect(state.writes).toEqual(["POST"]);
  });

  it("preserves an edit when filters hide its row and rejects a mismatched edit identity", async () => {
    registry();
    server.use(
      http.patch("*/api/v1/memory/fact-0", () =>
        HttpResponse.json({ ...fact(9), content: "Edited draft" }),
      ),
    );
    show();
    await ready();
    fireEvent.click(screen.getByRole("button", { name: "Edit memory fact-0" }));
    fireEvent.change(screen.getByLabelText(t.editContent), { target: { value: "Edited draft" } });
    fireEvent.change(screen.getByRole("searchbox", { name: t.search }), {
      target: { value: "absent" },
    });
    fireEvent.click(screen.getByRole("button", { name: t.searchAction }));
    await screen.findByText(t.noMatches);
    expect((screen.getByLabelText(t.editContent) as HTMLTextAreaElement).value).toBe(
      "Edited draft",
    );
    fireEvent.click(screen.getByRole("button", { name: t.saveChanges }));
    await screen.findByText(t.saveUnconfirmed);
    expect(screen.queryByText(t.saved)).toBeNull();
  });

  it("saves the exact personal edit and confirms a single-row delete", async () => {
    const state = registry();
    show();
    await ready();
    fireEvent.click(screen.getByRole("button", { name: "Edit memory fact-0" }));
    fireEvent.change(screen.getByLabelText(t.editContent), { target: { value: "Updated note" } });
    fireEvent.click(screen.getByRole("button", { name: t.saveChanges }));
    await screen.findByText("Updated note");
    await waitFor(() => expect(screen.queryByLabelText(t.editContent)).toBeNull());
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Delete memory fact-0" }).matches(":disabled"),
      ).toBe(false),
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete memory fact-0" }));
    await screen.findByText(t.deleted);
    await screen.findByText(t.empty);
    expect(state.writes).toEqual(["PATCH fact-0", "DELETE fact-0"]);
  });

  it.each([{}, { deleted: "true" }])(
    "does not claim deletion for an unconfirmed receipt %j",
    async (receipt) => {
      const state = registry();
      server.use(
        http.delete("*/api/v1/memory/:id", () => {
          state.writes.push("DELETE");
          return HttpResponse.json(receipt);
        }),
      );
      show();
      await ready();
      fireEvent.click(screen.getByRole("button", { name: "Delete memory fact-0" }));
      await screen.findByText(t.deleteUnconfirmed);
      expect(screen.queryByText(t.deleted)).toBeNull();
      fireEvent.click(screen.getByRole("button", { name: t.refresh }));
      await waitFor(() => expect(screen.queryByText(t.recovery)).toBeNull());
      expect(screen.getByText("Saved preference 0")).toBeTruthy();
      expect(state.writes).toEqual(["DELETE"]);
    },
  );

  it("uses the actual preference receipt and never leaves an optimistic switch after a refusal", async () => {
    const state = registry();
    let refuse = true;
    server.use(
      http.patch("*/api/v1/memory/settings", async ({ request }) => {
        state.writes.push("PREFERENCE");
        if (refuse)
          return HttpResponse.json(
            { code: "csrf_failed", detail: "CSRF check failed" },
            { status: 403 },
          );
        state.enabled = ((await request.json()) as { enabled: boolean }).enabled;
        return HttpResponse.json({ memoryEnabled: state.enabled });
      }),
    );
    show();
    await ready();
    const toggle = () =>
      screen.getByRole("checkbox", { name: new RegExp(`^${t.enabled}`) }) as HTMLInputElement;
    fireEvent.click(toggle());
    await screen.findByText(messages.apiErrors.csrf);
    expect(toggle().checked).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await waitFor(() => expect(screen.queryByText(t.recovery)).toBeNull());
    refuse = false;
    fireEvent.click(toggle());
    await screen.findByText(t.preferenceSaved);
    expect(toggle().checked).toBe(false);
    expect(state.writes).toEqual(["PREFERENCE", "PREFERENCE"]);
  });

  it.each([{}, { memoryEnabled: "false" }])(
    "holds an incomplete preference receipt %j",
    async (receipt) => {
      registry();
      server.use(http.patch("*/api/v1/memory/settings", () => HttpResponse.json(receipt)));
      show();
      await ready();
      fireEvent.click(screen.getByRole("checkbox", { name: new RegExp(`^${t.enabled}`) }));
      await screen.findByText(t.preferenceUnconfirmed);
      expect(screen.queryByText(t.preferenceSaved)).toBeNull();
    },
  );

  it("withholds workspace mutation and bulk deletion controls", async () => {
    const state = registry([{ ...fact(0), scope: "workspace" }]);
    let bulk = 0;
    server.use(
      http.delete("*/api/v1/memory", () => {
        bulk += 1;
        return HttpResponse.json({ deleted: 1 });
      }),
    );
    show();
    await ready();
    expect(screen.getByText("Saved preference 0")).toBeTruthy();
    expect(screen.getByText(t.readOnlyFact)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^(Edit|Delete) memory / })).toBeNull();
    expect(
      screen.queryByRole("button", { name: /Forget everything|Delete all memory/ }),
    ).toBeNull();
    expect(bulk).toBe(0);
    expect(state.writes).toEqual([]);
  });

  it("submits search explicitly, clears all filters and bounds 100,000 loaded rows", async () => {
    const state = registry(Array.from({ length: 100_000 }, (_, i) => fact(i)));
    show();
    await ready();
    expect(screen.getByRole("list").querySelectorAll("li")).toHaveLength(25);
    const initial = state.reads;
    fireEvent.change(screen.getByRole("searchbox", { name: t.search }), {
      target: { value: "Saved preference 99999" },
    });
    expect(state.reads).toBe(initial);
    fireEvent.click(screen.getByRole("button", { name: t.searchAction }));
    await screen.findByText("Saved preference 99999");
    expect(screen.getByRole("list").querySelectorAll("li")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: t.clearFilters }));
    await screen.findByText("Saved preference 0");
    expect(screen.getByRole("list").querySelectorAll("li")).toHaveLength(25);
  });

  it.each([{}, { items: [], teams: [], memoryEnabled: "true" }])(
    "withholds missing/malformed saved metadata %j",
    async (body) => {
      registry();
      server.use(http.get("*/api/v1/memory", () => HttpResponse.json(body)));
      show();
      await screen.findByText(t.metadataError);
      expect(screen.queryByLabelText(t.content)).toBeNull();
    },
  );

  it("gates private reads and clears stale controls on access loss", async () => {
    const state = registry();
    show();
    await ready();
    server.use(
      http.get("*/api/v1/memory", () => {
        state.reads += 1;
        return HttpResponse.json({ detail: "Access removed" }, { status: 403 });
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await screen.findByText("Access removed");
    expect(screen.queryByText("Saved preference 0")).toBeNull();
    expect(screen.queryByLabelText(t.content)).toBeNull();
    clearCachedSession();
    server.use(http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: [] })));
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await screen.findByText(t.readDenied);
    expect(state.reads).toBe(2);
  });

  it("does not request private memories without chat permission", async () => {
    const state = registry();
    server.use(http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: [] })));
    show();
    await screen.findByText(t.readDenied);
    expect(state.reads).toBe(0);
    expect(screen.queryByLabelText(t.content)).toBeNull();
  });

  it("discards a late filtered read after a newer search has finished", async () => {
    registry();
    const original = globalThis.fetch;
    let signal: AbortSignal | null = null;
    let finish: (value: Response) => void = () => undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input).includes("q=slow")) {
        signal = init?.signal as AbortSignal;
        return new Promise<Response>((resolve) => {
          finish = resolve;
        });
      }
      return original(input, init);
    });
    show();
    await ready();
    const query = screen.getByRole("searchbox", { name: t.search });
    fireEvent.change(query, { target: { value: "slow" } });
    fireEvent.click(screen.getByRole("button", { name: t.searchAction }));
    await waitFor(() => expect(signal).not.toBeNull());
    fireEvent.change(query, { target: { value: "absent" } });
    fireEvent.click(screen.getByRole("button", { name: t.searchAction }));
    await screen.findByText(t.noMatches);
    expect((signal as AbortSignal | null)?.aborted).toBe(true);
    await act(async () => {
      finish(new Response(JSON.stringify({ items: [fact(8)], teams: [], memoryEnabled: true })));
    });
    expect(screen.queryByText("Saved preference 8")).toBeNull();
    expect(screen.getByText(t.noMatches)).toBeTruthy();
  });

  it("accepts 500 Unicode characters and blocks over-limit raw drafts", async () => {
    const state = registry([]);
    show();
    await ready();
    fireEvent.change(create(), { target: { value: "\ufeff" } });
    expect(saveNew().matches(":disabled")).toBe(true);
    fireEvent.submit(create().closest("form") as HTMLFormElement);
    expect(state.writes).toEqual([]);
    await add("🌱".repeat(500));
    await screen.findByText(t.saved);
    expect(Array.from(state.items[0]?.content ?? "")).toHaveLength(500);
    fireEvent.change(create(), { target: { value: "x".repeat(501) } });
    expect(screen.getByText(t.contentTooLong)).toBeTruthy();
    expect(saveNew().matches(":disabled")).toBe(true);
    fireEvent.submit(create().closest("form") as HTMLFormElement);
    expect(state.writes).toEqual(["POST"]);
  });

  it("guards same-frame writes and aborts a pending receipt on unmount", async () => {
    registry([]);
    const original = globalThis.fetch;
    let writes = 0;
    let signal: AbortSignal | null = null;
    let finish: (value: Response) => void = () => undefined;
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
    fireEvent.change(create(), { target: { value: "Pending draft" } });
    const form = create().closest("form") as HTMLFormElement;
    act(() => {
      fireEvent.submit(form);
      fireEvent.submit(form);
    });
    expect(writes).toBe(1);
    view.unmount();
    expect((signal as AbortSignal | null)?.aborted).toBe(true);
    await act(async () => {
      finish(new Response(JSON.stringify({ ...fact(1), content: "Pending draft" })));
    });
    expect(screen.queryByText(t.saved)).toBeNull();
  });
});
