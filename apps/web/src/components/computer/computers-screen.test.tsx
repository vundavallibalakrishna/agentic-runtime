import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { ComputersScreen } from "@/components/computer/computers-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => children,
}));
beforeEach(() => {
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ permissions: ["sandboxes:manage", "chat:use"] }),
    ),
  );
});
afterEach(() => {
  cleanup();
  window.localStorage.clear();
});
function show() {
  server.use(
    http.get("*/api/v1/sandbox-templates", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/sandboxes", () =>
      HttpResponse.json({
        items: Array.from({ length: 30 }, (_, id) => ({
          id: `instance-${id}`,
          scopeKey: "same-conversation",
          status: id === 29 ? "ready" : "failed",
        })),
      }),
    ),
  );
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ComputersScreen />
    </NextIntlClientProvider>,
  );
}
it("starts template identity empty and uses positive numeric resource controls", async () => {
  show();
  await screen.findByText("Instance ID: instance-0");
  expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText("Slug") as HTMLInputElement).value).toBe("");
  expect(
    (screen.getByRole("button", { name: "Save template" }) as HTMLButtonElement).disabled,
  ).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
  const cpu = screen.getByLabelText("CPU (millicores)") as HTMLInputElement;
  expect(cpu.type).toBe("number");
  expect(cpu.min).toBe("1");
  expect((screen.getByLabelText("Memory (MB)") as HTMLInputElement).type).toBe("number");
  server.use(
    http.post("*/api/v1/sandbox-templates", () =>
      HttpResponse.json({
        id: "new-template",
        name: "Workstation",
        slug: "workstation",
        cpuMillis: 7000,
        memoryMb: 8192,
        allowPackages: false,
      }),
    ),
    http.get("*/api/v1/sandbox-templates", () =>
      HttpResponse.json({
        items: [
          {
            id: "new-template",
            name: "Workstation",
            slug: "workstation",
            cpuMillis: 7000,
            memoryMb: 8192,
            allowPackages: false,
          },
        ],
      }),
    ),
  );
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Workstation" } });
  fireEvent.change(screen.getByLabelText("Slug"), { target: { value: "workstation" } });
  fireEvent.click(screen.getByRole("button", { name: "Save template" }));
  await screen.findByText("Template saved.");
  expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText("Slug") as HTMLInputElement).value).toBe("");
});
it("distinguishes repeated scopes, bounds rows, and filters by status or instance ID", async () => {
  show();
  await screen.findByText("Instance ID: instance-0");
  expect(screen.getAllByText("same-conversation")).toHaveLength(25);
  expect(screen.queryByText("Instance ID: instance-29")).toBeNull();
  fireEvent.change(screen.getByRole("combobox", { name: "Status" }), {
    target: { value: "ready" },
  });
  expect(screen.getByText("Instance ID: instance-29")).toBeTruthy();
  fireEvent.change(screen.getByRole("combobox", { name: "Status" }), { target: { value: "" } });
  fireEvent.change(
    screen.getByRole("searchbox", { name: "Find an instance by ID, conversation or template" }),
    { target: { value: "instance-28" } },
  );
  expect(screen.getByText("Instance ID: instance-28")).toBeTruthy();
  expect(screen.getAllByText("same-conversation")).toHaveLength(1);
});
