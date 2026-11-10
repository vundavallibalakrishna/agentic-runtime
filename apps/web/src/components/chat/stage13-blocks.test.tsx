import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Followups } from "@/components/chat/followups";
import { MessageBody } from "@/components/chat/message-body";
import { PlanChecklist } from "@/components/chat/plan-checklist";
import { ThinkingBlock } from "@/components/chat/thinking-block";
import messages from "@/messages/en.json";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("stage 13 chat blocks", () => {
  afterEach(() => cleanup());

  it("renders a plan, thinking, a chart image and a follow-up", () => {
    const pick = vi.fn();
    render(
      wrap(
        <div>
          <PlanChecklist items={[{ id: "1", title: "Read the notes", status: "done" }]} />
          <ThinkingBlock durationMs={2000} text="Comparing the two files." />
          <MessageBody
            message={{
              content: [
                { type: "text", text: "The notes list two gaps." },
                { type: "image", fileId: "file-1", alt: "Counts" },
              ],
              toolCalls: [
                {
                  presentation: {
                    kind: "chart",
                    files: [{ fileId: "file-1", name: "chart.png" }],
                  },
                },
              ],
            }}
            onFollowup={pick}
            prompts={["What is missing?"]}
            text="The notes list two gaps."
          />
          <Followups onPick={pick} prompts={["Show the chart"]} />
        </div>,
      ),
    );
    expect(screen.getByTestId("plan-checklist").textContent).toContain("Read the notes");
    expect(screen.getByTestId("thinking").textContent).toContain("Comparing the two files.");
    expect(screen.getByRole("img", { name: "Counts" }).getAttribute("src")).toBe(
      "/api/v1/files/file-1/content",
    );
    fireEvent.click(screen.getByRole("button", { name: "Show the chart" }));
    expect(pick).toHaveBeenCalledWith("Show the chart");
  });
});
