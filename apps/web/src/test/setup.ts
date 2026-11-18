import { afterAll, afterEach, beforeAll } from "vitest";

import { clearInflightGets } from "@/lib/api";
import { clearCachedSession } from "@/lib/session";

import { server } from "./server";

beforeAll(() => {
  server.listen();
});
afterEach(() => {
  clearCachedSession();
  clearInflightGets();
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});
