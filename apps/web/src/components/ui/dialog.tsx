"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import type { ComponentProps, ReactNode } from "react";

export function Dialog(props: ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root {...props} />;
}

export function DialogTrigger({ children }: { children: ReactNode }) {
  return <DialogPrimitive.Trigger asChild>{children}</DialogPrimitive.Trigger>;
}

export function DialogContent({ title, children }: { title: string; children: ReactNode }) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[var(--scrim)]" />
      <DialogPrimitive.Content className="fixed left-1/2 top-1/2 z-50 max-h-[85dvh] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-lg">
        <DialogPrimitive.Title className="text-base font-semibold">{title}</DialogPrimitive.Title>
        <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
