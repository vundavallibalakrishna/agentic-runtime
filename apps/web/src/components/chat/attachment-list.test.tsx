import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AttachmentList, attachedOf, fileSize } from "@/components/chat/attachment-list";
import messages from "@/messages/en.json";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("Attached files", () => {
  afterEach(() => cleanup());

  it("shows each file with its type and size, and opens it", () => {
    render(
      wrap(
        <AttachmentList
          files={[
            { id: "f1", name: "orders.csv", mimeType: "text/csv", sizeBytes: 354 },
            { id: "f2", name: "policy.pdf", mimeType: "application/pdf", sizeBytes: 19168 },
          ]}
        />,
      ),
    );
    const list = screen.getByRole("list", { name: "Attached files" });
    expect(list.textContent).toContain("orders.csv");
    expect(list.textContent).toContain("(text/csv, 354 B)");
    expect(list.textContent).toContain("(application/pdf, 18.7 kB)");
    const link = screen.getByRole("link", { name: "policy.pdf" }) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe("/api/v1/files/f2/content");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("finds the files on a reply that a limit stopped", () => {
    const stopped = {
      role: "assistant",
      status: "completed",
      text: "Stopped because the max tokens limit was reached.",
      content: [
        { type: "text", text: "Stopped because the max tokens limit was reached." },
        { type: "file", fileId: "f1", name: "matrix.xlsx", mimeType: "application/zip" },
        { type: "file", fileId: "f2", name: "deck.pptx", mimeType: "application/zip" },
      ],
    };
    expect(attachedOf(stopped).map((file) => file.name)).toEqual(["matrix.xlsx", "deck.pptx"]);
    render(wrap(<AttachmentList files={attachedOf(stopped)} />));
    const link = screen.getByRole("link", { name: "deck.pptx" }) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe("/api/v1/files/f2/content");
  });

  it("lets a file be taken off before sending", () => {
    const remove = vi.fn();
    render(
      wrap(
        <AttachmentList
          files={[{ id: "f1", name: "orders.csv", mimeType: "text/csv", sizeBytes: 354 }]}
          onRemove={remove}
        />,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Remove orders.csv" }));
    expect(remove).toHaveBeenCalledWith("f1");
  });

  it("draws nothing for a message without files", () => {
    const { container } = render(wrap(<AttachmentList files={[]} />));
    expect(container.innerHTML).toBe("");
  });

  it("reads a stored message's file parts, with or without a size", () => {
    expect(
      attachedOf({
        content: [
          { type: "text", text: "Total this" },
          { type: "file", fileId: "f1", name: "orders.csv", mimeType: "text/csv", sizeBytes: 354 },
          { type: "file", fileId: "f2", name: "old.pdf", mimeType: "application/pdf" },
          { type: "file", name: "no id" },
        ],
      }),
    ).toEqual([
      { id: "f1", name: "orders.csv", mimeType: "text/csv", sizeBytes: 354 },
      { id: "f2", name: "old.pdf", mimeType: "application/pdf", sizeBytes: undefined },
    ]);
    expect(attachedOf({ text: "plain" })).toEqual([]);
    expect(fileSize(undefined)).toBe("");
    expect(fileSize(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});
