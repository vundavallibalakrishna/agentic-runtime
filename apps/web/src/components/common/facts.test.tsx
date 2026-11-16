import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { Facts } from "./facts";

it("shows each fact with its label and leaves out a fact with no value", () => {
  render(
    <Facts
      items={[
        { label: "Trigger", value: "Every Monday" },
        { label: "Webhook address", value: null },
        { label: "Pages", value: "" },
      ]}
    />,
  );
  expect(screen.getByText("Trigger").tagName).toBe("DT");
  expect(screen.getByText("Every Monday").tagName).toBe("DD");
  expect(screen.queryByText("Webhook address")).toBeNull();
  expect(screen.queryByText("Pages")).toBeNull();
});
