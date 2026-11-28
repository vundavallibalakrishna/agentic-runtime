import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { type ReactNode, useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { AliasDialog, ProviderDialog } from "@/components/models/dialogs";
import { UsesSection } from "@/components/models/sections";
import type { Alias, Model, StandardAlias } from "@/components/models/types";
import messages from "@/messages/en.json";

const providerNames = new Map([
  ["provider-1", "First service"],
  ["provider-2", "Second service"],
]);
function model(id: string, kind: Model["kind"] = "chat", capabilities: string[] = []): Model {
  return {
    id,
    name: id,
    providerId: "provider-1",
    upstreamModel: `upstream-${id}`,
    kind,
    capabilities,
    platform: false,
  };
}
function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}
const imageUse: StandardAlias = {
  alias: "vision",
  kind: "chat",
  required: false,
  capability: "vision",
  set: true,
  aliasId: "image-alias",
  modelId: "plain",
  modelName: "plain",
  platform: false,
};

describe("bounded model choice", () => {
  it("keeps 100,000 model choices out of closed defaults and pages/searches on demand", () => {
    const models = Array.from({ length: 100_000 }, (_, index) => model(`model-${index}`));
    const use: StandardAlias = {
      ...imageUse,
      alias: "reasoning",
      capability: null,
      required: true,
      modelId: "model-0",
      modelName: "model-0",
    };
    const onPoint = vi.fn();
    render(
      wrap(
        <UsesSection
          standard={[use]}
          models={models}
          providerNames={providerNames}
          canManage
          advanced={false}
          tests={{}}
          onPoint={onPoint}
          onTest={vi.fn()}
          onClear={vi.fn()}
          onOptions={vi.fn()}
        />,
      ),
    );
    expect(screen.queryAllByRole("option")).toHaveLength(0);
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /^Model for Answers:/ }));
    const picker = within(screen.getByRole("dialog", { name: "Model for Answers" }));
    expect(picker.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.click(picker.getByRole("button", { name: "Next" }));
    expect(picker.getByText("model-25 · First service")).toBeTruthy();
    fireEvent.change(picker.getByRole("searchbox"), { target: { value: "upstream-model-99999" } });
    expect(picker.getAllByRole("listitem")).toHaveLength(1);
    fireEvent.click(picker.getByText("model-99999 · First service"));
    expect(onPoint).toHaveBeenCalledWith(use, "model-99999");
    expect(screen.queryByRole("button", { name: "Clear Model for Answers" })).toBeNull();
  });

  it("shows provider context for equal names and searches by that context", () => {
    const models = [
      { ...model("first"), name: "Shared name" },
      { ...model("second"), name: "Shared name", providerId: "provider-2" },
    ];
    const use = {
      ...imageUse,
      alias: "reasoning",
      capability: null,
      modelId: "first",
      modelName: "Shared name",
    };
    render(
      wrap(
        <UsesSection
          standard={[use]}
          models={models}
          providerNames={providerNames}
          canManage
          advanced={false}
          tests={{}}
          onPoint={vi.fn()}
          onTest={vi.fn()}
          onClear={vi.fn()}
          onOptions={vi.fn()}
        />,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: /^Model for Answers:/ }));
    const picker = within(screen.getByRole("dialog"));
    expect(picker.getByText("Shared name · First service")).toBeTruthy();
    expect(picker.getByText("Shared name · Second service")).toBeTruthy();
    fireEvent.change(picker.getByRole("searchbox"), { target: { value: "Second service" } });
    expect(picker.queryByText("Shared name · First service")).toBeNull();
    expect(picker.getByText("Shared name · Second service")).toBeTruthy();
  });

  it("keeps alias choices staged until Save and clears selection when kind changes", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const models = [model("chat-model"), model("embedding-model", "embedding")];
    render(
      wrap(
        <AliasDialog
          target={{ alias: null }}
          standard={[]}
          providerNames={providerNames}
          models={models}
          onSave={onSave}
          onClose={vi.fn()}
        />,
      ),
    );
    fireEvent.change(screen.getByLabelText("Alias"), { target: { value: "custom_alias" } });
    fireEvent.click(screen.getByRole("button", { name: /^Model:/ }));
    fireEvent.click(
      within(screen.getByRole("dialog", { name: "Model" })).getByText("chat-model · First service"),
    );
    expect(onSave).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "embedding" } });
    expect(screen.getByRole("button", { name: /^Model:/ }).textContent).toContain(
      messages.referencePicker.choose,
    );
    fireEvent.click(screen.getByRole("button", { name: /^Model:/ }));
    const picker = within(screen.getByRole("dialog", { name: "Model" }));
    expect(picker.queryByText("chat-model · First service")).toBeNull();
    fireEvent.click(picker.getByText("embedding-model · First service"));
    expect(onSave).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Add alias" }));
    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith({
        alias: "custom_alias",
        kind: "embedding",
        modelId: "embedding-model",
        temperature: null,
      }),
    );
  });

  it("uses standard capability rules inside alias options and blocks an invalid saved choice", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const alias: Alias = {
      id: "image-alias",
      alias: "vision",
      kind: "chat",
      primaryModelId: "plain",
      platform: false,
    };
    render(
      wrap(
        <AliasDialog
          target={{ alias }}
          standard={[imageUse]}
          providerNames={providerNames}
          models={[model("plain"), model("image-capable", "chat", ["vision"])]}
          onSave={onSave}
          onClose={vi.fn()}
        />,
      ),
    );
    expect(await screen.findByText(messages.models.incompatibleAssignment)).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Model:/ }).textContent).toContain("plain");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(onSave).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /^Model:/ }));
    const picker = within(screen.getByRole("dialog", { name: "Model" }));
    expect(picker.queryByText("plain · First service")).toBeNull();
    fireEvent.click(picker.getByText("image-capable · First service"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ modelId: "image-capable" })),
    );
  });

  it("discards a cancelled new-alias draft when opening another new alias", () => {
    const onClose = vi.fn();
    const content = (target: { alias: Alias | null } | null) =>
      wrap(
        <AliasDialog
          target={target}
          standard={[]}
          providerNames={providerNames}
          models={[model("chat-model")]}
          onSave={vi.fn()}
          onClose={onClose}
        />,
      );
    const { rerender } = render(content({ alias: null }));
    fireEvent.change(screen.getByLabelText("Alias"), { target: { value: "discard_this" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
    rerender(content(null));
    rerender(content({ alias: null }));
    expect((screen.getByLabelText("Alias") as HTMLInputElement).value).toBe("");
    expect(screen.getByRole("button", { name: /^Model:/ }).textContent).toContain(
      messages.referencePicker.choose,
    );
  });
  it("freezes dialog fields and ignores another submit until the save settles", async () => {
    let finish: (() => void) | undefined;
    const onSave = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve;
        }),
    );
    render(
      wrap(
        <AliasDialog
          target={{ alias: null }}
          standard={[]}
          providerNames={providerNames}
          models={[model("chat-model")]}
          onSave={onSave}
          onClose={vi.fn()}
        />,
      ),
    );
    fireEvent.change(screen.getByLabelText("Alias"), { target: { value: "custom_alias" } });
    fireEvent.click(screen.getByRole("button", { name: /^Model:/ }));
    fireEvent.click(
      within(screen.getByRole("dialog", { name: "Model" })).getByText("chat-model · First service"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Add alias" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("group", { name: "Add alias" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByText(messages.detail.working)).toBeTruthy();
    const form = screen.getByRole("dialog", { name: "Add alias" }).querySelector("form");
    if (!form) throw new Error("Expected alias form");
    fireEvent.submit(form);
    expect(onSave).toHaveBeenCalledTimes(1);
    await act(async () => {
      finish?.();
    });
    expect(screen.getByRole("group", { name: "Add alias" }).hasAttribute("disabled")).toBe(false);
  });
  it("applies known default requirements when creating an alias with that name", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      wrap(
        <AliasDialog
          target={{ alias: null }}
          standard={[imageUse]}
          providerNames={providerNames}
          models={[model("plain"), model("image-capable", "chat", ["vision"])]}
          onSave={onSave}
          onClose={vi.fn()}
        />,
      ),
    );
    fireEvent.change(screen.getByLabelText("Alias"), { target: { value: "vision" } });
    const kind = screen.getByLabelText("Kind") as HTMLSelectElement;
    expect(kind.value).toBe("chat");
    expect(kind.disabled).toBe(true);
    expect(screen.getByText(messages.models.standardKindHelp)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /^Model:/ }));
    const picker = within(screen.getByRole("dialog", { name: "Model" }));
    expect(picker.queryByText("plain · First service")).toBeNull();
    fireEvent.click(picker.getByText("image-capable · First service"));
    fireEvent.click(screen.getByRole("button", { name: "Add alias" }));
    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({ alias: "vision", kind: "chat", modelId: "image-capable" }),
      ),
    );
  });

  it("describes a missing capability without claiming that no chat model exists", () => {
    const alias: Alias = {
      id: "image-alias",
      alias: "vision",
      kind: "chat",
      primaryModelId: "plain",
      platform: false,
    };
    render(
      wrap(
        <AliasDialog
          target={{ alias }}
          standard={[imageUse]}
          providerNames={providerNames}
          models={[model("plain")]}
          onSave={vi.fn()}
          onClose={vi.fn()}
        />,
      ),
    );
    expect(screen.getByText(messages.models.needs.vision)).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Model:/ }).hasAttribute("disabled")).toBe(true);
    expect(screen.queryByText(/No chat model yet/)).toBeNull();
  });
});

describe("model form focus", () => {
  function Host({ removeOpener = false }: { removeOpener?: boolean }) {
    const [open, setOpen] = useState(false);
    const [removed, setRemoved] = useState(false);
    return (
      <>
        <main id="main-content" tabIndex={-1} />
        {!removed ? (
          <button type="button" onClick={() => setOpen(true)}>
            Edit connection
          </button>
        ) : null}
        <ProviderDialog
          provider={
            open
              ? {
                  id: "provider-1",
                  name: "Service",
                  hasApiKey: false,
                  baseUrl: "https://models.example.com",
                  kind: "openai_compatible",
                  platform: false,
                }
              : null
          }
          onClose={() => {
            setOpen(false);
            if (removeOpener) setRemoved(true);
          }}
          onSave={async () => {}}
        />
      </>
    );
  }

  it("returns focus to the actual form opener after Cancel", async () => {
    render(wrap(<Host />));
    const opener = screen.getByRole("button", { name: "Edit connection" });
    opener.focus();
    fireEvent.click(opener);
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it("moves focus to the workspace when its opener was removed", async () => {
    render(wrap(<Host removeOpener />));
    const opener = screen.getByRole("button", { name: "Edit connection" });
    opener.focus();
    fireEvent.click(opener);
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() =>
      expect(document.activeElement).toBe(document.getElementById("main-content")),
    );
  });
});
