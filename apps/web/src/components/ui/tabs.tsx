"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

export function Tabs({ defaultValue, children }: { defaultValue: string; children: ReactNode }) {
  return <TabsPrimitive.Root defaultValue={defaultValue}>{children}</TabsPrimitive.Root>;
}

export function TabsList({ children }: { children: ReactNode }) {
  return (
    <TabsPrimitive.List className="mb-5 flex flex-wrap gap-1 rounded-lg bg-[var(--muted)] p-1">
      {children}
    </TabsPrimitive.List>
  );
}

export function TabsTrigger({ value, children }: { value: string; children: ReactNode }) {
  return (
    <TabsPrimitive.Trigger
      className="min-h-9 rounded-md px-3 py-2 text-sm text-[var(--muted-foreground)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] data-[state=active]:bg-[var(--card)] data-[state=active]:text-[var(--foreground)] data-[state=active]:shadow-[var(--shadow-xs)]"
      value={value}
    >
      {children}
    </TabsPrimitive.Trigger>
  );
}

export function TabsContent({ value, children }: { value: string; children: ReactNode }) {
  return (
    <TabsPrimitive.Content
      className="min-w-0 outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
      value={value}
    >
      {children}
    </TabsPrimitive.Content>
  );
}
