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

  it("renders returned account metadata without inventing a sign-in time", () => {
    render(
      wrap(
        <UsersPanel
          users={[
            {
              id: "1",
              email: "admin@dev.local",
              displayName: "Dev Admin",
              status: "active",
              lastLoginAt: null,
            },
          ]}
        />,
      ),
    );
    expect(screen.getByText("Dev Admin")).toBeTruthy();
    expect(screen.getByText("admin@dev.local")).toBeTruthy();
    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.getByText("No recorded sign-in")).toBeTruthy();
    expect(screen.getAllByRole("columnheader")).toHaveLength(4);
  });
});
