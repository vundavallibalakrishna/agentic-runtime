import { afterEach, describe, expect, it, vi } from "vitest";
import { confirmStepUp } from "@/lib/step-up";

afterEach(() => vi.unstubAllGlobals());
describe("session confirmation acknowledgement", () => {
  it.each([true, "true"])("accepts the API acknowledgement %s", async (steppedUp) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json({ steppedUp })),
    );
    await expect(confirmStepUp("Confirmation incomplete")).resolves.toBeUndefined();
  });
  it.each([false, "false", undefined, "yes"])(
    "refuses an unconfirmed successful response %s",
    async (steppedUp) => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => Response.json({ steppedUp })),
      );
      await expect(confirmStepUp("Confirmation incomplete")).rejects.toThrow(
        "Confirmation incomplete",
      );
    },
  );
  it("checks cancellation even if transport delivers a late acknowledgement", async () => {
    const controller = new AbortController();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        controller.abort();
        return Response.json({ steppedUp: true });
      }),
    );
    await expect(confirmStepUp("Confirmation incomplete", controller.signal)).rejects.toThrow();
  });
});
