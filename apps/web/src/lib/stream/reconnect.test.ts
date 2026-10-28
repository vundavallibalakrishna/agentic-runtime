import { describe, expect, it } from "vitest";

import { shouldResumeStatus, shouldResumeStream, streamHeaders } from "./reconnect";

describe("stream reconnect", () => {
  it("resumes a dropped stream until the cap", () => {
    expect(shouldResumeStream("streaming", 1)).toBe(true);
    expect(shouldResumeStream("idle", 2)).toBe(true);
    expect(shouldResumeStream("streaming", 3)).toBe(false);
    expect(shouldResumeStream("completed", 1)).toBe(false);
    expect(shouldResumeStream("failed", 0)).toBe(false);
    expect(shouldResumeStream("cancelled", 0)).toBe(false);
  });

  it("retries gateway errors and keeps the last event id", () => {
    expect(shouldResumeStatus(503, 1)).toBe(true);
    expect(shouldResumeStatus(404, 1)).toBe(false);
    expect(shouldResumeStatus(503, 3)).toBe(false);
    expect(streamHeaders(0)).toEqual({});
    expect(streamHeaders(4)).toEqual({ "Last-Event-ID": "4" });
  });
});
