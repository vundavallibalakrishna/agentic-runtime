import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Providers } from "@/components/providers";
import messages from "@/messages/en.json";

import "./globals.css";

export const metadata: Metadata = {
  title: "Agentic Runtime",
  description: "TalentFino Agentic Runtime",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers messages={messages}>{children}</Providers>
      </body>
    </html>
  );
}
