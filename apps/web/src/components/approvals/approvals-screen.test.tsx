import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApprovalsScreen } from "@/components/approvals/approvals-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/approvals",
  useParams: () => ({}),
  useRouter: () => ({ push: () => undefined }),
}));
function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ApprovalsScreen />
    </NextIntlClientProvider>,
  );
}
const requests = Array.from({ length: 30 }, (_, i) => ({
  id: `approval-${i.toString().padStart(8, "0")}`,
  qualifiedName: "workspace.write",
  argsHash: "hash",
  preview: { title: `Request ${i}` },
  riskClass: "W2",
  status: i === 28 ? "approved" : "pending",
}));
beforeEach(() => {
  window.localStorage.clear();
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({
        permissions: ["approvals:decide", "approvals:read_all", "approvals:grant_standing"],
      }),
    ),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/approvals", () => HttpResponse.json({ items: requests })),
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("approval queues", () => {
  it("keeps page selections visible and clears them when filtering; uses the contract risk query", async () => {
    const risks: string[] = [];
    server.use(
      http.get("*/api/v1/approvals", ({ request }) => {
        const risk = new URL(request.url).searchParams.get("risk_class") ?? "";
        risks.push(risk);
        return HttpResponse.json({ items: requests });
      }),
    );
    show();
    await screen.findByText("Request 0");
    expect(screen.queryByText("Request 29")).toBeNull();
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Select workspace.write, reference 00000000" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Select workspace.write, reference 00000029" }),
    );
    expect(screen.getByText("2 selected across pages")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.approvals.search }), {
      target: { value: "Request 0" },
    });
    expect(screen.getByText("Request 0")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Reject selected" })).toBeNull();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.approvals.search }), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "approved" } });
    expect(screen.getByText("Request 28")).toBeTruthy();
    expect(
      screen
        .getByRole("checkbox", { name: "Select workspace.write, reference 00000028" })
        .hasAttribute("disabled"),
    ).toBe(true);
    fireEvent.change(screen.getByLabelText("Risk"), { target: { value: "W3" } });
    await waitFor(() => expect(risks).toContain("W3"));
  });

  it("does not request privileged standing approvals or enable All for a basic decider", async () => {
    let standingReads = 0;
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["approvals:decide"] }),
      ),
      http.get("*/api/v1/standing-approvals", () => {
        standingReads += 1;
        return HttpResponse.json({ items: [] });
      }),
    );
    show();
    await screen.findByText("Request 0");
    expect(screen.getByRole("button", { name: "All" }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    await screen.findByText("Request 0");
    expect(standingReads).toBe(0);
    expect(screen.queryByRole("heading", { name: "Standing approvals" })).toBeNull();
  });

  it("keeps the main queue available when standing approval loading fails and retries it", async () => {
    let attempts = 0;
    server.use(
      http.get("*/api/v1/standing-approvals", () =>
        ++attempts === 1
          ? HttpResponse.json({ detail: "Standing approvals unavailable" }, { status: 503 })
          : HttpResponse.json({
              items: Array.from({ length: 30 }, (_, i) => ({
                id: `grant-${i}`,
                tool: { name: `Stored tool ${i}` },
              })),
            }),
      ),
    );
    show();
    await screen.findByText("Request 0");
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    await screen.findByRole("alert");
    expect(screen.getByText("Request 0")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("Stored tool 0");
    expect(screen.queryByText("Stored tool 29")).toBeNull();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.approvals.searchStanding }), {
      target: { value: "grant-29" },
    });
    expect(screen.getByText("Stored tool 29")).toBeTruthy();
  });
});

function setupQueue(count = 3) {
  const state = {
    rows: requests.slice(0, count).map((row) => ({ ...row })),
    posted: [] as { id: string; body: Record<string, unknown> }[],
    detailReads: [] as string[],
  };
  server.use(
    http.get("*/api/v1/approvals", () => HttpResponse.json({ items: state.rows })),
    http.get("*/api/v1/approvals/:id", ({ params }) => {
      state.detailReads.push(String(params.id));
      return HttpResponse.json({
        ...state.rows.find((row) => row.id === params.id),
        canDecide: true,
      });
    }),
    http.post("*/api/v1/approvals/:operation", async ({ params, request }) => {
      const id = String(params.operation).replace(":decide", "");
      const body = (await request.json()) as Record<string, unknown>;
      state.posted.push({ id, body });
      const row = state.rows.find((row) => row.id === id);
      const result = { ...row, status: body.decision === "reject" ? "rejected" : "approved" };
      state.rows = state.rows.map((row) => (row.id === id ? { ...row, ...result } : row));
      return HttpResponse.json(result);
    }),
  );
  return state;
}
function select(id: string) {
  fireEvent.click(
    screen.getByRole("checkbox", { name: `Select workspace.write, reference ${id.slice(-8)}` }),
  );
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
function answer(body: unknown) {
  return new Response(JSON.stringify(body), { headers: { "content-type": "application/json" } });
}

describe("approval queue action states", () => {
  it("prepares a decision from authoritative detail rather than assuming summary eligibility or step-up", async () => {
    const state = setupQueue(1);
    let confirmations = 0;
    server.use(
      http.get("*/api/v1/approvals/:id", () =>
        HttpResponse.json({ ...queueRow(state, 0), canDecide: true, stepUpRequired: true }),
      ),
      http.post("*/api/v1/auth/step-up", () => {
        confirmations++;
        return HttpResponse.json({ steppedUp: "true" });
      }),
    );
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await screen.findByText("Confirmed decisions in this attempt: 1 of 1.");
    expect(confirmations).toBe(1);
    expect(state.posted).toEqual([
      { id: queueRow(state, 0).id, body: { decision: "approve", argsHash: "hash", comment: "" } },
    ]);
  });
  it.each([{ canDecide: false }, { argsHash: "changed" }, { status: "approved" }])(
    "does not post when authoritative detail has changed %j",
    async (changes) => {
      const state = setupQueue(1);
      server.use(
        http.get("*/api/v1/approvals/:id", () =>
          HttpResponse.json({ ...queueRow(state, 0), canDecide: true, ...changes }),
        ),
      );
      show();
      fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
      await screen.findByText(messages.approvals.queueEligibility);
      expect(state.posted).toEqual([]);
    },
  );
  it("does not offer quick decisions in All or Requested views", async () => {
    setupQueue(1);
    show();
    await screen.findByRole("button", { name: "Approve" });
    fireEvent.click(screen.getByRole("button", { name: "All" }));
    await screen.findByText("Request 0");
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
  it("stops bulk rejection at an unconfirmed receipt, applies only confirmed results and preserves the remaining comment/selection", async () => {
    const state = setupQueue();
    server.use(
      http.post(`*/api/v1/approvals/${queueRow(state, 1).id}:decide`, () => HttpResponse.json({})),
    );
    show();
    await screen.findByText("Request 0");
    for (const row of state.rows) select(row.id);
    fireEvent.change(screen.getByRole("textbox", { name: /^Comment/ }), {
      target: { value: "Shared note" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reject selected" }));
    await screen.findByText(messages.approvals.decisionUnconfirmed);
    expect(screen.getByText("Confirmed decisions in this attempt: 1 of 3.")).toBeTruthy();
    expect(screen.getByText("2 selected across pages")).toBeTruthy();
    expect(state.detailReads).toEqual([queueRow(state, 0).id, queueRow(state, 1).id]);
    expect((screen.getByRole("textbox", { name: /^Comment/ }) as HTMLTextAreaElement).value).toBe(
      "Shared note",
    );
    expect(screen.getByRole("button", { name: "Reject selected" }).matches(":disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Refresh approval lists" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Reject selected" }).matches(":disabled")).toBe(
        false,
      ),
    );
    expect(state.posted).toHaveLength(1);
    expect(state.posted[0]?.body.comment).toBe("Shared note");
  });
  it("guards same-frame approve/reject requests during detail preparation", async () => {
    const state = setupQueue(1);
    const pending = deferred<Response>();
    const nativeFetch = globalThis.fetch;
    let preparations = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === `/api/v1/approvals/${queueRow(state, 0).id}`) {
          preparations++;
          return pending.promise;
        }
        return nativeFetch(input, init);
      }),
    );
    show();
    const approve = await screen.findByRole("button", { name: "Approve" });
    act(() => {
      fireEvent.click(approve);
      fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    });
    expect(preparations).toBe(1);
    await act(async () => pending.resolve(answer({ ...queueRow(state, 0), canDecide: true })));
    await screen.findByText("Confirmed decisions in this attempt: 1 of 1.");
    expect(state.posted).toHaveLength(1);
  });
  it("retains a quorum vote and removes its quick action even when the API list still returns it", async () => {
    const state = setupQueue(1);
    server.use(
      http.post(`*/api/v1/approvals/${queueRow(state, 0).id}:decide`, () =>
        HttpResponse.json({ ...queueRow(state, 0), status: "pending" }),
      ),
    );
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await screen.findByText(messages.approvals.decisionWaiting);
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.getByRole("checkbox").matches(":disabled")).toBe(true);
  });
  it("does not post a decision after unmounting while confirming the session", async () => {
    const state = setupQueue(1);
    const pending = deferred<Response>();
    const nativeFetch = globalThis.fetch;
    let signal: AbortSignal | null | undefined;
    server.use(
      http.get("*/api/v1/approvals/:id", () =>
        HttpResponse.json({ ...queueRow(state, 0), canDecide: true, stepUpRequired: true }),
      ),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input).endsWith("/step-up")) {
          signal = init?.signal;
          return pending.promise;
        }
        return nativeFetch(input, init);
      }),
    );
    const rendered = show();
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await waitFor(() => expect(signal).toBeTruthy());
    rendered.unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => pending.resolve(answer({ steppedUp: "true" })));
    expect(state.posted).toEqual([]);
  });
  it("rejects an unconfirmed session without sending a protected decision", async () => {
    const state = setupQueue(1);
    server.use(
      http.get("*/api/v1/approvals/:id", () =>
        HttpResponse.json({ ...queueRow(state, 0), canDecide: true, stepUpRequired: true }),
      ),
      http.post("*/api/v1/auth/step-up", () => HttpResponse.json({ steppedUp: "false" })),
    );
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await screen.findByText(messages.detail.stepUpUnconfirmed);
    expect(state.posted).toEqual([]);
  });
  it("preserves an accepted decision notice when the subsequent list read fails", async () => {
    const state = setupQueue(1);
    server.use(
      http.get("*/api/v1/approvals", () =>
        state.posted.length
          ? HttpResponse.json({ detail: "queue unavailable" }, { status: 503 })
          : HttpResponse.json({ items: state.rows }),
      ),
    );
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await screen.findByText("queue unavailable");
    expect(screen.getByText("Confirmed decisions in this attempt: 1 of 1.")).toBeTruthy();
    expect(screen.getByText("Request 0")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });
  it("bounds 100,000 requests and standing approvals independently", async () => {
    server.use(
      http.get("*/api/v1/approvals", () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, n) => ({
            ...requests[0],
            id: `request-${n}`,
            preview: { title: `Task ${n}` },
          })),
        }),
      ),
      http.get("*/api/v1/standing-approvals", () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, n) => ({
            id: `grant-${n}`,
            tool: { name: `Tool ${n}` },
          })),
        }),
      ),
    );
    show();
    await screen.findByText("Task 0");
    expect(screen.getAllByRole("checkbox")).toHaveLength(25);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "request-99999" } });
    expect(screen.getByText("Task 99999")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    await screen.findByText("Tool 0");
    expect(screen.getAllByRole("listitem")).toHaveLength(26);
    fireEvent.change(screen.getByRole("searchbox", { name: messages.approvals.searchStanding }), {
      target: { value: "grant-99999" },
    });
    expect(screen.getByText("Tool 99999")).toBeTruthy();
  });
  it.each([{}, { id: "grant", revokedAt: "invalid" }])(
    "holds standing revocation after an incomplete receipt %j",
    async (receipt) => {
      setupQueue(1);
      let writes = 0;
      server.use(
        http.get("*/api/v1/standing-approvals", () =>
          HttpResponse.json({ items: [{ id: "grant", tool: { name: "Standing tool" } }] }),
        ),
        http.post("*/api/v1/standing-approvals/grant:revoke", () => {
          writes++;
          return HttpResponse.json(receipt);
        }),
      );
      show();
      await screen.findByText("Request 0");
      fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
      fireEvent.click(await screen.findByRole("button", { name: "Revoke" }));
      await screen.findByText(messages.approvals.revokeUnconfirmed);
      expect(screen.getByRole("button", { name: "Revoke" }).matches(":disabled")).toBe(true);
      fireEvent.click(screen.getByRole("button", { name: "Refresh approval lists" }));
      await waitFor(() =>
        expect(screen.getByRole("button", { name: "Revoke" }).matches(":disabled")).toBe(false),
      );
      expect(writes).toBe(1);
    },
  );
});

function queueRow(state: ReturnType<typeof setupQueue>, index: number) {
  const row = state.rows[index];
  if (!row) throw new Error("A saved unit-test approval is required");
  return row;
}

describe("approval queue read and receipt recovery", () => {
  it("retains a valid standing revocation when its follow-up read fails", async () => {
    setupQueue(1);
    let revoked = false;
    let fail = true;
    let writes = 0;
    const grant = {
      id: "grant",
      tool: { name: "Standing tool" },
      expiresAt: "2027-01-01T10:00:00Z",
    };
    server.use(
      http.get("*/api/v1/standing-approvals", () =>
        revoked && fail
          ? HttpResponse.json({ detail: "grants unavailable" }, { status: 503 })
          : HttpResponse.json({
              items: [{ ...grant, revokedAt: revoked ? "2026-11-22T10:00:00Z" : null }],
            }),
      ),
      http.post("*/api/v1/standing-approvals/grant:revoke", () => {
        revoked = true;
        writes++;
        return HttpResponse.json({ ...grant, revokedAt: "2026-11-22T10:00:00Z" });
      }),
    );
    show();
    await screen.findByText("Request 0");
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    fireEvent.click(await screen.findByRole("button", { name: "Revoke" }));
    await screen.findByText("grants unavailable");
    expect(screen.getByText(messages.approvals.revokeRecorded)).toBeTruthy();
    expect(screen.getByText("Standing tool")).toBeTruthy();
    expect(screen.getByText(messages.approvals.revoked)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Revoke" })).toBeNull();
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Refresh approval lists" }));
    await waitFor(() => expect(screen.queryByText("grants unavailable")).toBeNull());
    expect(writes).toBe(1);
  });
  it("keeps a request with missing exact arguments viewable but unavailable for quick decisions", async () => {
    const state = setupQueue(1);
    server.use(
      http.get("*/api/v1/approvals", () =>
        HttpResponse.json({ items: [{ ...queueRow(state, 0), argsHash: null }] }),
      ),
    );
    show();
    await screen.findByText("Request 0");
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.getByRole("checkbox").matches(":disabled")).toBe(true);
    expect(screen.getByText(messages.approvals.queueHashUnavailable)).toBeTruthy();
    expect(screen.getByRole("link", { name: /workspace.write/ }).getAttribute("href")).toBe(
      `/approvals/${queueRow(state, 0).id}`,
    );
  });
  it("aborts an outdated queue read and never overwrites the newly selected scope", async () => {
    const pending = deferred<Response>();
    const nativeFetch = globalThis.fetch;
    let signal: AbortSignal | null | undefined;
    server.use(
      http.get("*/api/v1/approvals", () =>
        HttpResponse.json({ items: [{ ...requests[0], preview: { title: "Fresh request" } }] }),
      ),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input).includes("/approvals?scope=to_decide")) {
          signal = init?.signal;
          return pending.promise;
        }
        return nativeFetch(input, init);
      }),
    );
    show();
    await waitFor(() => expect(signal).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: messages.approvals.requested }));
    expect(signal?.aborted).toBe(true);
    await screen.findByText("Fresh request");
    await act(async () => pending.resolve(answer({ items: requests })));
    expect(screen.queryByText("Request 0")).toBeNull();
    expect(screen.getByText("Fresh request")).toBeTruthy();
  });
});
