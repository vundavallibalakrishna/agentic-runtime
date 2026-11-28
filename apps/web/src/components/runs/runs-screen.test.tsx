import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { expect, it, vi } from "vitest";
import messages from "@/messages/en.json";
import { server } from "@/test/server";
import { RunsScreen } from "./runs-screen";

vi.mock("next/navigation", () => ({
  usePathname: () => "/runs",
  useParams: () => ({}),
  useRouter: () => ({ push: () => undefined }),
}));

it("pages and filters on the server without displaying a false no-matches state", async () => {
  const requests: URLSearchParams[] = [];
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["chat:use"] })),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/runs", ({ request }) => {
      const params = new URL(request.url).searchParams;
      requests.push(params);
      const id = params.get("q") || params.get("cursor") || "first";
      return HttpResponse.json({
        items: [{ id, trigger: `Run ${id}`, status: params.get("status") || "completed" }],
        hasMore: !params.get("cursor"),
        nextCursor: params.get("cursor") ? null : "second",
      });
    }),
  );
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <RunsScreen />
    </NextIntlClientProvider>,
  );
  await screen.findByText("Run first");
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  await screen.findByText("Run second");
  expect(requests.at(-1)?.get("cursor")).toBe("second");
  fireEvent.change(screen.getByLabelText(messages.runs.status), { target: { value: "failed" } });
  await screen.findByText("Run first");
  expect(requests.at(-1)?.get("status")).toBe("failed");
  expect(requests.at(-1)?.has("cursor")).toBe(false);
  expect(screen.queryByText(messages.runs.noMatches)).toBeNull();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "older" } });
  await screen.findByText("Run older");
  await waitFor(() => expect(requests.at(-1)?.get("q")).toBe("older"));
  expect(requests.every((params) => params.get("limit") === "25")).toBe(true);
});
