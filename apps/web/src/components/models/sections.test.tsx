import { fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { AliasesSection, ProvidersSection } from "@/components/models/sections";
import type { Alias, Model, Provider } from "@/components/models/types";
import messages from "@/messages/en.json";

function show(children: ReactNode) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>,
  );
}
const provider = (index: number): Provider => ({
  id: `provider-${index}`,
  name: `Provider ${index}`,
  kind: "openai_compatible",
  baseUrl: `https://endpoint-${index}.invalid/v1`,
  hasApiKey: true,
  platform: false,
});
const model = (index: number, providerId: string): Model => ({
  id: `model-${index}`,
  providerId,
  name: `Model ${index}`,
  upstreamModel: `upstream-${index}`,
  kind: index % 2 ? "embedding" : "chat",
  platform: false,
});
const actions = () => ({
  onTestProvider: vi.fn(),
  onEditProvider: vi.fn(),
  onRemoveProvider: vi.fn(),
  onAddModel: vi.fn(),
  onTestModel: vi.fn(),
  onEditModel: vi.fn(),
  onRemoveModel: vi.fn(),
});

describe("model registry lists", () => {
  it("bounds 100,000 provider groups and finds a matching model across provider pages", () => {
    const providers = Array.from({ length: 100_000 }, (_, index) => provider(index));
    const models = providers.map((item, index) => model(index, item.id));
    const callbacks = actions();
    show(
      <ProvidersSection
        providers={providers}
        models={models}
        canManage
        advanced={false}
        tests={{}}
        {...callbacks}
      />,
    );
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(25);
    expect(screen.queryByText("Model 0")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "Provider 25" })).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.models.findProviderModel }), {
      target: { value: "upstream-99999" },
    });
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "Provider 99999" })).toBeTruthy();
    expect(screen.getByText("Model 99999")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Edit Model 99999" }));
    expect(callbacks.onEditModel).toHaveBeenCalledWith(providers[99999], models[99999]);
    fireEvent.change(screen.getByRole("combobox", { name: "Model type" }), {
      target: { value: "chat" },
    });
    expect(screen.getByText(messages.models.noRegistryMatches)).toBeTruthy();
    expect(screen.queryByRole("heading", { level: 3 })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByRole("heading", { name: "Provider 0" })).toBeTruthy();
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(25);
  });

  it("pages 100,000 models within one provider and resets its page on a global search", () => {
    const saved = provider(0);
    const models = Array.from({ length: 100_000 }, (_, index) => model(index, saved.id));
    show(
      <ProvidersSection
        providers={[saved]}
        models={models}
        canManage
        advanced={false}
        tests={{}}
        {...actions()}
      />,
    );
    const rows = within(screen.getByRole("list", { name: "Models under Provider 0" }));
    expect(rows.getAllByRole("listitem")).toHaveLength(25);
    expect(rows.getByText("Model 0")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(rows.getByText("Model 25")).toBeTruthy();
    expect(rows.queryByText("Model 0")).toBeNull();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.models.findProviderModel }), {
      target: { value: "upstream-99999" },
    });
    expect(screen.getByText("Model 99999")).toBeTruthy();
    expect(
      within(screen.getByRole("list", { name: "Models under Provider 0" })).getAllByRole(
        "listitem",
      ),
    ).toHaveLength(1);
  });

  it("keeps a provider without models visible and preserves read-only actions", () => {
    const callbacks = actions();
    show(
      <ProvidersSection
        providers={[provider(0)]}
        models={[]}
        canManage={false}
        advanced={false}
        tests={{}}
        {...callbacks}
      />,
    );
    expect(screen.getByText(messages.models.noModels)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Test Provider 0" }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(screen.queryByRole("button", { name: "Add model to Provider 0" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Edit Provider 0" })).toBeNull();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.models.findProviderModel }), {
      target: { value: "endpoint-0" },
    });
    expect(screen.getByRole("heading", { name: "Provider 0" })).toBeTruthy();
  });

  it("bounds 100,000 additional aliases and searches beyond the first page", () => {
    const aliases: Alias[] = Array.from({ length: 100_000 }, (_, index) => ({
      id: `alias-${index}`,
      alias: `alias_${index}`,
      kind: "chat",
      primaryModelId: "model-0",
      platform: false,
    }));
    show(
      <AliasesSection
        aliases={aliases}
        models={[model(0, "provider-0")]}
        canManage={false}
        tests={{}}
        onAdd={vi.fn()}
        onEdit={vi.fn()}
        onTest={vi.fn()}
        onRemove={vi.fn()}
      />,
    );
    const rows = within(screen.getByRole("list", { name: messages.models.aliasesTitle }));
    expect(rows.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(rows.getByText("alias_25")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.models.findAlias }), {
      target: { value: "alias_99999" },
    });
    expect(rows.getAllByRole("listitem")).toHaveLength(1);
    expect(rows.getByText("alias_99999")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.models.findAlias }), {
      target: { value: "not returned" },
    });
    expect(rows.getByText(messages.models.noRegistryMatches)).toBeTruthy();
  });
});
