import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { PermissionGate } from "@/components/permission-gate";
import { UsersPanel } from "@/components/users-panel";
import messages from "@/messages/en.json";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("admin panels", () => {
  it("hides children when the permission is missing", () => {
    render(wrap(<PermissionGate allowed={false}>secret</PermissionGate>));
    expect(screen.getByRole("alert").textContent).toContain("permission");
    expect(screen.queryByText("secret")).toBeNull();
  });

  it("renders loading, empty, error and a camelCase user row", () => {
    const { rerender } = render(wrap(<UsersPanel status="loading" users={[]} />));
    expect(screen.getByText("Loading users")).toBeTruthy();
    rerender(wrap(<UsersPanel status="empty" users={[]} />));
    expect(screen.getByText(/No users yet/)).toBeTruthy();
    rerender(wrap(<UsersPanel status="error" users={[]} />));
    expect(screen.getByText(/could not be loaded/)).toBeTruthy();
    rerender(
      wrap(
        <UsersPanel
          status="ready"
          users={[{ id: "1", email: "admin@dev.local", displayName: "Dev Admin" }]}
        />,
      ),
    );
    expect(screen.getByText("Dev Admin")).toBeTruthy();
    expect(screen.getByText("admin@dev.local")).toBeTruthy();
  });
});
