import { fireEvent, render, screen, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InboxScreen } from "@/components/inbox/inbox-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/inbox",
  useParams: () => ({}),
  useRouter: () => ({ push: () => undefined }),
}));
function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <InboxScreen />
    </NextIntlClientProvider>,
  );
}
beforeEach(() =>
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["chat:use"] })),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
  ),
);

describe("inbox queue", () => {
  it("pages loaded requests and finds approvals with a direct detail link", async () => {
    server.use(
      http.get("*/api/v1/inbox", () =>
        HttpResponse.json({
          items: Array.from({ length: 30 }, (_, i) => ({
            id: `item-${i}`,
            type: i === 29 ? "approval" : "question",
            question: `Request ${i}`,
            runId: `run-${i}`,
          })),
        }),
      ),
    );
    show();
    await screen.findByText("Request 0");
    expect(within(screen.getByRole("main")).getAllByRole("listitem")).toHaveLength(25);
    expect(screen.queryByText("Request 29")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Request 29")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.inbox.search }), {
      target: { value: "item-29" },
    });
    expect(
      screen.getByRole("link", { name: messages.inbox.reviewApproval }).getAttribute("href"),
    ).toBe("/approvals/item-29");
    fireEvent.change(screen.getByLabelText("Item type"), { target: { value: "question" } });
    expect(screen.getByText(messages.inbox.noMatches)).toBeTruthy();
  });

  it("requires an answer and retains it when submission fails", async () => {
    let attempts = 0;
    let answered = false;
    const writes: unknown[] = [];
    server.use(
      http.get("*/api/v1/inbox", () =>
        HttpResponse.json({
          items: answered
            ? []
            : [{ id: "question", type: "question", question: "What should happen next?" }],
        }),
      ),
      http.post("*/api/v1/inbox/question:answer", async ({ request }) => {
        writes.push(await request.json());
        if (++attempts === 1)
          return HttpResponse.json({ detail: "Answer unavailable" }, { status: 503 });
        answered = true;
        return HttpResponse.json({});
      }),
    );
    show();
    const input = (await screen.findByLabelText("Your answer")) as HTMLTextAreaElement;
    expect(input.tagName).toBe("TEXTAREA");
    expect(input.required).toBe(true);
    expect(screen.getByRole("button", { name: "Send" }).hasAttribute("disabled")).toBe(true);
    fireEvent.change(input, { target: { value: "Please continue with the summary." } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("alert");
    expect(input.value).toBe("Please continue with the summary.");
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText(messages.inbox.sent)).toBeTruthy();
    expect(await screen.findByText(messages.inbox.empty)).toBeTruthy();
    expect(writes).toEqual(Array(2).fill({ text: "Please continue with the summary." }));
  });
});
