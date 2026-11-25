import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import { filled, NotesView, wholeGuide } from "@/components/developers/notes-view";
import notes from "@/generated/developer-notes.json";
import messages from "@/messages/en.json";

const values = { baseUrl: "https://work.example", agentSlug: "helpdesk" };

describe("developer notes", () => {
  afterEach(cleanup);

  it("puts the workspace's address and agent in the samples, and never a key", () => {
    const text = wholeGuide(values);
    expect(text).toContain("https://work.example/api/v1/files:upload");
    expect(text).toContain("https://work.example/v1/agents/helpdesk:run");
    expect(text).not.toContain("{{");
    // A sample reads its key from the caller's own environment.
    expect(text).toContain('"Authorization: Bearer $CURA_KEY"');
    // No sample holds anything shaped like a real secret.
    expect(text).not.toMatch(/sk_[A-Za-z0-9]{16,}/);
    expect(text).not.toMatch(/ara_[A-Za-z0-9]{20,}/);
    expect(filled("{{BASE_URL}}/x {{AGENT_SLUG}}", values)).toBe("https://work.example/x helpdesk");
  });

  it("has a note for each thing an integrator does", () => {
    const slugs = notes.map((note) => note.slug);
    for (const wanted of [
      "connect-your-platform",
      "documents-and-knowledge",
      "chat",
      "embed",
      "known-differences",
    ])
      expect(slugs).toContain(wanted);
    const chat = notes.find((note) => note.slug === "chat")?.body ?? "";
    for (const heading of ["## Attach documents", "## Mention documents", "## Read citations"])
      expect(chat).toContain(heading);
  });

  it("opens a note from the list and narrows the list by a search", () => {
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <NotesView agentSlug="helpdesk" baseUrl="https://work.example" />
      </NextIntlClientProvider>,
    );
    expect(screen.getByRole("button", { name: "Connect your platform" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Chat from your application" }));
    expect(
      screen
        .getByRole("button", { name: "Chat from your application" })
        .getAttribute("aria-current"),
    ).toBe("page");
    expect(screen.getByTestId("note").textContent).toContain("Mention documents");
    fireEvent.change(screen.getByLabelText("Search the notes"), {
      target: { value: "frame-ancestors-not-a-word" },
    });
    expect(screen.getByText("No note has those words.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Search the notes"), { target: { value: "JWKS" } });
    expect(screen.getByRole("button", { name: "Embed the chat" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Known differences" })).toBeNull();
  });
});
