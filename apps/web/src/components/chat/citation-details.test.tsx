import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { delay, HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";
import messages from "@/messages/en.json";
import { server } from "@/test/server";
import { type CitationChip, CitationList } from "./citations";

function show(citations: CitationChip[] = [], messageId = "reply") {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <CitationList citations={citations} conversationId="conversation" messageId={messageId} />
    </NextIntlClientProvider>,
  );
}
const endpoint = "*/api/v1/conversations/conversation/messages/:messageId/grounding";
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
describe("chat source and grounding inspectors", () => {
  it("does not read on render and makes Why available on saved replies without citations", async () => {
    let calls = 0;
    server.use(
      http.get(endpoint, () => {
        calls++;
        return HttpResponse.json({ mode: "off", claims: [] });
      }),
    );
    show();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(calls).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "Why" }));
    await screen.findByText(messages.chat.whyNoClaims);
    expect(screen.getByText(messages.chat.groundingOff)).toBeTruthy();
    expect(calls).toBe(1);
  });
  it("keeps transient replies from showing a grounding action", () => {
    show([], "local-reply");
    expect(screen.queryByRole("button", { name: "Why" })).toBeNull();
  });
  it("lazily pages 100,000 citations, searches and filters them and preserves the source selection path", () => {
    show(
      Array.from({ length: 100_000 }, (_, offset) => ({
        index: offset + 1,
        title: `Source ${offset}`,
        snippet: `Passage ${offset}`,
        uri: `source:${offset}`,
        verified: offset < 2,
        documentId: `file/${offset}`,
        pageFrom: 2,
        pageTo: 4,
      })),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "100,000 sources" }));
    const dialog = screen.getByRole("dialog", { name: "Sources" });
    const list = within(dialog).getByRole("list");
    expect(within(list).getAllByRole("button")).toHaveLength(25);
    fireEvent.click(within(dialog).getByRole("button", { name: "Next" }));
    fireEvent.click(within(list).getByRole("button", { name: "[26] Source 25" }));
    expect(screen.getByRole("region", { name: messages.chat.sourcePassage }).textContent).toBe(
      "Passage 25",
    );
    expect(
      screen.getByRole("link", { name: messages.chat.openSourceDocument }).getAttribute("href"),
    ).toBe("/documents/file%2F25");
    expect(screen.getByText("Page 2–4")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: messages.chat.backToSources }));
    expect(screen.getByText("Page 2 of 4,000")).toBeTruthy();
    fireEvent.click(screen.getByRole("checkbox", { name: messages.chat.sourcesVerifiedOnly }));
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("1–2 of 2")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "no matching source" } });
    expect(screen.getByText(messages.chat.sourcesNoMatches)).toBeTruthy();
  });
  it("keeps duplicate citation labels distinct and shows missing passages honestly", () => {
    show([
      { index: 1, title: "same", snippet: "", uri: "source:one" },
      { index: 1, title: "same", snippet: "", uri: "source:two" },
    ]);
    fireEvent.click(screen.getByRole("button", { name: "2 sources" }));
    expect(screen.getAllByRole("button", { name: "[1] same" })).toHaveLength(2);
    fireEvent.click(screen.getAllByRole("button", { name: "[1] same" })[1] as HTMLElement);
    expect(screen.getByText("source:two")).toBeTruthy();
    expect(screen.getByText(messages.chat.sourceNoPassage)).toBeTruthy();
  });
  it("separates a missing report from server failure and retries explicitly", async () => {
    let calls = 0;
    server.use(
      http.get(endpoint, () => {
        calls++;
        return calls === 1
          ? new HttpResponse(null, { status: 404 })
          : calls === 2
            ? HttpResponse.json({ detail: "Storage is unavailable" }, { status: 503 })
            : HttpResponse.json({ mode: "preferred", claims: [] });
      }),
    );
    show();
    fireEvent.click(screen.getByRole("button", { name: "Why" }));
    await screen.findByText(messages.chat.whyUnavailable);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText("This answer was not checked.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: messages.chat.retry }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(/Storage is unavailable/)).toBeTruthy();
    expect(screen.queryByText(messages.chat.whyUnavailable)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: messages.detail.retry }));
    await screen.findByText(messages.chat.whyNoClaims);
    expect(calls).toBe(3);
  });
  it("bounds 100,000 claims, filters actual statuses, resets search pages and inspects only expanded records", async () => {
    server.use(
      http.get(endpoint, () =>
        HttpResponse.json({
          mode: "strict",
          claims: Array.from({ length: 100_000 }, (_, offset) => ({
            text: `Saved statement ${offset}`,
            status: offset < 2 ? "flagged" : "grounded",
            citationIndexes: [offset + 1],
          })),
        }),
      ),
    );
    show();
    fireEvent.click(screen.getByRole("button", { name: "Why" }));
    await screen.findByText(/Saved statement 24$/);
    expect(screen.getAllByRole("listitem")).toHaveLength(25);
    expect(screen.queryByRole("region", { name: messages.chat.claimDetails })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText(/Saved statement 25$/)).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: messages.chat.groundingStatus }), {
      target: { value: "flagged" },
    });
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    const details = screen.getByText(/Saved statement 0$/).closest("details") as HTMLDetailsElement;
    details.open = true;
    fireEvent(details, new Event("toggle"));
    expect(screen.getByRole("region", { name: messages.chat.claimDetails }).textContent).toContain(
      '"citationIndexes"',
    );
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "no matching claim" } });
    expect(screen.getByText(messages.chat.noClaimMatches)).toBeTruthy();
  });
  it.each([
    { claims: "invalid" },
    { claims: [null] },
    { claims: [{ text: 2, status: "grounded" }] },
  ])("surfaces an invalid report instead of fabricating an empty one (%j)", async ({ claims }) => {
    server.use(http.get(endpoint, () => HttpResponse.json({ mode: "strict", claims })));
    show();
    fireEvent.click(screen.getByRole("button", { name: "Why" }));
    await screen.findByRole("alert");
    expect(screen.getByText(new RegExp(messages.chat.whyInvalid))).toBeTruthy();
    expect(screen.queryByText(messages.chat.whyNoClaims)).toBeNull();
  });
  it("aborts closed reads and prevents an old reply from replacing the current one", async () => {
    const signals: AbortSignal[] = [];
    const fetcher = globalThis.fetch;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (init?.signal) signals.push(init.signal);
      return fetcher(input, init);
    });
    server.use(
      http.get(endpoint, async ({ params }) => {
        if (params.messageId === "reply") await delay(100);
        return HttpResponse.json({
          mode: "strict",
          claims: [{ text: `Report ${params.messageId}`, status: "grounded" }],
        });
      }),
    );
    const view = show();
    fireEvent.click(screen.getByRole("button", { name: "Why" }));
    expect(screen.getByText(messages.detail.loading)).toBeTruthy();
    view.rerender(
      <NextIntlClientProvider locale="en" messages={messages}>
        <CitationList citations={[]} conversationId="conversation" messageId="next" />
      </NextIntlClientProvider>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(signals[0]?.aborted).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Why" }));
    await screen.findByText(/Report next$/);
    await delay(150);
    expect(screen.queryByText(/Report reply$/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: messages.chat.closePreview }));
    await waitFor(() => expect(signals[1]?.aborted).toBe(true));
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole("button", { name: "Why" })),
    );
  });
});
