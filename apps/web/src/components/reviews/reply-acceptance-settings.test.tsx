import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReplyAcceptanceSettings } from "@/components/reviews/reply-acceptance-settings";
import { clearCachedSession } from "@/lib/session";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const t = messages.reviews;
const permissions = ["tenant:read", "tenant:manage", "reviews:read"];
type Queue = { id: string; name: string; subjectType: string };
function registry(
  options: { saved?: string | null; queues?: Queue[]; permissions?: string[] } = {},
) {
  const state = {
    saved: options.saved ?? null,
    queues: options.queues ?? [{ id: "queue", name: "Reply review", subjectType: "message" }],
    permissions: options.permissions ?? permissions,
    reads: 0,
    queueReads: 0,
    writes: [] as unknown[],
    failRead: false,
  };
  const tenant = () => ({ settings: { approvals: { replyReviewQueueId: state.saved } } });
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: state.permissions })),
    http.get("*/api/v1/review-queues", () => {
      state.queueReads += 1;
      return HttpResponse.json({ items: state.queues });
    }),
    http.get("*/api/v1/tenant", () => {
      state.reads += 1;
      return state.failRead
        ? HttpResponse.json({ detail: "Settings unavailable" }, { status: 503 })
        : HttpResponse.json(tenant());
    }),
    http.patch("*/api/v1/tenant", async ({ request }) => {
      const body = (await request.json()) as {
        settings: { approvals: { replyReviewQueueId: string | null } };
      };
      state.writes.push(body);
      state.saved = body.settings.approvals.replyReviewQueueId;
      return HttpResponse.json(tenant());
    }),
  );
  return state;
}
function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ReplyAcceptanceSettings />
    </NextIntlClientProvider>,
  );
}
const picker = () => screen.getByRole("button", { name: /^Review queue for replies:/ });
const save = () => screen.getByRole("button", { name: t.replySave });
async function choose(name = "Reply review") {
  fireEvent.click(picker());
  fireEvent.click(within(await screen.findByRole("dialog")).getByText(name, { exact: true }));
}

afterEach(() => vi.restoreAllMocks());

describe("reply acceptance settings", () => {
  it("withholds editable Off after a failed load and retries the actual saved queue", async () => {
    const state = registry({ saved: "queue" });
    state.failRead = true;
    show();
    await screen.findByRole("alert");
    expect(screen.queryByRole("button", { name: t.replySave })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Review queue for replies:/ })).toBeNull();
    state.failRead = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("button", { name: "Review queue for replies: Reply review" });
    expect(save().matches(":disabled")).toBe(true);
  });

  it("shows unavailable saved identity and requires an available queue or explicit Off", async () => {
    registry({ saved: "missing-queue", queues: [] });
    show();
    await screen.findByRole("button", {
      name: "Review queue for replies: Configured queue unavailable (missing-queue)",
    });
    expect(screen.getByText(t.replyUnavailableHelp)).toBeTruthy();
    expect(save().matches(":disabled")).toBe(true);
    fireEvent.click(picker());
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: t.replyOff }));
    expect(save().matches(":disabled")).toBe(false);
    fireEvent.click(save());
    await screen.findByText(t.replySaved);
    expect(screen.queryByText(t.replyUnavailableHelp)).toBeNull();
  });

  it("saves only the selected queue and removes stale saved feedback when the draft changes", async () => {
    const state = registry();
    show();
    await screen.findByRole("button", { name: `Review queue for replies: ${t.replyOff}` });
    await choose();
    expect(screen.getByText(t.replyUnsaved)).toBeTruthy();
    fireEvent.click(save());
    await screen.findByText(t.replySaved);
    expect(state.writes).toEqual([{ settings: { approvals: { replyReviewQueueId: "queue" } } }]);
    expect(screen.queryByText(t.replyUnsaved)).toBeNull();
    expect(save().matches(":disabled")).toBe(true);
    fireEvent.click(picker());
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: t.replyOff }));
    expect(screen.queryByText(t.replySaved)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: t.replyUseSaved }));
    expect(save().matches(":disabled")).toBe(true);
    expect(state.writes).toHaveLength(1);
  });

  it.each([undefined, { settings: { approvals: { replyReviewQueueId: "other" } } }])(
    "holds an unconfirmed receipt and refreshes saved metadata without replay",
    async (receipt) => {
      const state = registry();
      let writes = 0;
      server.use(
        http.patch("*/api/v1/tenant", () => {
          writes += 1;
          return receipt === undefined
            ? new HttpResponse(null, { status: 204 })
            : HttpResponse.json(receipt);
        }),
      );
      show();
      await screen.findByRole("button", { name: /^Review queue for replies:/ });
      await choose();
      fireEvent.click(save());
      await screen.findByText(t.replyUnconfirmed);
      await waitFor(() => expect(screen.getByRole("alert")).toBe(document.activeElement));
      expect(screen.queryByText(t.replySaved)).toBeNull();
      expect(save().matches(":disabled")).toBe(true);
      state.failRead = true;
      fireEvent.click(screen.getByRole("button", { name: t.replyRefresh }));
      await screen.findByText("Settings unavailable");
      expect(save().matches(":disabled")).toBe(true);
      state.failRead = false;
      fireEvent.click(screen.getByRole("button", { name: t.replyRefresh }));
      await waitFor(() => expect(screen.queryByText(t.replyRecovery)).toBeNull());
      expect(picker().textContent).toBe("Reply review");
      expect(screen.getByText(t.replyUnsaved)).toBeTruthy();
      expect(writes).toBe(1);
      expect(save().matches(":disabled")).toBe(false);
    },
  );

  it("explains a verification refusal and preserves selection through read-only recovery", async () => {
    registry();
    let writes = 0;
    server.use(
      http.patch("*/api/v1/tenant", () => {
        writes += 1;
        return HttpResponse.json(
          { code: "csrf_failed", detail: "CSRF check failed" },
          { status: 403 },
        );
      }),
    );
    show();
    await screen.findByRole("button", { name: /^Review queue for replies:/ });
    await choose();
    fireEvent.click(save());
    await screen.findByText(messages.apiErrors.csrf);
    expect(screen.queryByText("CSRF check failed")).toBeNull();
    expect(picker().matches(":disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: t.replyRefresh }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(picker().textContent).toBe("Reply review");
    expect(writes).toBe(1);
  });

  it("bounds 100,000 loaded queues, searches all message queues and retains selection on Cancel", async () => {
    const queues = Array.from({ length: 100_000 }, (_, index) => ({
      id: `queue-${index}`,
      name: `Review ${index}`,
      subjectType: "message",
    }));
    queues.push({ id: "different", name: "Not a message queue", subjectType: "document" });
    registry({ queues });
    show();
    await screen.findByRole("button", { name: /^Review queue for replies:/ });
    fireEvent.click(picker());
    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.getAllByRole("listitem")).toHaveLength(25);
    expect(dialog.queryByText("Not a message queue")).toBeNull();
    fireEvent.change(dialog.getByRole("searchbox"), { target: { value: "Review 99999" } });
    fireEvent.click(dialog.getByText("Review 99999", { exact: true }));
    expect(picker().textContent).toBe("Review 99999");
    fireEvent.click(picker());
    fireEvent.change(within(screen.getByRole("dialog")).getByRole("searchbox"), {
      target: { value: "absent queue" },
    });
    expect(screen.getByText(messages.referencePicker.noMatches)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(picker().textContent).toBe("Review 99999");
    fireEvent.click(save());
    await screen.findByText(t.replySaved);
  });

  it.each([
    ["tenant:manage", "reviews:read"],
    ["tenant:read", "reviews:read"],
    ["tenant:read", "tenant:manage"],
  ])(
    "does not read private settings/queues without the required permissions %j",
    async (...held) => {
      const state = registry({ permissions: held });
      show();
      await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
      expect(state.reads).toBe(0);
      expect(state.queueReads).toBe(0);
      expect(screen.queryByRole("button", { name: t.replySave })).toBeNull();
    },
  );

  it("removes stale controls when refresh returns an explicit access failure", async () => {
    registry({ saved: "queue" });
    show();
    await screen.findByRole("button", { name: /^Review queue for replies:/ });
    server.use(
      http.get("*/api/v1/tenant", () =>
        HttpResponse.json({ detail: "Access removed" }, { status: 403 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: t.replyRefresh }));
    await screen.findByText("Access removed");
    expect(screen.queryByRole("button", { name: /^Review queue for replies:/ })).toBeNull();
    expect(screen.queryByRole("button", { name: t.replySave })).toBeNull();
  });

  it("rechecks current permissions before refresh reads", async () => {
    const state = registry();
    show();
    await screen.findByRole("button", { name: /^Review queue for replies:/ });
    clearCachedSession();
    state.permissions = [];
    fireEvent.click(screen.getByRole("button", { name: t.replyRefresh }));
    await waitFor(() => expect(screen.queryByRole("button", { name: t.replyRefresh })).toBeNull());
    expect(state.reads).toBe(1);
    expect(state.queueReads).toBe(1);
  });

  it.each([{ settings: {} }, { settings: { approvals: {} } }])(
    "rejects incomplete saved metadata rather than inventing Off",
    async (body) => {
      registry();
      server.use(http.get("*/api/v1/tenant", () => HttpResponse.json(body)));
      show();
      await screen.findByText(t.replyMetadataError);
      expect(screen.queryByRole("button", { name: t.replySave })).toBeNull();
    },
  );

  it("coordinates same-frame submits and aborts a pending save on unmount", async () => {
    registry();
    const original = globalThis.fetch;
    let writes = 0;
    let signal: AbortSignal | null = null;
    let finish: (response: Response) => void = () => undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (init?.method === "PATCH") {
        writes += 1;
        signal = init.signal as AbortSignal;
        return new Promise<Response>((resolve) => {
          finish = resolve;
        });
      }
      return original(input, init);
    });
    const view = show();
    await screen.findByRole("button", { name: /^Review queue for replies:/ });
    await choose();
    const form = save().closest("form") as HTMLFormElement;
    act(() => {
      fireEvent.submit(form);
      fireEvent.submit(form);
    });
    expect(writes).toBe(1);
    expect(picker().matches(":disabled")).toBe(true);
    view.unmount();
    expect((signal as AbortSignal | null)?.aborted).toBe(true);
    await act(async () => {
      finish(
        new Response(JSON.stringify({ settings: { approvals: { replyReviewQueueId: "queue" } } })),
      );
    });
    expect(screen.queryByText(t.replySaved)).toBeNull();
  });
});
