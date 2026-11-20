import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { clearInflightGets } from "@/lib/api";
import { clearCachedSession } from "@/lib/session";

import { server } from "./server";

beforeAll(() => {
  server.listen();
});
afterEach(() => {
  // Take every rendered screen off the page. The library does this by itself only when
  // the test functions are globals, which they are not here. A screen left mounted can
  // finish a request after its test has ended and ask React to draw again once the
  // browser environment is gone ("window is not defined", on some runs).
  cleanup();
  clearCachedSession();
  clearInflightGets();
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});
