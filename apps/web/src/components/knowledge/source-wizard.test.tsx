import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SourceWizard } from "@/components/knowledge/source-wizard";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  usePathname: () => "/knowledge/collection/sources/new",
  useParams: () => ({}),
  useRouter: () => ({ push }),
}));

function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <SourceWizard collectionId="collection" />
    </NextIntlClientProvider>,
  );
}

function configuration() {
  return JSON.parse(
    (screen.getByLabelText(messages.detail.configuration) as HTMLTextAreaElement).value,
  );
}

beforeEach(() => {
  push.mockClear();
  server.use(
    http.get("*/api/v1/tenant", () => HttpResponse.json({ settings: {} })),
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ permissions: ["knowledge:write"] }),
    ),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/data-connections", () =>
      HttpResponse.json({
        items: [{ id: "old-connection", name: "Workspace database", kind: "postgres" }],
      }),
    ),
  );
});

afterEach(() => {
  cleanup();
});

describe("source wizard", () => {
  it("starts each kind with the fields it needs and holds no credential field", () => {
    show();
    const kind = screen.getByLabelText(messages.knowledge.sourceKind);
    fireEvent.change(kind, { target: { value: "s3" } });
    expect(Object.keys(configuration())).toEqual([
      "bucket",
      "prefix",
      "endpoint",
      "region",
      "connection",
    ]);
    expect(screen.getByText(/whose username is the access key/)).toBeTruthy();
    fireEvent.change(kind, { target: { value: "database" } });
    expect(configuration().idColumn).toBe("id");
    expect(screen.getByRole("button", { name: /^Database connection:/ })).toBeTruthy();
    fireEvent.change(kind, { target: { value: "mcp_resource" } });
    expect(screen.getByText(/tool server registered in this workspace/)).toBeTruthy();
    // A key or password is a saved connection. No field here takes one.
    expect(screen.queryByLabelText(/secret/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /secret/i })).toBeNull();
    expect(document.body.textContent).not.toMatch(/"items"|"objects"|"rows"|"resources"/);
  });

  it("sends the configuration and the chosen data connection for a database source", async () => {
    const writes: unknown[] = [];
    server.use(
      http.post("*/api/v1/knowledge/collections/collection/sources", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json({ id: "source" });
      }),
    );
    show();
    fireEvent.change(screen.getByLabelText(messages.knowledge.name), {
      target: { value: "Articles" },
    });
    fireEvent.change(screen.getByLabelText(messages.knowledge.sourceKind), {
      target: { value: "database" },
    });
    fireEvent.change(screen.getByLabelText(messages.detail.configuration), {
      target: { value: '{"query": "SELECT id, title, text FROM articles"}' },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Database connection:/ }));
    fireEvent.click(await screen.findByText("Workspace database"));
    fireEvent.click(screen.getByRole("button", { name: messages.knowledge.connect }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/knowledge/collection"));
    expect(writes).toEqual([
      {
        name: "Articles",
        kind: "database",
        config: { query: "SELECT id, title, text FROM articles" },
        dataConnectionId: "old-connection",
      },
    ]);
  });

  it("omits a hidden database reference and sends crawl settings after switching to a website", async () => {
    const writes: unknown[] = [];
    server.use(
      http.post("*/api/v1/knowledge/collections/collection/sources", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json({ id: "source" });
      }),
    );
    show();
    fireEvent.change(screen.getByLabelText(messages.knowledge.name), {
      target: { value: "  Workspace pages  " },
    });
    fireEvent.change(screen.getByLabelText(messages.knowledge.sourceKind), {
      target: { value: "database" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Database connection:/ }));
    fireEvent.click(await screen.findByText("Workspace database"));
    fireEvent.change(screen.getByLabelText(messages.knowledge.sourceKind), {
      target: { value: "web" },
    });
    fireEvent.change(screen.getByLabelText(messages.knowledge.url), {
      target: { value: "https://workspace.invalid/docs" },
    });
    fireEvent.change(screen.getByLabelText(messages.knowledge.maxPages), {
      target: { value: "50" },
    });
    fireEvent.change(screen.getByLabelText(messages.knowledge.linkDepth), {
      target: { value: "1" },
    });
    fireEvent.click(screen.getByRole("button", { name: messages.knowledge.connect }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/knowledge/collection"));
    expect(writes).toEqual([
      {
        name: "Workspace pages",
        kind: "web",
        config: {
          start_urls: ["https://workspace.invalid/docs"],
          allowed_domains: ["workspace.invalid"],
          max_pages: 50,
          max_depth: 1,
        },
      },
    ]);
  });

  it("validates web protocols and keeps invalid JSON editable without saving", async () => {
    const writes: unknown[] = [];
    server.use(
      http.post("*/api/v1/knowledge/collections/collection/sources", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json({ id: "source" });
      }),
    );
    show();
    fireEvent.change(screen.getByLabelText(messages.knowledge.name), {
      target: { value: "Workspace source" },
    });
    fireEvent.change(screen.getByLabelText(messages.knowledge.url), {
      target: { value: "ftp://workspace.invalid/docs" },
    });
    fireEvent.click(screen.getByRole("button", { name: messages.knowledge.connect }));
    expect(await screen.findByText(messages.detail.invalidWebUrl)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(messages.knowledge.sourceKind), {
      target: { value: "database" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Database connection:/ }));
    fireEvent.click(await screen.findByText("Workspace database"));
    fireEvent.change(screen.getByLabelText(messages.knowledge.sourceKind), {
      target: { value: "s3" },
    });
    fireEvent.change(screen.getByLabelText(messages.detail.configuration), {
      target: { value: "[]" },
    });
    fireEvent.click(screen.getByRole("button", { name: messages.knowledge.connect }));
    expect(await screen.findByText(messages.detail.invalidConfig)).toBeTruthy();
    expect(writes).toEqual([]);
    fireEvent.change(screen.getByLabelText(messages.detail.configuration), {
      target: { value: '{"bucket":"workspace"}' },
    });
    fireEvent.click(screen.getByRole("button", { name: messages.knowledge.connect }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/knowledge/collection"));
    expect(writes).toEqual([
      { name: "Workspace source", kind: "s3", config: { bucket: "workspace" } },
    ]);
  });
});
