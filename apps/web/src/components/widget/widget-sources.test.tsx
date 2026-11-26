import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import { WidgetSources } from "@/components/widget/widget-sources";
import messages from "@/messages/en.json";

function cite(index: number, title: string, uri: string) {
  return { type: "citation_ref", index, citation: { index, title, uri, snippet: "" } };
}

function show(content: unknown[], open = true) {
  const view = render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <WidgetSources message={{ id: "m1", content }} />
    </NextIntlClientProvider>,
  );
  const toggle = screen.queryByRole("button", { name: /^Sources/ });
  if (open && toggle) fireEvent.click(toggle);
  return view;
}

describe("widget sources", () => {
  afterEach(cleanup);

  it("keeps the sources closed until the visitor asks for them", () => {
    show(
      [
        cite(1, "Industries", "https://example.test/industries/"),
        cite(2, "Risk", "https://example.test/risk/"),
      ],
      false,
    );
    const toggle = screen.getByRole("button", { name: "Sources (2)" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("link")).toBeNull();
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getAllByRole("link")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Hide sources" }));
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("lists each cited source, linking a web page outside the chat frame", () => {
    show([
      { type: "text", text: "Banks [1] and incidents [3]." },
      cite(1, "Industries", "https://example.test/industries/"),
      cite(3, "Handbook", "s3://bucket/tenant/handbook.pdf"),
    ]);
    const list = screen.getByRole("region", { name: "Sources" });
    const link = screen.getByRole("link", { name: /Industries/ }) as HTMLAnchorElement;
    expect(link.href).toBe("https://example.test/industries/");
    expect(link.target).toBe("_blank");
    expect(link.rel).toBe("noopener noreferrer");
    // A stored file is named, never linked: a visitor cannot open the workspace's files.
    expect(screen.queryByRole("link", { name: /Handbook/ })).toBeNull();
    expect(list.textContent).toContain("[3]Handbook");
  });

  it("lists a page cited twice once, with both numbers", () => {
    show([
      cite(1, "Incidents", "https://example.test/incidents/"),
      cite(2, "Risk", "https://example.test/risk/"),
      cite(5, "Incidents", "https://example.test/incidents/"),
    ]);
    const items = screen.getAllByRole("listitem").map((item) => item.textContent);
    expect(items).toEqual(["[1, 5]Incidents(opens in a new tab)", "[2]Risk(opens in a new tab)"]);
  });

  it("does not link a script address", () => {
    show([cite(1, "Trap", "javascript:alert(1)")]);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("Trap")).toBeTruthy();
  });

  it("shows nothing for an answer that cites nothing", () => {
    const { container } = show([{ type: "text", text: "Hello" }]);
    expect(container.textContent).toBe("");
  });
});
