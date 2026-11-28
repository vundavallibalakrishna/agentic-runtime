import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { type UserRow, UsersPanel } from "@/components/users-panel";
import messages from "@/messages/en.json";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

const people: UserRow[] = [
  { id: "1", email: "admin@x.test", displayName: "Ada Admin", status: "active", lastLoginAt: null },
  { id: "2", email: "mo@x.test", displayName: "Mo Member", status: "active", lastLoginAt: null },
  { id: "3", email: "sam@x.test", displayName: "Sam Gone", status: "suspended", lastLoginAt: null },
];

describe("the people of a workspace", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows each person's status, and no actions to someone who may only read", () => {
    render(wrap(<UsersPanel users={people} />));
    expect(screen.getAllByText("Active")).toHaveLength(2);
    expect(screen.getByText("Suspended")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByText("Actions")).toBeNull();
  });

  it("asks before suspending, and suspends only on yes", async () => {
    const onStatus = vi.fn(async () => {});
    render(wrap(<UsersPanel onStatus={onStatus} selfId="1" users={people} />));
    fireEvent.click(screen.getByRole("button", { name: "Suspend Mo Member" }));
    expect(screen.getByText(/signed out at once/)).toBeTruthy();
    expect(onStatus).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText(/signed out at once/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Suspend Mo Member" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, suspend" }));
    await waitFor(() => expect(onStatus).toHaveBeenCalledWith(people[1], "suspended"));
  });

  it("offers no action on the viewer's own row", () => {
    render(wrap(<UsersPanel onStatus={async () => {}} selfId="1" users={people} />));
    expect(screen.getByText("(You)")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Suspend Ada Admin" })).toBeNull();
  });

  it("lets a suspended person back in with one press", async () => {
    const onStatus = vi.fn(async () => {});
    render(wrap(<UsersPanel onStatus={onStatus} selfId="1" users={people} />));
    fireEvent.click(screen.getByRole("button", { name: "Let Sam Gone back in" }));
    await waitFor(() => expect(onStatus).toHaveBeenCalledWith(people[2], "active"));
  });

  it("says why when the change is refused", async () => {
    const onStatus = vi.fn(async () => {
      throw new Error("you cannot suspend this person");
    });
    render(wrap(<UsersPanel onStatus={onStatus} selfId="1" users={people} />));
    fireEvent.click(screen.getByRole("button", { name: "Suspend Mo Member" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, suspend" }));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain("you cannot suspend this person"),
    );
  });
});
