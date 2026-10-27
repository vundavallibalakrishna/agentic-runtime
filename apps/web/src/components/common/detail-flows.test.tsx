import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { delay, HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AgentEditor } from "@/components/agents/editor";
import { ApprovalDetail } from "@/components/approvals/approval-detail";
import { CollectionScreen } from "@/components/knowledge/collection-screen";
import { SkillEditor } from "@/components/skills/skill-editor";
import { formatCost } from "@/lib/format";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "agent", skillId: "skill" }),
  usePathname: () => "/agents/agent",
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock("next/dynamic", () => ({ default: () => () => null }));
function wrap(child: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {child}
    </NextIntlClientProvider>
  );
}
beforeEach(() => {
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ user: { displayName: "Admin" }, permissions: ["skills:manage_all"] }),
    ),
  );
});
afterEach(cleanup);

describe("detail flow failures", () => {
  it("does not publish or validate an agent after the draft save fails", async () => {
    const publish = vi.fn();
    const validate = vi.fn();
    server.use(
      http.get("*/api/v1/agents/agent", () =>
        HttpResponse.json({
          id: "agent",
          name: "Helper",
          canEdit: true,
          draft: { definition: { instructions: "Original instructions" } },
        }),
      ),
      http.get("*/api/v1/agents/agent/versions", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents/agent/memory", () => HttpResponse.json({ items: [] })),
      http.put("*/api/v1/agents/agent/versions/draft", () =>
        HttpResponse.json({ detail: "Draft could not be saved" }, { status: 503 }),
      ),
      http.post("*/api/v1/agents/agent:publish", () => {
        publish();
        return HttpResponse.json({});
      }),
      http.post("*/api/v1/agents/agent:validate", () => {
        validate();
        return HttpResponse.json({ valid: true });
      }),
    );
    render(wrap(<AgentEditor />));
    fireEvent.change(await screen.findByLabelText("Instructions"), {
      target: { value: "Changed instructions" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Publish" }));
    expect(await screen.findByText("Draft could not be saved")).toBeTruthy();
    expect(publish).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    expect((screen.getByLabelText("Instructions") as HTMLTextAreaElement).value).toBe(
      "Changed instructions",
    );
    fireEvent.click(screen.getByRole("button", { name: "Validate" }));
    await waitFor(() =>
      expect((screen.getByRole("button", { name: "Validate" }) as HTMLButtonElement).disabled).toBe(
        false,
      ),
    );
    expect(validate).not.toHaveBeenCalled();
  });

  it("does not publish a skill after saving fails", async () => {
    const publish = vi.fn();
    server.use(
      http.get("*/api/v1/skills/skill", () =>
        HttpResponse.json({
          id: "skill",
          name: "Writing",
          draft: { instructionsMd: "Be concise" },
        }),
      ),
      http.get("*/api/v1/skills/skill/versions", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/skills/skill/where-used", () => HttpResponse.json({ agents: [] })),
      http.patch("*/api/v1/skills/skill", () =>
        HttpResponse.json({ detail: "Save failed" }, { status: 503 }),
      ),
      http.post("*/api/v1/skills/skill:publish", () => {
        publish();
        return HttpResponse.json({});
      }),
    );
    render(wrap(<SkillEditor />));
    fireEvent.click(await screen.findByRole("button", { name: "Publish" }));
    expect(await screen.findByText("Save failed")).toBeTruthy();
    expect(publish).not.toHaveBeenCalled();
  });

  it("lets skill readers inspect published content without offering edit actions", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ user: { id: "reader" }, permissions: ["skills:read"] }),
      ),
      http.get("*/api/v1/skills/skill", () =>
        HttpResponse.json({
          id: "skill",
          name: "Writing",
          owner: { id: "owner" },
          published: { instructionsMd: "Be concise" },
        }),
      ),
      http.get("*/api/v1/skills/skill/versions", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/skills/skill/where-used", () => HttpResponse.json({ agents: [] })),
    );
    render(wrap(<SkillEditor />));
    const publish = await screen.findByRole("button", { name: "Publish" });
    expect((publish as HTMLButtonElement).disabled).toBe(true);
    expect(
      (screen.getByRole("textbox", { name: "Instructions" }) as HTMLTextAreaElement).readOnly,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    expect(
      (screen.getByLabelText("Required tools, separated by commas") as HTMLInputElement).readOnly,
    ).toBe(true);
  });

  it("keeps decisions disabled in flight and removes the form when completed", async () => {
    let status = "pending";
    let decisions = 0;
    server.use(
      http.get("*/api/v1/approvals/approval", () =>
        HttpResponse.json({
          id: "approval",
          qualifiedName: "tickets.create",
          status,
          argsHash: "hash",
        }),
      ),
      http.post("*/api/v1/approvals/approval:decide", async () => {
        decisions++;
        await delay(100);
        status = "approved";
        return HttpResponse.json({});
      }),
    );
    render(wrap(<ApprovalDetail approvalId="approval" />));
    const approve = await screen.findByRole("button", { name: "Approve" });
    fireEvent.click(approve);
    expect((approve as HTMLButtonElement).disabled).toBe(true);
    await waitFor(() => expect(screen.queryByRole("button", { name: "Approve" })).toBeNull());
    expect(decisions).toBe(1);
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("shows upload failures and retains the selected file for retry", async () => {
    let attempts = 0;
    server.use(
      http.get("*/api/v1/knowledge/collections/collection", () =>
        HttpResponse.json({ id: "collection", name: "Library", canManage: true }),
      ),
      ...["documents", "sources", "jobs"].map((part) =>
        http.get(`*/api/v1/knowledge/collections/collection/${part}`, () =>
          HttpResponse.json({ items: [] }),
        ),
      ),
      http.post("*/api/v1/files:upload", () => {
        attempts++;
        return HttpResponse.json({ detail: "Upload unavailable" }, { status: 503 });
      }),
    );
    render(wrap(<CollectionScreen collectionId="collection" />));
    const input = await screen.findByLabelText("Add a file");
    fireEvent.change(input, {
      target: { files: [new File(["hello"], "hello.txt", { type: "text/plain" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add a file" }));
    expect(await screen.findByText("Upload unavailable")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Add a file" }));
    await waitFor(() => expect(attempts).toBe(2));
  });
});

it("formats costs from micros without inflating the displayed amount", () => {
  expect(formatCost(1_250_000, "USD")).toBe("$1.25");
  expect(formatCost(1200, "INR")).toBe("₹0.0012");
});
