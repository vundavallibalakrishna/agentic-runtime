import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    render(
      wrap(
        <AcceptReply
          onRefresh={async () => undefined}
          messageId="m1"
          onAccepted={accepted}
          review={null}
        />,
      ),
    );
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
    cleanup();
    render(
      wrap(
        <AcceptReply
          onRefresh={async () => undefined}
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
          onRefresh={async () => undefined}
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
          onRefresh={async () => undefined}
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
          onRefresh={async () => undefined}
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

  it("shows why the reply could not be accepted and requires a read-only refresh", async () => {
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
          onRefresh={async () => undefined}
          messageId="m1"
          onAccepted={accepted}
          review={{ status: "unreviewed", canAccept: true }}
        />,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("sod_violation"));
    expect(accepted).not.toHaveBeenCalled();
    expect((screen.getByRole("button", { name: "Accept" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
    expect(screen.getByRole("button", { name: "Refresh chat" })).toBeTruthy();
  });
  it("shows an explicit unavailable acceptance time instead of inventing one", () => {
    render(wrap(<ReplyReviewStatus review={{ status: "accepted", acceptedAt: "invalid" }} />));
    expect(screen.getByText(/Time unavailable/)).toBeTruthy();
  });
  it("does not post acceptance after an unconfirmed session", async () => {
    const fetched = vi.fn(async () => answer({ steppedUp: "false" }));
    vi.stubGlobal("fetch", fetched);
    render(
      wrap(
        <AcceptReply
          messageId="m1"
          review={{ canAccept: true }}
          onAccepted={vi.fn()}
          onRefresh={async () => undefined}
        />,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    await screen.findByText(messages.detail.stepUpUnconfirmed);
    expect(fetched).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Accept" }).hasAttribute("disabled")).toBe(false);
  });
  it("guards duplicate clicks while session confirmation is pending", async () => {
    let resolve!: (response: Response) => void;
    const deferred = new Promise<Response>((done) => {
      resolve = done;
    });
    const fetched = vi.fn(async (path: string) =>
      path.endsWith("step-up") ? deferred : answer({ status: "in_review", contentHash: "hash" }),
    );
    vi.stubGlobal("fetch", fetched);
    const accepted = vi.fn();
    render(
      wrap(
        <AcceptReply
          messageId="m1"
          review={{ canAccept: true, contentHash: "hash" }}
          onAccepted={accepted}
          onRefresh={async () => undefined}
        />,
      ),
    );
    const accept = screen.getByRole("button", { name: "Accept" });
    act(() => {
      fireEvent.click(accept);
      fireEvent.click(accept);
    });
    expect(fetched).toHaveBeenCalledTimes(1);
    await act(async () => resolve(answer({ steppedUp: "true" })));
    await waitFor(() =>
      expect(accepted).toHaveBeenCalledWith({ status: "in_review", contentHash: "hash" }),
    );
    expect(fetched).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("button", { name: "Review recorded" }).hasAttribute("disabled")).toBe(
      true,
    );
  });
  it.each(["disabled", "message", "hash"])(
    "cancels pending confirmation when the %s context changes",
    async (change) => {
      let resolve!: (response: Response) => void;
      let signal: AbortSignal | null | undefined;
      const deferred = new Promise<Response>((done) => {
        resolve = done;
      });
      const fetched = vi.fn((_path: string, options?: RequestInit) => {
        signal = options?.signal;
        return deferred;
      });
      vi.stubGlobal("fetch", fetched);
      const accepted = vi.fn();
      const rendered = render(
        wrap(
          <AcceptReply
            messageId="m1"
            review={{ canAccept: true, contentHash: "hash" }}
            onAccepted={accepted}
            onRefresh={async () => undefined}
          />,
        ),
      );
      fireEvent.click(screen.getByRole("button", { name: "Accept" }));
      rendered.rerender(
        wrap(
          <AcceptReply
            disabled={change === "disabled"}
            messageId={change === "message" ? "m2" : "m1"}
            review={{ canAccept: true, contentHash: change === "hash" ? "new" : "hash" }}
            onAccepted={accepted}
            onRefresh={async () => undefined}
          />,
        ),
      );
      expect(signal?.aborted).toBe(true);
      await act(async () => resolve(answer({ steppedUp: "true" })));
      expect(fetched).toHaveBeenCalledTimes(1);
      expect(accepted).not.toHaveBeenCalled();
    },
  );
  it.each([{}, { status: "accepted", contentHash: "wrong" }])(
    "requires read-only recovery after an incomplete or mismatched receipt",
    async (receipt) => {
      const fetched = vi.fn(async (path: string) =>
        answer(path.endsWith(":accept") ? receipt : { steppedUp: true }),
      );
      vi.stubGlobal("fetch", fetched);
      const accepted = vi.fn();
      const refresh = vi.fn(async () => undefined);
      render(
        wrap(
          <AcceptReply
            messageId="m1"
            review={{ canAccept: true, contentHash: "hash" }}
            onAccepted={accepted}
            onRefresh={refresh}
          />,
        ),
      );
      fireEvent.click(screen.getByRole("button", { name: "Accept" }));
      await screen.findByText(messages.chat.acceptUnconfirmed);
      expect(screen.getByRole("button", { name: "Accept" }).hasAttribute("disabled")).toBe(true);
      fireEvent.click(screen.getByRole("button", { name: "Refresh chat" }));
      await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
      expect(fetched).toHaveBeenCalledTimes(2);
      expect(accepted).not.toHaveBeenCalled();
    },
  );
  it("holds an attempted acceptance when chat becomes busy before its response", async () => {
    let resolve!: (response: Response) => void;
    const deferred = new Promise<Response>((done) => {
      resolve = done;
    });
    const fetched = vi.fn(async (path: string) =>
      path.endsWith(":accept") ? deferred : answer({ steppedUp: true }),
    );
    vi.stubGlobal("fetch", fetched);
    const accepted = vi.fn();
    const refresh = vi.fn(async () => undefined);
    const props = {
      messageId: "m1",
      review: { canAccept: true },
      onAccepted: accepted,
      onRefresh: refresh,
    };
    const rendered = render(wrap(<AcceptReply {...props} />));
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(fetched).toHaveBeenCalledTimes(2));
    rendered.rerender(wrap(<AcceptReply {...props} disabled />));
    await act(async () => resolve(answer({ status: "accepted" })));
    rendered.rerender(wrap(<AcceptReply {...props} />));
    expect(screen.getByRole("button", { name: "Accept" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Refresh chat" })).toBeTruthy();
    expect(accepted).not.toHaveBeenCalled();
  });
});
