"use client";

import { Label } from "@radix-ui/react-label";
import type { ReactNode } from "react";
import { FormProvider, type UseFormReturn, useForm } from "react-hook-form";

import { Input } from "@/components/ui/input";

type SampleValues = { name: string };

export function SampleForm({ onSubmit }: { onSubmit?: (values: SampleValues) => void }) {
  const form: UseFormReturn<SampleValues> = useForm<SampleValues>({ defaultValues: { name: "" } });
  return (
    <FormProvider {...form}>
      <form
        onSubmit={form.handleSubmit((values) => {
          onSubmit?.(values);
        })}
      >
        <Label htmlFor="agent-name">Agent name</Label>
        <Input id="agent-name" {...form.register("name")} />
        <FormNote>Shown on the agent card.</FormNote>
      </form>
    </FormProvider>
  );
}

export function FormNote({ children }: { children: ReactNode }) {
  return <p className="text-sm text-[var(--muted-foreground)]">{children}</p>;
}
