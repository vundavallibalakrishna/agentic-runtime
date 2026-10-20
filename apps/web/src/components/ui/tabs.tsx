"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

export function Tabs({ defaultValue, children }: { defaultValue: string; children: ReactNode }) {
  return <TabsPrimitive.Root defaultValue={defaultValue}>{children}</TabsPrimitive.Root>;
}

export function TabsList({ children }: { children: ReactNode }) {
  return <TabsPrimitive.List className="flex gap-2">{children}</TabsPrimitive.List>;
}

export function TabsTrigger({ value, children }: { value: string; children: ReactNode }) {
  return (
    <TabsPrimitive.Trigger className="rounded-md px-3 py-1 text-sm" value={value}>
      {children}
    </TabsPrimitive.Trigger>
  );
}

export function TabsContent({ value, children }: { value: string; children: ReactNode }) {
  return <TabsPrimitive.Content value={value}>{children}</TabsPrimitive.Content>;
}
