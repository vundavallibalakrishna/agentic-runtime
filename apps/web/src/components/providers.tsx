"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { type ReactNode, useState } from "react";

import { AppToaster } from "@/components/ui/toaster";

export function Providers({
  children,
  messages,
}: {
  children: ReactNode;
  messages: Record<string, unknown>;
}) {
  const [client] = useState(() => new QueryClient());
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <QueryClientProvider client={client}>
        {children}
        <AppToaster />
      </QueryClientProvider>
    </NextIntlClientProvider>
  );
}
