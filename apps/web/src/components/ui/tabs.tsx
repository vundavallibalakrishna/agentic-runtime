"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ComponentProps, ReactNode } from "react";

export function Tabs(props: ComponentProps<typeof TabsPrimitive.Root>) {
  return <TabsPrimitive.Root {...props} />;
}

export function TabsList({ children }: { children: ReactNode }) {
  return (
    <TabsPrimitive.List className="mb-5 flex flex-wrap gap-1 rounded-lg bg-[var(--muted)] p-1">
      {children}
    </TabsPrimitive.List>
  );
}

export function TabsTrigger({
  value,
  children,
  disabled = false,
}: {
  value: string;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <TabsPrimitive.Trigger
      className="min-h-9 rounded-md px-3 py-2 text-sm text-[var(--muted-foreground)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] disabled:cursor-not-allowed disabled:opacity-50 data-[state=active]:bg-[var(--card)] data-[state=active]:text-[var(--foreground)] data-[state=active]:shadow-[var(--shadow-xs)]"
      value={value}
      disabled={disabled}
    >
      {children}
    </TabsPrimitive.Trigger>
  );
}

export function TabsContent({
  value,
  children,
  forceMount,
}: {
  value: string;
  children: ReactNode;
  forceMount?: true;
}) {
  return (
    <TabsPrimitive.Content
      className="min-w-0 outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] data-[state=inactive]:hidden"
      value={value}
      forceMount={forceMount}
    >
      {children}
    </TabsPrimitive.Content>
  );
}
