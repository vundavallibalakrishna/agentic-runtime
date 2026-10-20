import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";

export const server = setupServer(
  http.get("http://127.0.0.1:8000/healthz", () => HttpResponse.json({ status: "ok" })),
);
