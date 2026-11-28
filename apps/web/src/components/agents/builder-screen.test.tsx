import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BuilderScreen } from "@/components/agents/builder-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <BuilderScreen />
    </NextIntlClientProvider>,
  );
}
beforeEach(() => push.mockClear());

describe("agent creation", () => {
  it("keeps optional controls collapsed and creates a draft for review without publishing", async () => {
    const writes: { name: string; visibility: string; definition: { model: { alias: string } } }[] =
      [];
    const publish = vi.fn();
    server.use(
      http.get("*/api/v1/model-aliases", () =>
        HttpResponse.json({
          items: [
            { alias: "workspace-chat", kind: "chat" },
            { alias: "workspace-embed", kind: "embedding" },
          ],
        }),
      ),
      http.post("*/api/v1/agents", async ({ request }) => {
        writes.push((await request.json()) as (typeof writes)[number]);
        return HttpResponse.json({ id: "draft-agent" });
      }),
      http.post("*/api/v1/agents/draft-agent:publish", () => {
        publish();
        return HttpResponse.json({});
      }),
    );
    show();
    const manual = screen.getByText(messages.agents.createForm).closest("details");
    expect(manual?.open).toBe(false);
    fireEvent.click(screen.getByText(messages.agents.createForm));
    const form = within(manual as HTMLDetailsElement);
    await waitFor(() =>
      expect(form.getByRole("button", { name: "Model alias: workspace-chat" })).toBeTruthy(),
    );
    expect(form.queryByRole("option", { name: "reasoning" })).toBeNull();
    expect(form.queryByRole("option", { name: "workspace-embed" })).toBeNull();
    expect(form.getByText("General tools · 16 selected").closest("details")?.open).toBe(false);
    fireEvent.change(form.getByLabelText("Name"), { target: { value: "  Workspace helper  " } });
    fireEvent.change(form.getByLabelText("Instructions"), {
      target: { value: "Write concise updates" },
    });
    fireEvent.click(form.getByText("General tools · 16 selected"));
    fireEvent.change(form.getByLabelText("Timeout (seconds)"), { target: { value: "121" } });
    fireEvent.submit(
      form.getByRole("button", { name: "Create draft" }).closest("form") as HTMLFormElement,
    );
    expect(writes).toHaveLength(0);
    fireEvent.change(form.getByLabelText("Timeout (seconds)"), { target: { value: "30" } });
    fireEvent.click(form.getByRole("button", { name: "Create draft" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/agents/draft-agent"));
    expect(writes).toHaveLength(1);
    expect(writes[0]?.name).toBe("Workspace helper");
    expect(writes[0]?.visibility).toBe("private");
    expect(writes[0]?.definition.model.alias).toBe("workspace-chat");
    expect(publish).not.toHaveBeenCalled();
    expect(JSON.stringify(writes)).not.toContain("skipEvalGate");
  });

  it("does not invent a selectable model when loading assignments fails", async () => {
    let attempts = 0;
    server.use(
      http.get("*/api/v1/model-aliases", () =>
        ++attempts === 1
          ? HttpResponse.json({ detail: "Models unavailable" }, { status: 503 })
          : HttpResponse.json({ items: [{ alias: "tenant-chat", kind: "chat" }] }),
      ),
    );
    show();
    fireEvent.click(screen.getByText(messages.agents.createForm));
    await screen.findByText(messages.agents.noCreateModels);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Workspace helper" } });
    fireEvent.change(screen.getByLabelText("Instructions"), {
      target: { value: "Write concise updates" },
    });
    expect(screen.getByRole("button", { name: "Create draft" }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(screen.queryByRole("option", { name: "reasoning" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Model alias: tenant-chat" })).toBeTruthy(),
    );
    expect(screen.getByRole("button", { name: "Create draft" }).hasAttribute("disabled")).toBe(
      false,
    );
  });
  it("pages and searches a large alias catalogue without mounting native options", async () => {
    server.use(
      http.get("*/api/v1/model-aliases", () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, index) => ({
            alias: `tenant-chat-${index}`,
            kind: "chat",
          })),
        }),
      ),
    );
    show();
    fireEvent.click(screen.getByText(messages.agents.createForm));
    const trigger = await screen.findByRole("button", { name: "Model alias: tenant-chat-0" });
    expect(screen.queryAllByRole("option", { name: /tenant-chat-/ })).toHaveLength(0);
    fireEvent.click(trigger);
    let picker = within(screen.getByRole("dialog", { name: "Model alias" }));
    expect(picker.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.change(picker.getByRole("searchbox"), { target: { value: "tenant-chat-99999" } });
    fireEvent.click(picker.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Model alias: tenant-chat-0" })).toBeTruthy();
    fireEvent.click(trigger);
    picker = within(screen.getByRole("dialog", { name: "Model alias" }));
    fireEvent.change(picker.getByRole("searchbox"), { target: { value: "tenant-chat-99999" } });
    expect(picker.getAllByText("tenant-chat-99999")).toHaveLength(1);
    fireEvent.click(picker.getByRole("button", { name: /tenant-chat-99999/ }));
    expect(screen.getByRole("button", { name: "Model alias: tenant-chat-99999" })).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
