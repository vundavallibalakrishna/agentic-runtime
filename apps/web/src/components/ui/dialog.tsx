"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import type { ComponentProps, ReactNode } from "react";

export function Dialog(props: ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root {...props} />;
}

export function DialogTrigger({ children }: { children: ReactNode }) {
  return <DialogPrimitive.Trigger asChild>{children}</DialogPrimitive.Trigger>;
}

export function DialogContent({
  title,
  children,
  footer,
  onOpenAutoFocus,
  onCloseAutoFocus,
}: {
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  onOpenAutoFocus?: ComponentProps<typeof DialogPrimitive.Content>["onOpenAutoFocus"];
  onCloseAutoFocus?: ComponentProps<typeof DialogPrimitive.Content>["onCloseAutoFocus"];
}) {
  const heading = (
    <>
      <DialogPrimitive.Title className="text-base font-semibold">{title}</DialogPrimitive.Title>
      <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
    </>
  );
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[var(--scrim)]" />
      <DialogPrimitive.Content
        onOpenAutoFocus={onOpenAutoFocus}
        onCloseAutoFocus={onCloseAutoFocus}
        className={`fixed left-1/2 top-1/2 z-50 max-h-[85dvh] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-lg ${footer ? "flex flex-col overflow-hidden" : "overflow-auto p-6"}`}
      >
        {footer ? (
          <>
            <div className="shrink-0 px-6 pt-6">{heading}</div>
            <div className="min-h-0 overflow-y-auto px-6 pb-6">{children}</div>
            <div
              data-slot="dialog-footer"
              className="shrink-0 border-t border-[var(--border)] bg-[var(--card)] px-6 py-4"
            >
              {footer}
            </div>
          </>
        ) : (
          <>
            {heading}
            {children}
          </>
        )}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
