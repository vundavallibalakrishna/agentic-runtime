import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MarkdownView } from "@/components/chat/markdown-view";

describe("Markdown view", () => {
  afterEach(() => cleanup());

  it("draws a line that starts with a masking token, which Markdown read as a link definition", () => {
    const { container } = render(
      <MarkdownView text={"The totals are:\n\n- [NRP]: 1042.5\n- North: 817.0\n- [NRP]: 420.5"} />,
    );
    const items = Array.from(container.querySelectorAll("li")).map((item) => item.textContent);
    expect(items).toEqual(["[NRP]: 1042.5", "North: 817.0", "[NRP]: 420.5"]);
    expect(container.querySelectorAll("code")).toHaveLength(2);
  });

  it("still draws an ordinary link", () => {
    const { container } = render(<MarkdownView text="See [the docs](https://example.com/docs)." />);
    const link = container.querySelector("a");
    expect(link?.getAttribute("href")).toBe("https://example.com/docs");
    expect(link?.textContent).toBe("the docs");
  });
});
