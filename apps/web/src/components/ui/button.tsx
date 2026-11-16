import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex min-h-9 items-center justify-center rounded-md px-3.5 py-2 text-sm font-medium disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--primary)] font-semibold text-[var(--primary-foreground)] hover:bg-[var(--primary-hover)]",
        outline:
          "border border-[var(--border)] bg-[var(--card)] text-[var(--foreground)] hover:bg-[var(--muted)]",
        ghost: "bg-transparent text-[var(--foreground)] hover:bg-[var(--muted)]",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean };

export function Button({ className, variant, asChild = false, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant }), className)} {...props} />;
}
