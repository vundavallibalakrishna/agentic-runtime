import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, expect, it, vi } from "vitest";
import { ModelDialog } from "@/components/models/dialogs";
import messages from "@/messages/en.json";

const t = messages.models;
afterEach(cleanup);
const provider = {
  id: "provider",
  name: "Provider",
  kind: "openai_compatible",
  baseUrl: "https://endpoint.invalid",
  hasApiKey: false,
  platform: false,
};
function show(onSave: () => Promise<void>) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ModelDialog
        target={{ provider, model: null }}
        standard={[]}
        advanced
        onClose={() => undefined}
        onSave={onSave}
      />
    </NextIntlClientProvider>,
  );
}
it("preserves exact price micros at the safe-integer boundary", async () => {
  const saved = vi.fn(async () => undefined);
  show(saved);
  fireEvent.change(screen.getByLabelText(t.upstream), { target: { value: "upstream" } });
  fireEvent.change(screen.getByLabelText(t.priceInput), { target: { value: "9007199254.740991" } });
  fireEvent.change(screen.getByLabelText(t.priceOutput), { target: { value: "0.000001" } });
  fireEvent.click(screen.getByRole("button", { name: t.addModel }));
  await waitFor(() =>
    expect(saved).toHaveBeenCalledWith(
      expect.objectContaining({ priceIn: Number.MAX_SAFE_INTEGER, priceOut: 1 }),
    ),
  );
});
it("keeps the entered price and refuses unsupported precision without saving", async () => {
  const saved = vi.fn(async () => undefined);
  show(saved);
  fireEvent.change(screen.getByLabelText(t.upstream), { target: { value: "upstream" } });
  const input = screen.getByLabelText(t.priceInput);
  fireEvent.change(input, { target: { value: "9007199254.740992" } });
  fireEvent.click(screen.getByRole("button", { name: t.addModel }));
  await screen.findByText(t.invalidPrice);
  expect(saved).not.toHaveBeenCalled();
  expect((input as HTMLInputElement).value).toBe("9007199254.740992");
});
