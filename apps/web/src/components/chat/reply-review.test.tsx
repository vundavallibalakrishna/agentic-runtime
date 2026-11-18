import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AcceptReply, ReplyReviewStatus } from "@/components/chat/reply-review";
import messages from "@/messages/en.json";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

function answer(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("Reply review", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("labels a reply as AI-generated and not reviewed, also before the API has said so", () => {
    render(wrap(<ReplyReviewStatus review={null} />));
    const label = screen.getByTestId("reply-review");
    expect(label.textContent).toBe("Review status: AI-generated · not reviewed");
    cleanup();
    render(wrap(<ReplyReviewStatus review={{ status: "unreviewed", canAccept: true }} />));
    expect(screen.getByTestId("reply-review").textContent).toBe(
      "Review status: AI-generated · not reviewed",
    );
  });

  it("names who accepted the reply and when, in place of the label", () => {
    render(
      wrap(
        <ReplyReviewStatus
          review={{
            status: "accepted",
            acceptedBy: { id: "u1", name: "Dev Approver" },
            acceptedAt: "2026-11-18T10:30:00+00:00",
          }}
        />,
      ),
    );
    const label = screen.getByTestId("reply-review");
    expect(label.textContent).toContain("Accepted by Dev Approver · ");
    expect(label.textContent).toContain("2026");
    expect(label.textContent).not.toContain("not reviewed");
  });

  it("says when a review is in progress or was rejected", () => {
    render(wrap(<ReplyReviewStatus review={{ status: "in_review" }} />));
    expect(screen.getByTestId("reply-review").textContent).toBe(
      "Review status: AI-generated · review in progress",
    );
    cleanup();
    render(wrap(<ReplyReviewStatus review={{ status: "rejected" }} />));
    expect(screen.getByTestId("reply-review").textContent).toBe(
      "Review status: AI-generated · rejected in review",
    );
  });

  it("offers Accept only when the API says this person may accept the reply", () => {
    const accepted = vi.fn();
    render(wrap(<AcceptReply messageId="m1" onAccepted={accepted} review={null} />));
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
    cleanup();
    render(
      wrap(
        <AcceptReply
          messageId="m1"
          onAccepted={accepted}
          review={{ status: "unreviewed", canAccept: false }}
        />,
      ),
    );
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
    cleanup();
    render(
      wrap(
        <AcceptReply
          messageId="local-1"
          onAccepted={accepted}
          review={{ status: "unreviewed", canAccept: true }}
        />,
      ),
    );
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
  });

  it("waits while another reply is being written", () => {
    render(
      wrap(
        <AcceptReply
          disabled
          messageId="m1"
          onAccepted={() => undefined}
          review={{ status: "unreviewed", canAccept: true }}
        />,
      ),
    );
    expect((screen.getByRole("button", { name: "Accept" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("confirms it is the person, records the acceptance and hands back the new state", async () => {
    const review = {
      status: "accepted",
      acceptedBy: { id: "u1", name: "Dev Approver" },
      acceptedAt: "2026-11-18T10:30:00+00:00",
      canAccept: false,
    };
    const fetched = vi.fn(async (path: string) =>
      path.endsWith(":accept") ? answer(review) : answer({ steppedUp: true }),
    );
    vi.stubGlobal("fetch", fetched);
    const accepted = vi.fn();
    render(
      wrap(
        <AcceptReply
          messageId="m1"
          onAccepted={accepted}
          review={{ status: "unreviewed", canAccept: true }}
        />,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(accepted).toHaveBeenCalledWith(review));
    expect(fetched.mock.calls.map((call) => call[0])).toEqual([
      "/api/v1/auth/step-up",
      "/api/v1/messages/m1:accept",
    ]);
  });

  it("shows why the reply could not be accepted and keeps the action", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string) =>
        path.endsWith(":accept")
          ? answer({ detail: "sod_violation" }, 422)
          : answer({ steppedUp: true }),
      ),
    );
    const accepted = vi.fn();
    render(
      wrap(
        <AcceptReply
          messageId="m1"
          onAccepted={accepted}
          review={{ status: "unreviewed", canAccept: true }}
        />,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("sod_violation"));
    expect(accepted).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy();
  });
});
