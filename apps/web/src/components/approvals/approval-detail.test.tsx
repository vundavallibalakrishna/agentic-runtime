import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApprovalDetail } from "@/components/approvals/approval-detail";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/approvals/approval",
  useParams: () => ({}),
  useRouter: () => ({ push: () => undefined }),
}));
const row = {
  id: "approval",
  qualifiedName: "workspace.write",
  status: "pending",
  argsHash: "hash",
  canDecide: true,
};
function view(id = "approval") {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <ApprovalDetail approvalId={id} />
    </NextIntlClientProvider>
  );
}
function answer(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
beforeEach(() => {
  window.localStorage.clear();
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ permissions: ["approvals:decide"] }),
    ),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/approvals/:id", ({ params }) =>
      HttpResponse.json({ ...row, id: params.id }),
    ),
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("approval detail", () => {
  it.each([false, undefined])(
    "uses authoritative eligibility %s without offering decisions",
    async (canDecide) => {
      server.use(
        http.get("*/api/v1/approvals/:id", () => HttpResponse.json({ ...row, canDecide })),
      );
      render(view());
      await screen.findByText("workspace.write");
      expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
      expect(
        screen.getByText(
          messages.approvals[canDecide === false ? "cannotDecide" : "eligibilityUnconfirmed"],
        ),
      ).toBeTruthy();
    },
  );
  it("holds decisions when the exact arguments hash is missing", async () => {
    server.use(
      http.get("*/api/v1/approvals/:id", () => HttpResponse.json({ ...row, argsHash: "" })),
    );
    render(view());
    expect((await screen.findByRole("button", { name: "Approve" })).hasAttribute("disabled")).toBe(
      true,
    );
    expect(screen.getByText(messages.approvals.hashUnconfirmed)).toBeTruthy();
  });
  it("shows a missing request without an editable stale form", async () => {
    server.use(http.get("*/api/v1/approvals/:id", () => new HttpResponse(null, { status: 404 })));
    render(view());
    expect(await screen.findByText(messages.approvals.missingHelp)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });
  it("does not decide after an unconfirmed session and permits an explicit confirmation retry", async () => {
    let confirmations = 0;
    let decisions = 0;
    server.use(
      http.get("*/api/v1/approvals/:id", () => HttpResponse.json({ ...row, stepUpRequired: true })),
      http.post("*/api/v1/auth/step-up", () => {
        confirmations++;
        return HttpResponse.json({ steppedUp: "false" });
      }),
      http.post("*/api/v1/approvals/approval:decide", () => {
        decisions++;
        return HttpResponse.json(row);
      }),
    );
    render(view());
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await screen.findByText(messages.detail.stepUpUnconfirmed);
    expect(decisions).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    await waitFor(() => expect(confirmations).toBe(2));
    expect(decisions).toBe(0);
  });
  it("guards same-frame actions, records a quorum vote and never offers a second vote", async () => {
    const receipt = deferred<Response>();
    const nativeFetch = globalThis.fetch;
    let decisions = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, options?: RequestInit) => {
        if (String(input).endsWith(":decide")) {
          decisions++;
          return receipt.promise;
        }
        return nativeFetch(input, options);
      }),
    );
    render(view());
    const approve = await screen.findByRole("button", { name: "Approve" });
    act(() => {
      fireEvent.click(approve);
      fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    });
    expect(decisions).toBe(1);
    await act(async () =>
      receipt.resolve(answer({ ...row, approvalsReceived: 1, requiredApprovals: 2 })),
    );
    await screen.findByText(messages.approvals.decisionWaiting);
    await waitFor(() => expect(screen.queryByRole("button", { name: "Approve" })).toBeNull());
    fireEvent.click(screen.getByRole("button", { name: "Refresh approval" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Refresh approval" }).hasAttribute("disabled"),
      ).toBe(false),
    );
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(decisions).toBe(1);
  });
  it.each([{ ...row, id: "other" }, { ...row, argsHash: "changed" }, {}])(
    "holds an incomplete or mismatched receipt and preserves the comment",
    async (receipt) => {
      let decisions = 0;
      server.use(
        http.post("*/api/v1/approvals/approval:decide", () => {
          decisions++;
          return HttpResponse.json(receipt);
        }),
      );
      render(view());
      fireEvent.change(await screen.findByRole("textbox", { name: messages.approvals.comment }), {
        target: { value: "Review note" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Approve" }));
      await screen.findByText(messages.approvals.decisionUnconfirmed);
      expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("Review note");
      expect(screen.getByRole("button", { name: "Approve" }).hasAttribute("disabled")).toBe(true);
      fireEvent.click(screen.getByRole("button", { name: "Refresh approval" }));
      await waitFor(() =>
        expect(screen.getByRole("button", { name: "Approve" }).hasAttribute("disabled")).toBe(
          false,
        ),
      );
      expect(decisions).toBe(1);
    },
  );
  it("retains an acknowledged decision when its metadata refresh fails", async () => {
    let saved = false;
    server.use(
      http.get("*/api/v1/approvals/:id", () =>
        saved
          ? HttpResponse.json({ detail: "metadata unavailable" }, { status: 503 })
          : HttpResponse.json(row),
      ),
      http.post("*/api/v1/approvals/approval:decide", () => {
        saved = true;
        return HttpResponse.json({ ...row, status: "approved", canDecide: false });
      }),
    );
    render(view());
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await screen.findByText(messages.approvals.acceptedRecovery);
    expect(screen.getByText(messages.approvals.approvedRecorded)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });
  it("aborts confirmation on a different approval without posting a decision", async () => {
    const confirmation = deferred<Response>();
    const nativeFetch = globalThis.fetch;
    let signal: AbortSignal | null | undefined;
    let decisions = 0;
    server.use(
      http.get("*/api/v1/approvals/:id", ({ params }) =>
        HttpResponse.json({ ...row, id: params.id, stepUpRequired: true }),
      ),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, options?: RequestInit) => {
        if (String(input).endsWith("/step-up")) {
          signal = options?.signal;
          return confirmation.promise;
        }
        if (String(input).endsWith(":decide")) {
          decisions++;
          return Promise.resolve(answer(row));
        }
        return nativeFetch(input, options);
      }),
    );
    const rendered = render(view());
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await waitFor(() => expect(signal).toBeTruthy());
    rendered.rerender(view("next"));
    expect(signal?.aborted).toBe(true);
    await act(async () => confirmation.resolve(answer({ steppedUp: "true" })));
    await screen.findByRole("button", { name: "Approve" });
    expect(decisions).toBe(0);
  });
  it("bounds 100,000 reasons and searches all loaded reasons before paging", async () => {
    server.use(
      http.get("*/api/v1/approvals/:id", () =>
        HttpResponse.json({
          ...row,
          policyReasons: Array.from({ length: 100_000 }, (_, n) => `Reason ${n}`),
        }),
      ),
    );
    render(view());
    await screen.findByText("Reason 0");
    expect(screen.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Reason 99999" } });
    expect(screen.getByText("Reason 99999")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
  });
});
