import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ComputersScreen } from "@/components/computer/computers-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => children,
}));
const t = messages.computers;
const template = {
  id: "tpl-1",
  name: "Workstation",
  slug: "workstation",
  cpuMillis: 3500,
  memoryMb: 6000,
  allowPackages: false,
};
const instance = {
  id: "computer-1",
  status: "ready",
  scopeKey: "same-conversation",
  templateSlug: "workstation",
};
function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ComputersScreen />
    </NextIntlClientProvider>,
  );
}
async function ready() {
  await screen.findByText(`Instance ID: ${instance.id}`);
  await waitFor(() =>
    expect(screen.getByRole("button", { name: t.refresh }).hasAttribute("disabled")).toBe(false),
  );
}
function draft() {
  fireEvent.change(screen.getByLabelText(t.name), { target: { value: "A new workstation" } });
  fireEvent.change(screen.getByLabelText(t.slug), { target: { value: "NEW-Workstation" } });
}
function refresh() {
  fireEvent.click(screen.getAllByRole("button", { name: t.refresh })[0] as HTMLElement);
}
beforeEach(() => {
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ permissions: ["sandboxes:manage", "chat:use"] }),
    ),
    http.get("*/api/v1/sandbox-templates", () => HttpResponse.json({ items: [template] })),
    http.get("*/api/v1/sandboxes", () => HttpResponse.json({ items: [instance] })),
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
});
describe("computer template setup", () => {
  it("takes the stacked-layout create shortcut directly to the template name", async () => {
    show();
    await ready();
    fireEvent.click(screen.getByRole("button", { name: t.createTitle }));
    expect(document.activeElement).toBe(screen.getByLabelText(t.name));
  });
  it("uses service defaults when optional overrides are unset and checks the saved row", async () => {
    let body: unknown;
    const saved = {
      ...template,
      id: "saved",
      name: "A new workstation",
      slug: "new-workstation",
      cpuMillis: 8000,
      allowPackages: true,
    };
    server.use(
      http.post("*/api/v1/sandbox-templates", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(saved);
      }),
    );
    show();
    await ready();
    draft();
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    expect((screen.getByLabelText(t.cpu) as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText(t.memory) as HTMLInputElement).value).toBe("");
    expect((screen.getByRole("combobox", { name: t.packages }) as HTMLSelectElement).value).toBe(
      "default",
    );
    server.use(
      http.get("*/api/v1/sandbox-templates", () => HttpResponse.json({ items: [template, saved] })),
    );
    fireEvent.click(screen.getByRole("button", { name: t.save }));
    await screen.findByText(t.saved);
    expect(body).toEqual({ name: saved.name, slug: saved.slug });
    expect((screen.getByLabelText(t.name) as HTMLInputElement).value).toBe("");
    expect(screen.getByText(saved.name)).toBeTruthy();
  });
  it("preserves advanced overrides through Simple and submits explicit package blocking", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/v1/sandbox-templates", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...template, ...(body as object), id: "saved" });
      }),
    );
    show();
    await ready();
    draft();
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    fireEvent.change(screen.getByLabelText(t.cpu), { target: { value: "4500" } });
    fireEvent.change(screen.getByLabelText(t.memory), { target: { value: "8000" } });
    fireEvent.change(screen.getByRole("combobox", { name: t.packages }), {
      target: { value: "block" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Simple" }));
    expect(screen.getByText(t.advancedIncluded)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: t.save }));
    await screen.findByText(t.savedNotListed);
    expect(body).toEqual({
      name: "A new workstation",
      slug: "new-workstation",
      cpuMillis: 4500,
      memoryMb: 8000,
      allowPackages: false,
    });
  });
  it("validates positive integer overrides even for direct form submission and resets only overrides", async () => {
    const write = vi.fn();
    server.use(http.post("*/api/v1/sandbox-templates", write));
    show();
    await ready();
    draft();
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    const cpu = screen.getByLabelText(t.cpu);
    fireEvent.change(cpu, { target: { value: "1.5" } });
    const form = screen.getByRole("button", { name: t.save }).closest("form");
    if (!form) throw new Error("Missing template form");
    fireEvent.submit(form);
    expect(screen.getByText(t.invalidForm)).toBeTruthy();
    expect(cpu.getAttribute("aria-invalid")).toBe("true");
    expect(write).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: t.resourceReset }));
    expect((cpu as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText(t.name) as HTMLInputElement).value).toBe("A new workstation");
  });
  it.each(["csrf", "receipt"])(
    "retains drafts after %s failure and recovers with a read without replay",
    async (failure) => {
      const write = vi.fn(() =>
        failure === "csrf"
          ? HttpResponse.json({ detail: "csrf_failed", code: "csrf_failed" }, { status: 403 })
          : HttpResponse.json({ id: "unconfirmed" }),
      );
      server.use(http.post("*/api/v1/sandbox-templates", write));
      show();
      await ready();
      draft();
      fireEvent.click(screen.getByRole("button", { name: t.save }));
      await screen.findByText(failure === "csrf" ? messages.apiErrors.csrf : t.saveUnconfirmed);
      expect((screen.getByLabelText(t.name) as HTMLInputElement).value).toBe("A new workstation");
      expect(screen.queryByText(t.saved)).toBeNull();
      expect(screen.getByRole("button", { name: t.save }).matches(":disabled")).toBe(true);
      expect(screen.getByLabelText(t.name).matches(":disabled")).toBe(false);
      expect(screen.getByText(`Instance ID: ${instance.id}`)).toBeTruthy();
      refresh();
      await screen.findByText(t.checked);
      expect(write).toHaveBeenCalledTimes(1);
      expect(screen.getByRole("button", { name: t.save }).hasAttribute("disabled")).toBe(false);
    },
  );
  it("keeps an acknowledged save distinct from a failed follow-up list read", async () => {
    show();
    await ready();
    draft();
    server.use(
      http.post("*/api/v1/sandbox-templates", () =>
        HttpResponse.json({
          ...template,
          id: "saved",
          name: "A new workstation",
          slug: "new-workstation",
        }),
      ),
      http.get("*/api/v1/sandbox-templates", () =>
        HttpResponse.json({ detail: "Template refresh failed" }, { status: 503 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: t.save }));
    await screen.findByText(t.saved);
    await screen.findByText("Template refresh failed");
    expect((screen.getByLabelText(t.name) as HTMLInputElement).value).toBe("");
    expect(screen.queryByText(t.saveUnconfirmed)).toBeNull();
  });
});
describe("computer reads and stop confirmation", () => {
  it("renders ready templates while an independent instance read is still pending", async () => {
    const nativeFetch = globalThis.fetch;
    let resolve!: (value: Response) => void;
    const response = new Promise<Response>((done) => {
      resolve = done;
    });
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) =>
      String(input) === "/api/v1/sandboxes" ? response : nativeFetch(input, init),
    );
    show();
    await screen.findByText(template.name);
    const instances = screen.getByRole("region", { name: t.live });
    expect(instances.querySelector('[aria-busy="true"]')).toBeTruthy();
    expect(
      screen.getByRole("region", { name: t.listTitle }).querySelector('[aria-busy="true"]'),
    ).toBeNull();
    resolve(Response.json({ items: [instance] }));
    await ready();
  });
  it("keeps successful instance reads available when templates fail", async () => {
    server.use(
      http.get("*/api/v1/sandbox-templates", () =>
        HttpResponse.json({ detail: "Templates unavailable" }, { status: 503 }),
      ),
    );
    show();
    await ready();
    await screen.findByText("Templates unavailable");
    expect(screen.queryByText(t.empty)).toBeNull();
    expect(screen.getByRole("button", { name: `Stop instance ${instance.id}` })).toBeTruthy();
  });
  it("keeps templates and their creation controls available when instances fail", async () => {
    server.use(
      http.get("*/api/v1/sandboxes", () =>
        HttpResponse.json({ detail: "Instances unavailable" }, { status: 503 }),
      ),
    );
    show();
    await screen.findByText("Instances unavailable");
    draft();
    expect(screen.getByRole("button", { name: t.save }).hasAttribute("disabled")).toBe(false);
    expect(screen.queryByText(t.emptyLive)).toBeNull();
  });
  it.each(["templates", "instances"])(
    "rejects missing %s metadata without claiming an empty list",
    async (which) => {
      server.use(
        http.get(which === "templates" ? "*/api/v1/sandbox-templates" : "*/api/v1/sandboxes", () =>
          HttpResponse.json({}),
        ),
      );
      show();
      await screen.findByText(
        which === "templates" ? t.templateMetadataError : t.instanceMetadataError,
      );
      expect(screen.queryByText(which === "templates" ? t.empty : t.emptyLive)).toBeNull();
    },
  );
  it("checks manager permission before private reads and hides stop without chat permission", async () => {
    const reads = vi.fn(() => HttpResponse.json({ items: [] }));
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: [] })),
      http.get("*/api/v1/sandboxes", reads),
    );
    const view = show();
    await screen.findByText(t.readDenied);
    expect(reads).not.toHaveBeenCalled();
    view.unmount();
  });
  it("clears protected rows and creation controls when a list read loses access", async () => {
    show();
    await ready();
    server.use(
      http.get("*/api/v1/sandboxes", () =>
        HttpResponse.json({ detail: "Access refused" }, { status: 403 }),
      ),
    );
    refresh();
    await screen.findByText(t.readDenied);
    expect(screen.queryByText(`Instance ID: ${instance.id}`)).toBeNull();
    expect(screen.queryByLabelText(t.name)).toBeNull();
    expect(screen.queryByText(template.name)).toBeNull();
  });
  it("retains known rows and template drafts through a failed refresh", async () => {
    show();
    await ready();
    draft();
    server.use(
      http.get("*/api/v1/sandboxes", () =>
        HttpResponse.json({ detail: "Instances unavailable" }, { status: 503 }),
      ),
    );
    refresh();
    await screen.findByText("Instances unavailable");
    expect(screen.getByText(`Instance ID: ${instance.id}`)).toBeTruthy();
    expect((screen.getByLabelText(t.name) as HTMLInputElement).value).toBe("A new workstation");
    expect(
      screen.getByRole("button", { name: `Stop instance ${instance.id}` }).hasAttribute("disabled"),
    ).toBe(true);
  });
  it("does not expose Stop to managers without the route's chat permission", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["sandboxes:manage"] }),
      ),
    );
    show();
    await ready();
    expect(screen.queryByRole("button", { name: `Stop instance ${instance.id}` })).toBeNull();
    expect(screen.getByText(t.stopDenied)).toBeTruthy();
  });
  it("confirms the exact instance, starts on Cancel, and returns focus without a write", async () => {
    const write = vi.fn();
    server.use(http.post("*/api/v1/sandboxes/:id", write));
    show();
    await ready();
    const button = screen.getByRole("button", { name: `Stop instance ${instance.id}` });
    // The visible text is part of the accessible name (WCAG 2.5.3, label in name).
    expect(button.getAttribute("aria-label")).toContain(button.textContent?.trim() ?? "");
    expect(button.textContent?.trim()).toBe(t.stopConfirm);
    fireEvent.click(button);
    const dialog = await screen.findByRole("dialog", { name: t.stopTitle });
    await waitFor(() =>
      expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: t.cancel })),
    );
    expect(within(dialog).getByText(instance.id)).toBeTruthy();
    expect(within(dialog).getByText(t.stopHelp)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: t.cancel }));
    await waitFor(() => expect(document.activeElement).toBe(button));
    expect(write).not.toHaveBeenCalled();
  });
  it.each([true, false])(
    "accepts only a stopped receipt for the selected instance (matching=%s)",
    async (matching) => {
      const write = vi.fn(() =>
        HttpResponse.json({
          ...instance,
          id: matching ? instance.id : "other-instance",
          status: "terminated",
        }),
      );
      server.use(http.post(`*/api/v1/sandboxes/${instance.id}:terminate`, write));
      show();
      await ready();
      if (matching)
        server.use(
          http.get("*/api/v1/sandboxes", () =>
            HttpResponse.json({ items: [{ ...instance, status: "terminated" }] }),
          ),
        );
      fireEvent.click(screen.getByRole("button", { name: `Stop instance ${instance.id}` }));
      const dialog = await screen.findByRole("dialog");
      fireEvent.click(within(dialog).getByRole("button", { name: t.stopConfirm }));
      if (matching) {
        await screen.findByText(t.stopped);
        await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
        expect(screen.queryByRole("button", { name: `Stop instance ${instance.id}` })).toBeNull();
      } else {
        await screen.findByText(t.stopUnconfirmed);
        expect(screen.queryByText(t.stopped)).toBeNull();
        fireEvent.click(within(dialog).getByRole("button", { name: t.refresh }));
        await screen.findByText(t.checked);
        expect(write).toHaveBeenCalledTimes(1);
      }
    },
  );
  it("discloses supplied instance errors only on demand as escaped text", async () => {
    const error = "Start failed: <script>window.untrusted = true</script>";
    server.use(
      http.get("*/api/v1/sandboxes", () =>
        HttpResponse.json({ items: [{ ...instance, status: "failed", error }] }),
      ),
    );
    show();
    await ready();
    expect(screen.queryByText(error)).toBeNull();
    const disclosure = screen.getByText(t.recordedError).closest("details");
    if (!disclosure) throw new Error("Missing error disclosure");
    disclosure.open = true;
    fireEvent(disclosure, new Event("toggle"));
    await screen.findByText(error);
    expect(document.querySelector("script")).toBeNull();
    expect(
      screen.getByRole("region", { name: `Recorded error for instance ${instance.id}` }),
    ).toBeTruthy();
  });
  it("does not offer Stop for failed or terminated instances", async () => {
    server.use(
      http.get("*/api/v1/sandboxes", () =>
        HttpResponse.json({
          items: [
            { ...instance, status: "failed" },
            { ...instance, id: "computer-2", status: "terminated" },
          ],
        }),
      ),
    );
    show();
    await ready();
    expect(screen.queryByRole("button", { name: /^Stop instance / })).toBeNull();
  });
  it("bounds both 100,000-row lists and resets search/status with focus", async () => {
    server.use(
      http.get("*/api/v1/sandbox-templates", () =>
        HttpResponse.json({
          items: Array.from({ length: 100000 }, (_, i) => ({
            ...template,
            id: `tpl-${i}`,
            name: `Workstation ${i}`,
            slug: `workstation-${i}`,
          })),
        }),
      ),
      http.get("*/api/v1/sandboxes", () =>
        HttpResponse.json({
          items: Array.from({ length: 100000 }, (_, i) => ({
            ...instance,
            id: `computer-${i}`,
            status: i === 99999 ? "suspended" : "failed",
          })),
        }),
      ),
    );
    show();
    await ready();
    expect(screen.getAllByRole("listitem")).toHaveLength(50);
    fireEvent.change(screen.getByRole("searchbox", { name: t.findTemplate }), {
      target: { value: "workstation-99999" },
    });
    expect(screen.getByText("Workstation 99999")).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: t.status }), {
      target: { value: "suspended" },
    });
    expect(screen.getByText("Instance ID: computer-99999")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    fireEvent.click(screen.getAllByRole("button", { name: t.clearFilters })[1] as HTMLElement);
    expect(document.activeElement).toBe(screen.getByRole("searchbox", { name: t.findComputer }));
    expect(screen.getAllByRole("listitem")).toHaveLength(26);
  }, 15000);
  it("aborts pending writes on unmount and does not start a follow-up read", async () => {
    const nativeFetch = globalThis.fetch;
    let signal: AbortSignal | null | undefined;
    let resolve!: (value: Response) => void;
    const write = new Promise<Response>((done) => {
      resolve = done;
    });
    let reads = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input) === "/api/v1/sandbox-templates" && init?.method === "POST") {
        signal = init.signal;
        return write;
      }
      if (String(input) === "/api/v1/sandbox-templates") reads++;
      return nativeFetch(input, init);
    });
    const view = show();
    await ready();
    draft();
    fireEvent.click(screen.getByRole("button", { name: t.save }));
    await waitFor(() => expect(signal).toBeTruthy());
    view.unmount();
    expect(signal?.aborted).toBe(true);
    resolve(Response.json({ ...template, name: "A new workstation", slug: "new-workstation" }));
    await write;
    await new Promise((done) => setTimeout(done, 0));
    expect(reads).toBe(1);
  });
});
