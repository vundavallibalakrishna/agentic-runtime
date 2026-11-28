import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReviewDetail } from "@/components/reviews/review-detail";
import * as stepUp from "@/lib/step-up";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/reviews",
  useRouter: () => ({ push: () => undefined, replace: () => undefined }),
}));

const item = {
  id: "item-1",
  subjectType: "saved_query",
  status: "pending",
  statementText: "Read the saved statement.",
  contentHash: "content-1",
  statementHash: "statement-1",
  preparerPrincipalId: "another-user",
};
function view(id = "item-1") {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <ReviewDetail reviewId={id} />
    </NextIntlClientProvider>
  );
}
function serveItem(overrides: Record<string, unknown> = {}) {
  server.use(
    http.get("*/api/v1/review-items/:id", ({ params }) =>
      HttpResponse.json({ ...item, id: params.id, ...overrides }),
    ),
  );
}

describe("review detail", () => {
  beforeEach(() => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          user: { id: "user-1" },
          permissions: ["reviews:read", "reviews:decide"],
        }),
      ),
    );
  });
  it("shows the query a saved-query item asks the signer to approve", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ user: { id: "user-1" }, permissions: ["reviews:decide"] }),
      ),
      http.get("*/api/v1/review-items/item-1", () =>
        HttpResponse.json({
          id: "item-1",
          subjectType: "saved_query",
          status: "pending",
          statementText: "I reviewed saved query Open items version 2.",
          contentHash: "abc",
          statementHash: "def",
          subjectRef: {
            name: "Open items",
            version: 2,
            description: "Items still open at the period end",
            sql: "SELECT * FROM items WHERE status = 'open'",
          },
        }),
      ),
    );
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <ReviewDetail reviewId="item-1" />
      </NextIntlClientProvider>,
    );
    expect(await screen.findByText("SELECT * FROM items WHERE status = 'open'")).toBeTruthy();
    expect(screen.getByText("Open items, version 2")).toBeTruthy();
    expect(screen.getByText("Items still open at the period end")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sign" })).toBeTruthy();
  });
  it("lets a reader inspect the statement without offering a decision", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ user: { id: "user-1" }, permissions: ["reviews:read"] }),
      ),
    );
    serveItem();
    render(view());
    expect(await screen.findByText(item.statementText)).toBeTruthy();
    expect(screen.getByText(messages.reviews.readOnly)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Sign" })).toBeNull();
    expect(screen.queryByLabelText("Comment")).toBeNull();
  });

  it.each([
    [{ preparerPrincipalId: "user-1" }, messages.reviews.selfReview],
    [{ contentHash: "" }, messages.reviews.missingHashes],
  ])("explains why signing is unavailable for %j", async (overrides, explanation) => {
    serveItem(overrides);
    render(view());
    expect(await screen.findByText(explanation)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Sign" })).toBeNull();
  });

  it("shows a settled review without signing controls", async () => {
    serveItem({ status: "signed" });
    render(view());
    expect(await screen.findByText("signed")).toBeTruthy();
    expect(screen.getByText(item.statementText)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Sign" })).toBeNull();
  });

  it("handles an unavailable review separately from a failed read", async () => {
    server.use(
      http.get("*/api/v1/review-items/:id", () =>
        HttpResponse.json({ detail: "Not found" }, { status: 404 }),
      ),
    );
    render(view());
    expect(await screen.findByText(messages.reviews.missing)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to reviews" }).getAttribute("href")).toBe(
      "/reviews",
    );
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("button", { name: "Sign" })).toBeNull();
  });

  it("retries a failed read without presenting stale content", async () => {
    server.use(
      http.get("*/api/v1/review-items/:id", () =>
        HttpResponse.json({ detail: "Unavailable" }, { status: 503 }),
      ),
    );
    render(view());
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Sign" })).toBeNull();
    serveItem();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(item.statementText)).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("keeps the comment and content after a refused decision", async () => {
    serveItem();
    let posted: unknown;
    server.use(
      http.post("*/api/v1/auth/step-up", () => HttpResponse.json({ steppedUp: "true" })),
      http.post("*/api/v1/review-items/item-1:decide", async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json({ detail: "Review has changed" }, { status: 409 });
      }),
    );
    render(view());
    fireEvent.change(await screen.findByLabelText("Comment"), {
      target: { value: "Please verify the changes." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign" }));
    expect(await screen.findByText("Review has changed")).toBeTruthy();
    expect(posted).toEqual({
      decision: "approve",
      comment: "Please verify the changes.",
      contentHash: item.contentHash,
      statementHash: item.statementHash,
    });
    expect((screen.getByLabelText("Comment") as HTMLTextAreaElement).value).toBe(
      "Please verify the changes.",
    );
    expect(screen.getByText(item.statementText)).toBeTruthy();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Sign" }).hasAttribute("disabled")).toBe(false),
    );
  });

  it("reads the saved status after a successful decision", async () => {
    let signed = false;
    server.use(
      http.get("*/api/v1/review-items/:id", () =>
        HttpResponse.json({ ...item, status: signed ? "signed" : "pending" }),
      ),
      http.post("*/api/v1/auth/step-up", () => HttpResponse.json({ steppedUp: "true" })),
      http.post("*/api/v1/review-items/item-1:decide", () => {
        signed = true;
        return HttpResponse.json({ ...item, status: "signed" });
      }),
    );
    render(view());
    fireEvent.click(await screen.findByRole("button", { name: "Sign" }));
    expect(await screen.findByText("signed")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Sign" })).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("resets comments and ignores an unfinished confirmation when the item changes", async () => {
    serveItem();
    let finish: (() => void) | undefined;
    let decisions = 0;
    const confirmation = vi.spyOn(stepUp, "confirmStepUp").mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve;
        }),
    );
    server.use(
      http.post("*/api/v1/review-items/item-1:decide", () => {
        decisions += 1;
        return HttpResponse.json({});
      }),
    );
    const { rerender } = render(view());
    fireEvent.change(await screen.findByLabelText("Comment"), {
      target: { value: "Only for the first review" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign" }));
    await waitFor(() => expect(finish).toBeTruthy());
    rerender(view("item-2"));
    expect(((await screen.findByLabelText("Comment")) as HTMLTextAreaElement).value).toBe("");
    await act(async () => {
      finish?.();
    });
    expect(decisions).toBe(0);
    confirmation.mockRestore();
    expect(screen.getByText("item-2")).toBeTruthy();
  });
});
