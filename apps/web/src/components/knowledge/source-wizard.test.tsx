import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SourceWizard } from "@/components/knowledge/source-wizard";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/knowledge/c1/sources/new",
  useRouter: () => ({ push: () => undefined }),
}));

function show() {
  server.use(http.get("*/api/v1/tenant", () => HttpResponse.json({ settings: {} })));
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <SourceWizard collectionId="c1" />
    </NextIntlClientProvider>,
  );
}

describe("source wizard", () => {
  afterEach(() => {
    cleanup();
  });

  it("starts each kind with the fields it needs and holds no credential field", () => {
    show();
    const kind = screen.getByLabelText("Source kind");
    fireEvent.change(kind, { target: { value: "s3" } });
    const s3 = JSON.parse(
      (screen.getByLabelText("Source configuration (JSON)") as HTMLTextAreaElement).value,
    );
    expect(Object.keys(s3)).toEqual(["bucket", "prefix", "endpoint", "region", "connection"]);
    expect(screen.getByText(/whose username is the access key/)).toBeTruthy();
    fireEvent.change(kind, { target: { value: "database" } });
    const database = JSON.parse(
      (screen.getByLabelText("Source configuration (JSON)") as HTMLTextAreaElement).value,
    );
    expect(database.idColumn).toBe("id");
    expect(screen.getByLabelText("Data connection (its name or ID)")).toBeTruthy();
    fireEvent.change(kind, { target: { value: "mcp_resource" } });
    expect(screen.getByText(/tool server registered in this workspace/)).toBeTruthy();
    // A key or password is a saved connection. No field here takes one.
    expect(screen.queryByLabelText(/secret/i)).toBeNull();
    expect(document.body.textContent).not.toMatch(/"items"|"objects"|"rows"|"resources"/);
  });

  it("sends the configuration and the data connection for a database source", async () => {
    let sent: Record<string, unknown> = {};
    server.use(
      http.post("*/api/v1/knowledge/collections/c1/sources", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "s1" });
      }),
    );
    show();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Articles" } });
    fireEvent.change(screen.getByLabelText("Source kind"), { target: { value: "database" } });
    fireEvent.change(screen.getByLabelText("Source configuration (JSON)"), {
      target: { value: '{"query": "SELECT id, title, text FROM articles"}' },
    });
    fireEvent.change(screen.getByLabelText("Data connection (its name or ID)"), {
      target: { value: "articles" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Connect source" }));
    await waitFor(() => expect(sent.kind).toBe("database"));
    expect(sent).toEqual({
      name: "Articles",
      kind: "database",
      config: { query: "SELECT id, title, text FROM articles" },
      dataConnectionId: "articles",
    });
  });
});
