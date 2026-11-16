import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Badge, statusTone } from "@/components/ui/badge";

describe("Badge", () => {
  afterEach(() => cleanup());

  it("gives each kind of status its own tone", () => {
    expect(statusTone("published")).toBe("success");
    expect(statusTone("completed")).toBe("success");
    expect(statusTone("running")).toBe("info");
    expect(statusTone("waiting_approval")).toBe("warning");
    expect(statusTone("draft")).toBe("warning");
    expect(statusTone("failed")).toBe("danger");
  });

  it("keeps a status it does not know neutral", () => {
    expect(statusTone("archived")).toBe("neutral");
    expect(statusTone(undefined)).toBe("neutral");
    expect(statusTone("something-new")).toBe("neutral");
  });

  it("draws the tone it is given and stays neutral without one", () => {
    render(
      <>
        <Badge tone="danger">failed</Badge>
        <Badge>plain</Badge>
      </>,
    );
    expect(screen.getByText("failed").className).toContain("tone-danger");
    expect(screen.getByText("plain").className).not.toContain("tone");
  });
});
