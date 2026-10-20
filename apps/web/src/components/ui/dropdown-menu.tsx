"use client";

import * as Dropdown from "@radix-ui/react-dropdown-menu";
import type { ReactNode } from "react";

export function DropdownMenu({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Dropdown.Root>
      <Dropdown.Trigger className="rounded-md border border-[var(--border)] px-3 py-2 text-sm">
        {label}
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content className="rounded-md border border-[var(--border)] bg-[var(--card)] p-1">
          {children}
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}

export function DropdownMenuItem({ children }: { children: ReactNode }) {
  return (
    <Dropdown.Item className="cursor-pointer rounded px-2 py-1 text-sm outline-none">
      {children}
    </Dropdown.Item>
  );
}
