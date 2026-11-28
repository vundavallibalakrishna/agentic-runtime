import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/en.json";
import { server } from "@/test/server";

import { SkillEditor } from "./skill-editor";

vi.mock("next/navigation", () => ({
  useParams: () => ({ skillId: "skill" }),
  usePathname: () => "/skills/skill",
  useRouter: () => ({ push: () => undefined, replace: () => undefined }),
}));
const saved = {
  id: "skill",
  slug: "writing",
  name: "Writing",
  status: "published",
  publishedVersion: 1,
  draft: {
    version: 0,
    instructionsMd: "Working text",
    requiredTools: ["unlisted.requirement"],
    assets: [],
  },
};
function view() {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <SkillEditor />
    </NextIntlClientProvider>
  );
}
function tab(name: string) {
  fireEvent.mouseDown(screen.getByRole("tab", { name }), { button: 0, ctrlKey: false });
}
async function resources() {
  await screen.findByRole("textbox", { name: "Instructions" });
  fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
  tab("Tools and files");
}
beforeEach(() => {
  localStorage.clear();
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({
        user: { id: "person", displayName: "Admin" },
        permissions: ["skills:read", "skills:manage_all", "tools:read", "agents:read"],
      }),
    ),
    http.get("*/api/v1/skills/skill", () => HttpResponse.json(saved)),
    http.get("*/api/v1/skills/skill/versions", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/skills/skill/where-used", () => HttpResponse.json({ agents: [] })),
  );
});
afterEach(cleanup);
describe("skill editing", () => {
  it("preserves unsaved text when version loading fails and retries independently", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/skills/skill/versions", () =>
        ++reads === 1
          ? HttpResponse.json({ detail: "History unavailable" }, { status: 503 })
          : HttpResponse.json({
              items: [{ version: 1, instructionsMd: "Published text", hash: "saved-hash" }],
            }),
      ),
    );
    render(view());
    const input = await screen.findByRole("textbox", { name: "Instructions" });
    fireEvent.change(input, { target: { value: "Unsaved procedure" } });
    tab("Versions");
    expect(await screen.findByRole("alert")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    fireEvent.click(await screen.findByRole("button", { name: "View version 1" }));
    expect(await within(screen.getByRole("dialog")).findByText("Published text")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    tab("Instructions");
    expect(
      (screen.getByRole("textbox", { name: "Instructions" }) as HTMLTextAreaElement).value,
    ).toBe("Unsaved procedure");
  });
  it("paginates version history and dependency results with filter page resets", async () => {
    server.use(
      http.get("*/api/v1/skills/skill/versions", () =>
        HttpResponse.json({ items: Array.from({ length: 30 }, (_, i) => ({ version: i + 1 })) }),
      ),
      http.get("*/api/v1/skills/skill/where-used", () =>
        HttpResponse.json({
          agents: Array.from({ length: 30 }, (_, i) => ({
            agentId: `agent-${i}`,
            name: `Agent ${i}`,
            state: i === 29 ? "draft" : "published",
            updateAvailable: i === 29,
          })),
        }),
      ),
    );
    render(view());
    await screen.findByRole("textbox", { name: "Instructions" });
    tab("Versions");
    await screen.findByText("v1");
    expect(screen.queryByText("v30")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("v30")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "v1" } });
    expect(screen.getByText("v1")).toBeTruthy();
    tab("Where used");
    await screen.findByText("Agent 0");
    expect(screen.queryByText("Agent 29")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Agent 29")).toBeTruthy();
    fireEvent.click(screen.getByRole("checkbox", { name: "Updates available only" }));
    expect(screen.getByText("Agent 29")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "Review agent" })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Review agent" }).getAttribute("href")).toBe(
      "/agents/agent-29",
    );
    expect(screen.queryByRole("button", { name: "Republish dependants" })).toBeNull();
  });
  it("saves named tool selections without removing unlisted existing requirements", async () => {
    const writes: Record<string, unknown>[] = [];
    server.use(
      http.get("*/api/v1/tools", () =>
        HttpResponse.json({
          items: [{ toolId: "tool", qualifiedName: "workspace.query", title: "Query records" }],
        }),
      ),
      http.patch("*/api/v1/skills/skill", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        writes.push(body);
        return HttpResponse.json({ ...saved, draft: { ...saved.draft, ...body } });
      }),
    );
    render(view());
    await resources();
    fireEvent.click(screen.getByRole("button", { name: "Required tools" }));
    fireEvent.click(
      await screen.findByRole("checkbox", { name: "Query records (workspace.query)" }),
    );
    expect(within(screen.getByRole("dialog")).getByText("workspace.query")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Use selected (2)" }));
    expect(screen.getByText("unlisted.requirement")).toBeTruthy();
    expect(screen.getByText("workspace.query")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("Draft saved.")).toBeTruthy();
    expect(writes).toEqual([
      {
        instructionsMd: "Working text",
        requiredTools: ["unlisted.requirement", "workspace.query"],
      },
    ]);
  });
  it("reports a saved draft when publish fails and preserves the change note", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/skills/skill", () => {
        reads++;
        return HttpResponse.json(saved);
      }),
      http.patch("*/api/v1/skills/skill", async ({ request }) =>
        HttpResponse.json({
          ...saved,
          draft: { ...saved.draft, ...((await request.json()) as object) },
        }),
      ),
      http.post("*/api/v1/skills/skill:publish", () =>
        HttpResponse.json({ detail: "Required tool is unavailable" }, { status: 422 }),
      ),
    );
    render(view());
    const input = await screen.findByRole("textbox", { name: "Instructions" });
    fireEvent.change(input, { target: { value: "New procedure" } });
    fireEvent.change(screen.getByLabelText("Change note"), { target: { value: "Clearer steps" } });
    fireEvent.click(screen.getByRole("button", { name: "Publish" }));
    expect(await screen.findByText("Required tool is unavailable")).toBeTruthy();
    expect(screen.getByText("Draft saved.")).toBeTruthy();
    expect(
      (screen.getByRole("textbox", { name: "Instructions" }) as HTMLTextAreaElement).value,
    ).toBe("New procedure");
    expect((screen.getByLabelText("Change note") as HTMLInputElement).value).toBe("Clearer steps");
    expect(reads).toBe(1);
  });
  it("validates an explicit asset path and retries attachment without another upload", async () => {
    let uploads = 0;
    const patches: Record<string, unknown>[] = [];
    server.use(
      http.post("*/api/v1/files:upload", () => {
        uploads++;
        return HttpResponse.json({ id: "file" });
      }),
      http.patch("*/api/v1/skills/skill", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        patches.push(body);
        return patches.length === 1
          ? HttpResponse.json({ detail: "Attachment unavailable" }, { status: 503 })
          : HttpResponse.json({ ...saved, draft: { ...saved.draft, ...body } });
      }),
    );
    render(view());
    await resources();
    fireEvent.change(screen.getByLabelText("Asset"), {
      target: { files: [new File(["source"], "My file.txt", { type: "text/plain" })] },
    });
    expect(screen.getByRole("button", { name: "Attach asset" }).hasAttribute("disabled")).toBe(
      true,
    );
    fireEvent.change(screen.getByLabelText("Relative asset path"), {
      target: { value: "notes/source..txt" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Attach asset" }));
    expect(await screen.findByText("Attachment unavailable")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Attach asset" }));
    expect(await screen.findByText("Asset added.")).toBeTruthy();
    expect(uploads).toBe(1);
    expect(patches).toEqual(
      Array(2).fill({
        instructionsMd: "Working text",
        requiredTools: ["unlisted.requirement"],
        assets: [{ path: "notes/source..txt", fileId: "file" }],
      }),
    );
  });
  it("handles export failure and gates new-skill import by its creation permission", async () => {
    server.use(
      http.post("*/api/v1/skills/skill:export", () =>
        HttpResponse.json({ detail: "Export unavailable" }, { status: 503 }),
      ),
    );
    render(view());
    await resources();
    expect(screen.queryByLabelText("Import as a new skill")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Export" }));
    expect(await screen.findByText("Export unavailable")).toBeTruthy();
    expect(screen.getByText("unlisted.requirement")).toBeTruthy();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Export" }).closest("fieldset")?.disabled).toBe(
        false,
      ),
    );
  });
  it("allows an empty working draft while keeping publish unavailable", async () => {
    const writes: unknown[] = [];
    server.use(
      http.patch("*/api/v1/skills/skill", async ({ request }) => {
        const body = (await request.json()) as object;
        writes.push(body);
        return HttpResponse.json({ ...saved, draft: { ...saved.draft, ...body } });
      }),
    );
    render(view());
    fireEvent.change(await screen.findByRole("textbox", { name: "Instructions" }), {
      target: { value: "" },
    });
    expect(screen.getByRole("button", { name: "Publish" }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("Draft saved.")).toBeTruthy();
    expect(writes).toEqual([{ instructionsMd: "", requiredTools: ["unlisted.requirement"] }]);
  });

  it("reports local import reading failure without creating a skill", async () => {
    let writes = 0;
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          user: { id: "person" },
          permissions: ["skills:read", "skills:manage_all", "skills:create"],
        }),
      ),
      http.post("*/api/v1/skills:import", () => {
        writes++;
        return HttpResponse.json({ id: "new" });
      }),
    );
    render(view());
    await resources();
    const file = new File(["procedure"], "procedure.md", { type: "text/markdown" });
    Object.defineProperty(file, "text", {
      value: async () => {
        throw new Error("File could not be read");
      },
    });
    fireEvent.change(screen.getByLabelText("Import as a new skill"), { target: { files: [file] } });
    expect(await screen.findByText("File could not be read")).toBeTruthy();
    expect(writes).toBe(0);
    tab("Instructions");
    expect(
      (screen.getByRole("textbox", { name: "Instructions" }) as HTMLTextAreaElement).value,
    ).toBe("Working text");
  });
  it("downloads the returned archive with its filename and releases the object URL", async () => {
    let captured: Blob | null = null;
    let filename = "";
    const createDescriptor = Object.getOwnPropertyDescriptor(URL, "createObjectURL");
    const revokeDescriptor = Object.getOwnPropertyDescriptor(URL, "revokeObjectURL");
    const revoke = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: (blob: Blob) => {
        captured = blob;
        return "blob:skill-export";
      },
    });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revoke });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      filename = this.download;
    });
    server.use(
      http.post("*/api/v1/skills/skill:export", () =>
        HttpResponse.json({
          filename: "saved-procedure.zip",
          archiveB64: "UEsDBA==",
          markdown: "Do not download this field",
        }),
      ),
    );
    try {
      render(view());
      await resources();
      fireEvent.click(screen.getByRole("button", { name: "Export" }));
      expect(await screen.findByText("Download started.")).toBeTruthy();
      expect(filename).toBe("saved-procedure.zip");
      expect(captured).toHaveProperty("type", "application/zip");
      expect(captured).toHaveProperty("size", 4);
      await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:skill-export"), {
        timeout: 2000,
      });
    } finally {
      click.mockRestore();
      if (createDescriptor) Object.defineProperty(URL, "createObjectURL", createDescriptor);
      else Reflect.deleteProperty(URL, "createObjectURL");
      if (revokeDescriptor) Object.defineProperty(URL, "revokeObjectURL", revokeDescriptor);
      else Reflect.deleteProperty(URL, "revokeObjectURL");
    }
  });
  it("distinguishes a saved unpublished draft from the published version", async () => {
    server.use(
      http.get("*/api/v1/skills/skill", () =>
        HttpResponse.json({
          ...saved,
          draft: { ...saved.draft, hash: "draft-hash" },
          published: { version: 1, instructionsMd: "Earlier text", hash: "published-hash" },
        }),
      ),
    );
    render(view());
    expect(await screen.findByText("Draft changes not published")).toBeTruthy();
    expect(screen.getByText("Published v1")).toBeTruthy();
    expect(screen.queryByText("Unsaved changes")).toBeNull();
    expect(screen.getByRole("button", { name: "Save draft" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Publish" }).hasAttribute("disabled")).toBe(false);
  });
});
