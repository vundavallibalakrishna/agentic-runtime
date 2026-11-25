import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import type { Attached } from "@/components/chat/attachment-list";
import { DocumentPicker, mentionStarted } from "@/components/chat/document-picker";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

function Harness({ onClose }: { onClose: () => void }) {
  const [chosen, setChosen] = useState<Attached[]>([]);
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <p data-testid="chosen">{chosen.map((item) => `${item.id}:${item.stored}`).join(",")}</p>
      <DocumentPicker
        chosen={chosen.map((item) => item.id)}
        onClose={onClose}
        onToggle={(document) =>
          setChosen((current) =>
            current.some((item) => item.id === document.id)
              ? current.filter((item) => item.id !== document.id)
              : [...current, document],
          )
        }
      />
    </NextIntlClientProvider>
  );
}

function library(items: object[]) {
  server.use(http.get("*/api/v1/library-documents", () => HttpResponse.json({ items })));
}

describe("document picker", () => {
  afterEach(cleanup);

  it("lists the library, narrows by name, and adds only the documents picked", async () => {
    library([
      { id: "d1", fileId: "f1", title: "Access policy" },
      { id: "d2", fileId: "f2", title: "Travel policy" },
      { id: "d3", title: "Not stored as a file" },
    ]);
    let closed = 0;
    render(<Harness onClose={() => (closed += 1)} />);
    expect(await screen.findByLabelText("Access policy")).toBeTruthy();
    // A document with no file cannot be sent, so it is not offered.
    expect(screen.queryByLabelText("Not stored as a file")).toBeNull();
    const search = screen.getByLabelText("Find a document");
    expect(document.activeElement).toBe(search);
    fireEvent.change(search, { target: { value: "travel" } });
    expect(screen.queryByLabelText("Access policy")).toBeNull();
    // Enter takes the highlighted document. It is sent as its file id.
    fireEvent.keyDown(search, { key: "Enter" });
    expect(screen.getByTestId("chosen").textContent).toBe("f2:true");
    fireEvent.change(search, { target: { value: "" } });
    fireEvent.click(screen.getByLabelText("Access policy"));
    expect(screen.getByTestId("chosen").textContent).toBe("f2:true,f1:true");
    // Picking it again takes it off.
    fireEvent.click(screen.getByLabelText("Travel policy"));
    expect(screen.getByTestId("chosen").textContent).toBe("f1:true");
    fireEvent.keyDown(search, { key: "Escape" });
    expect(closed).toBe(1);
  });

  it("says so when the library is empty or nothing matches", async () => {
    library([]);
    render(<Harness onClose={() => undefined} />);
    expect(
      await screen.findByText(
        "The library has no documents yet. Upload one on the Documents screen.",
      ),
    ).toBeTruthy();
    cleanup();
    library([{ id: "d1", fileId: "f1", title: "Access policy" }]);
    render(<Harness onClose={() => undefined} />);
    await screen.findByLabelText("Access policy");
    fireEvent.change(screen.getByLabelText("Find a document"), { target: { value: "zzz" } });
    expect(screen.getByText("No document has that name.")).toBeTruthy();
  });

  it("opens on an @ that starts a word, and not on one inside an address", () => {
    expect(mentionStarted("", "@", 1)).toBe(true);
    expect(mentionStarted("see ", "see @", 5)).toBe(true);
    expect(mentionStarted("ada", "ada@", 4)).toBe(false);
    // Pasting text that holds an @ is not typing one.
    expect(mentionStarted("", "mail ada@acme.example", 21)).toBe(false);
  });
});
