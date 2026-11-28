import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";

import { CollectionScreen } from "@/components/knowledge/collection-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => children,
}));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("submits the chosen content method instead of a previously selected library document", async () => {
  let saved: unknown;
  server.use(
    http.get("*/api/v1/knowledge/collections/collection-1", () =>
      HttpResponse.json({ name: "Team knowledge" }),
    ),
  );
  for (const path of [
    "knowledge/collections/collection-1/documents",
    "knowledge/collections/collection-1/sources",
    "knowledge/collections/collection-1/jobs",
    "service-connections",
  ]) {
    server.use(http.get(`*/api/v1/${path}`, () => HttpResponse.json({ items: [] })));
  }
  server.use(
    http.get("*/api/v1/library-documents", () =>
      HttpResponse.json({ items: [{ id: "doc-1", title: "Guide" }] }),
    ),
  );
  server.use(
    http.post("*/api/v1/knowledge/collections/collection-1/members", async ({ request }) => {
      saved = await request.json();
      return HttpResponse.json({});
    }),
  );
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <CollectionScreen collectionId="collection-1" />
    </NextIntlClientProvider>,
  );
  const method = await screen.findByLabelText("Where is the content?");
  fireEvent.change(method, { target: { value: "library" } });
  fireEvent.click(screen.getByRole("button", { name: /^From the library:/ }));
  fireEvent.click(await within(screen.getByRole("dialog")).findByText("Guide", { exact: true }));
  fireEvent.change(method, { target: { value: "url" } });
  const url = screen.getByLabelText("URL") as HTMLInputElement;
  fireEvent.change(url, { target: { value: "https://docs.example/guide" } });
  expect(screen.queryByRole("button", { name: /^From the library:/ })).toBeNull();
  if (!url.form) throw new Error("URL needs a form");
  fireEvent.submit(url.form);
  await waitFor(() => expect(saved).toEqual({ kind: "url", url: "https://docs.example/guide" }));
});

function collectionFixture(collectionId = "collection", canManage = true) {
  server.use(
    http.get(`*/api/v1/knowledge/collections/${collectionId}`, () =>
      HttpResponse.json({ name: `Collection ${collectionId}`, canManage }),
    ),
  );
  for (const part of ["documents", "sources", "jobs"]) {
    server.use(
      http.get(`*/api/v1/knowledge/collections/${collectionId}/${part}`, () =>
        HttpResponse.json({ items: [] }),
      ),
    );
  }
}

function collectionView(collectionId = "collection") {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <CollectionScreen collectionId={collectionId} />
    </NextIntlClientProvider>
  );
}

it.each(["documents", "sources", "jobs"] as const)(
  "bounds 100,000 %s with full-loaded-list search/status filtering before paging",
  async (part) => {
    collectionFixture("collection", false);
    server.use(
      http.get(`*/api/v1/knowledge/collections/collection/${part}`, () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, index) => ({
            id: `record-${index}`,
            title: `Document ${index}`,
            name: `Source ${index}`,
            kind: `Job ${index}`,
            status: index === 99_999 ? "failed" : "ready",
          })),
        }),
      ),
    );
    render(collectionView());
    await screen.findByRole("heading", { name: "Collection collection" });
    const label = messages.knowledge[part];
    if (part !== "documents")
      fireEvent.mouseDown(screen.getByRole("tab", { name: label }), { button: 0, ctrlKey: false });
    const region = within(await screen.findByRole("region", { name: label }));
    expect(region.getAllByRole("listitem")).toHaveLength(25);
    expect(region.getByText("1–25 of 100,000")).toBeTruthy();
    fireEvent.click(region.getByRole("button", { name: "Next" }));
    expect(region.getByText("26–50 of 100,000")).toBeTruthy();
    fireEvent.change(region.getByRole("searchbox"), { target: { value: "record-99999" } });
    expect(region.getAllByRole("listitem")).toHaveLength(1);
    expect(region.getByText("failed", { selector: "span" })).toBeTruthy();
    fireEvent.change(region.getByRole("combobox", { name: "Status" }), {
      target: { value: "ready" },
    });
    expect(region.getByText(messages.knowledge.noRecordMatches)).toBeTruthy();
    expect(region.queryAllByRole("listitem")).toHaveLength(0);
    fireEvent.click(region.getByRole("button", { name: "Clear filters" }));
    expect(region.getAllByRole("listitem")).toHaveLength(25);
    expect(region.getByText("1–25 of 100,000")).toBeTruthy();
  },
);

it.each(["library", "connection"] as const)(
  "loads a bounded %s picker only when opened and submits the selected record's exact id",
  async (method) => {
    collectionFixture();
    let reads = 0;
    const bodies: unknown[] = [];
    const label = method === "library" ? "From the library" : "Connection";
    const endpoint = method === "library" ? "library-documents" : "service-connections";
    server.use(
      http.get(`*/api/v1/${endpoint}`, () => {
        reads += 1;
        return HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, index) => ({
            id: `choice-${index}`,
            title: `Saved ${index}`,
            name: `Saved ${index}`,
          })),
        });
      }),
      http.post("*/api/v1/knowledge/collections/collection/members", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({});
      }),
    );
    render(collectionView());
    fireEvent.change(await screen.findByLabelText("Where is the content?"), {
      target: { value: method },
    });
    expect(reads).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: new RegExp(`^${label}:`) }));
    const picker = within(screen.getByRole("dialog", { name: label }));
    await picker.findByText("Saved 0", { exact: true });
    expect(picker.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.change(picker.getByRole("searchbox"), { target: { value: "choice-99999" } });
    fireEvent.click(picker.getByText("Saved 99999", { exact: true }));
    const submit = screen.getByRole("button", {
      name: method === "library" ? "Add document" : "Add connection",
    });
    const form = submit.closest("form");
    if (!form) throw new Error("Content selector needs its existing form");
    act(() => {
      fireEvent.submit(form);
      fireEvent.submit(form);
    });
    await waitFor(() =>
      expect(bodies).toEqual([
        method === "library"
          ? { kind: method, libraryDocumentId: "choice-99999" }
          : { kind: method, connectionId: "choice-99999", url: "" },
      ]),
    );
    expect(reads).toBe(1);
  },
);

it("shows a selector read failure as an error with retry, rather than an empty catalogue", async () => {
  collectionFixture();
  let reads = 0;
  server.use(
    http.get("*/api/v1/library-documents", () =>
      ++reads === 1
        ? HttpResponse.json({ detail: "Library unavailable" }, { status: 503 })
        : HttpResponse.json({ items: [{ id: "guide", title: "Saved guide" }] }),
    ),
  );
  render(collectionView());
  fireEvent.change(await screen.findByLabelText("Where is the content?"), {
    target: { value: "library" },
  });
  fireEvent.click(screen.getByRole("button", { name: /^From the library:/ }));
  const picker = within(screen.getByRole("dialog"));
  await picker.findByRole("alert");
  expect(picker.queryByText(messages.referencePicker.empty)).toBeNull();
  fireEvent.click(picker.getByRole("button", { name: "Try again" }));
  await picker.findByText("Saved guide", { exact: true });
  fireEvent.click(picker.getByRole("button", { name: "Cancel" }));
  expect(screen.getByRole("button", { name: "Add document" }).hasAttribute("disabled")).toBe(true);
  expect(reads).toBe(2);
});

it("keeps read-only collections free of management controls and unnecessary selector requests", async () => {
  collectionFixture("collection", false);
  const unexpected = vi.fn(() => HttpResponse.json({ items: [] }));
  server.use(
    http.get("*/api/v1/library-documents", unexpected),
    http.get("*/api/v1/service-connections", unexpected),
  );
  render(collectionView());
  await screen.findByText(messages.knowledge.emptyDocuments);
  expect(screen.queryByLabelText("Where is the content?")).toBeNull();
  expect(screen.queryByRole("link", { name: "Connect source" })).toBeNull();
  expect(unexpected).not.toHaveBeenCalled();
});

it("bounds returned search passages and labels them with the submitted question", async () => {
  collectionFixture("collection", false);
  let searches = 0;
  server.use(
    http.post("*/api/v1/knowledge/search", () => {
      searches += 1;
      return HttpResponse.json({
        answerable: true,
        hits: Array.from({ length: 100_000 }, (_, index) => ({
          chunkId: `chunk-${index}`,
          title: `Passage ${index}`,
          snippet: `Snippet ${index}`,
        })),
      });
    }),
  );
  render(collectionView());
  await screen.findByRole("heading", { name: "Collection collection" });
  fireEvent.mouseDown(screen.getByRole("tab", { name: "Search" }), {
    button: 0,
    ctrlKey: false,
  });
  const question = screen.getByLabelText("Question");
  fireEvent.change(question, { target: { value: "Submitted question" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask the library" }));
  await screen.findByText("Results for: Submitted question");
  const hits = within(screen.getByRole("list", { name: "Passages found" }));
  expect(hits.getAllByRole("listitem")).toHaveLength(25);
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(hits.getByText("Passage 25", { exact: true })).toBeTruthy();
  fireEvent.change(question, { target: { value: "Unsubmitted draft" } });
  expect(screen.getByText("Results for: Submitted question")).toBeTruthy();
  expect(hits.getByText("Passage 25", { exact: true })).toBeTruthy();
  expect(searches).toBe(1);
});

it("requires a ready file id before indexing and retains the chosen file through read-only recovery", async () => {
  collectionFixture();
  let uploads = 0;
  let indexing = 0;
  server.use(
    http.post("*/api/v1/files:upload", () => {
      uploads += 1;
      return HttpResponse.json({ status: "ready" });
    }),
    http.post("*/api/v1/knowledge/collections/collection/documents", () => {
      indexing += 1;
      return HttpResponse.json({});
    }),
  );
  render(collectionView());
  const input = await screen.findByLabelText("Add a file");
  const file = new File(["Actual unit input"], "kept.txt", { type: "text/plain" });
  fireEvent.change(input, { target: { files: [file] } });
  const form = input.closest("form");
  if (!form) throw new Error("Upload needs its existing form");
  act(() => {
    fireEvent.submit(form);
    fireEvent.submit(form);
  });
  await screen.findByText(messages.knowledge.uploadUnconfirmed);
  expect(uploads).toBe(1);
  expect(indexing).toBe(0);
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await waitFor(() => expect(screen.queryByText(messages.knowledge.uploadUnconfirmed)).toBeNull());
  expect(screen.getByLabelText("Add a file")).toBe(input);
  expect((input as HTMLInputElement).files?.[0]).toBe(file);
  expect(uploads).toBe(1);
  expect(indexing).toBe(0);
});

it("cancels an old collection upload and never indexes its late receipt into another collection", async () => {
  collectionFixture();
  collectionFixture("other");
  let release = (_response: Response) => {};
  const waiting = new Promise<Response>((resolve) => {
    release = resolve;
  });
  let transportSignal: AbortSignal | null | undefined;
  let started = false;
  const originalFetch = globalThis.fetch;
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    if (String(input) === "/api/v1/files:upload") {
      started = true;
      transportSignal = init?.signal;
      return waiting;
    }
    return originalFetch(input, init);
  });
  let indexing = 0;
  server.use(
    http.post("*/api/v1/knowledge/collections/:id/documents", () => {
      indexing += 1;
      return HttpResponse.json({});
    }),
  );
  const rendered = render(collectionView());
  const input = await screen.findByLabelText("Add a file");
  fireEvent.change(input, {
    target: { files: [new File(["Unit file"], "old.txt", { type: "text/plain" })] },
  });
  const form = input.closest("form");
  if (!form) throw new Error("Upload needs its existing form");
  fireEvent.submit(form);
  await waitFor(() => expect(started).toBe(true));
  rendered.rerender(collectionView("other"));
  await screen.findByRole("heading", { name: "Collection other" });
  expect(transportSignal?.aborted).toBe(true);
  await act(async () => {
    release(HttpResponse.json({ id: "old-file", status: "ready" }));
    await waiting;
  });
  expect(indexing).toBe(0);
  expect(screen.queryByText(messages.detail.uploadSuccess)).toBeNull();
  expect((screen.getByLabelText("Add a file") as HTMLInputElement).files?.length).toBe(0);
  expect(screen.getByRole("heading", { name: "Collection other" })).toBeTruthy();
});
