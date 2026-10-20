"use client";

import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";

export function Sheet({
  title,
  trigger,
  children,
}: {
  title: string;
  trigger: string;
  children: string;
}) {
  return (
    <Dialog>
      <DialogTrigger>
        <button type="button">{trigger}</button>
      </DialogTrigger>
      <DialogContent title={title}>{children}</DialogContent>
    </Dialog>
  );
}
