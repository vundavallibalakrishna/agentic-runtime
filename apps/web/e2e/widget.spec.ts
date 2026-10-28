import { createHmac, randomUUID } from "node:crypto";
import { createServer, type Server } from "node:http";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

let host: Server;
let hostOrigin = "";
let integrationId = "";
let appOrigin = "";
let csrf = "";
const signingKey = randomUUID();

test.describe.configure({ mode: "serial" });

function token(expired = false) {
  const head = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const body = Buffer.from(
    JSON.stringify({
      sub: "admin@dev.local",
      name: "Admin",
      aud: `ar-widget:${integrationId}`,
      exp: Math.floor(Date.now() / 1000) + (expired ? -10 : 120),
    }),
  ).toString("base64url");
  return `${head}.${body}.${createHmac("sha256", signingKey).update(`${head}.${body}`).digest("base64url")}`;
}

test.beforeAll(async ({ request, baseURL }) => {
  appOrigin = baseURL || "http://localhost:3000";
  host = createServer((req, res) => {
    if (req.url?.startsWith("/token")) {
      res.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end(JSON.stringify({ token: token(req.url.includes("expired")) }));
      return;
    }
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(`<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Portal chat test</title></head><body><main><h1>Team portal</h1><p>Your connected workspace assistant.</p></main><script>
window.addEventListener('ar-widget:token-request', async event => { const data = await fetch('/token${req.url?.includes("expired") ? "?expired=1" : ""}').then(r => r.json()); event.detail.respond(data.token); });
</script><script src="${appOrigin}/widget.js" data-integration="${integrationId}"></script></body></html>`);
  });
  await new Promise<void>((resolve) => host.listen(0, "127.0.0.1", resolve));
  const address = host.address();
  if (!address || typeof address === "string") throw new Error("Host server did not start");
  hostOrigin = `http://localhost:${address.port}`;
  await request.post("/api/v1/auth/dev-login", {
    data: { email: "admin@dev.local" },
    maxRedirects: 0,
  });
  const storage = await request.storageState();
  csrf = storage.cookies.find((cookie) => cookie.name === "ar_csrf")?.value ?? "";
  const headers = { "x-csrf-token": csrf, origin: appOrigin };
  const enabled = await request.patch("/api/v1/tenant", {
    headers,
    data: { settings: { features: { widget: true } } },
  });
  expect(enabled.ok(), await enabled.text()).toBeTruthy();
  const catalogue = await request.get("/api/v1/agents");
  const agents = await catalogue.json();
  const assistant = (agents.items ?? agents.data).find(
    (agent: { slug: string }) => agent.slug === "assistant",
  );
  const created = await request.post("/api/v1/channel-integrations", {
    headers,
    data: {
      name: `Portal test ${randomUUID()}`,
      kind: "widget",
      defaultAgentId: assistant.id,
      config: { allowedOrigins: [hostOrigin] },
      credentials: { widgetSecret: signingKey },
    },
  });
  expect(created.status(), await created.text()).toBe(201);
  integrationId = (await created.json()).id;
});

test.afterAll(async ({ request }) => {
  if (integrationId) {
    await request.post("/api/v1/auth/dev-login", {
      data: { email: "admin@dev.local" },
      maxRedirects: 0,
    });
    const storage = await request.storageState();
    csrf = storage.cookies.find((cookie) => cookie.name === "ar_csrf")?.value ?? "";
    const removed = await request.delete(`/api/v1/channel-integrations/${integrationId}`, {
      headers: { "x-csrf-token": csrf, origin: appOrigin },
    });
    expect(removed.ok(), await removed.text()).toBeTruthy();
    expect((await request.get(`/api/v1/channel-integrations/${integrationId}`)).status()).toBe(404);
  }
  if (host) await new Promise<void>((resolve) => host.close(() => resolve()));
});

test("host token opens an accessible embedded conversation and streams a worker reply", async ({
  page,
}) => {
  await page.goto(hostOrigin);
  await page.getByRole("button", { name: "Chat with an agent" }).click();
  const frame = page.frameLocator("iframe");
  await expect(frame.getByRole("heading", { name: "How can I help?" })).toBeVisible({
    timeout: 20_000,
  });
  await frame.getByLabel("Message", { exact: true }).fill("Hello from the embedded portal");
  await frame.getByRole("button", { name: "Send message" }).click();
  await expect(
    frame.getByRole("log").getByText("fake: Hello from the embedded portal", { exact: false }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(frame.getByRole("button", { name: "Stop response" })).toHaveCount(0);
  for (const theme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: theme });
    for (const width of [1280, 375]) {
      await page.setViewportSize({ width, height: 812 });
      await expect(frame.getByLabel("Message", { exact: true })).toBeVisible();
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
      if (process.env.E2E_SCREENSHOT_DIR)
        await page.screenshot({
          path: `${process.env.E2E_SCREENSHOT_DIR}/widget-${theme}-${width}.png`,
        });
    }
  }
  await frame.getByRole("button", { name: "Start a new chat" }).click();
  await expect(frame.getByRole("heading", { name: "How can I help?" })).toBeVisible({
    timeout: 20_000,
  });
  await frame.getByLabel("Message", { exact: true }).press("Escape");
  await expect(page.locator("iframe")).toBeHidden();
  await expect(page.getByRole("button", { name: "Chat with an agent" })).toBeFocused();
});

test("a dropped event stream reloads the same conversation", async ({ page }) => {
  await page.goto(hostOrigin);
  await page.getByRole("button", { name: "Chat with an agent" }).click();
  const frame = page.frameLocator("iframe");
  await expect(frame.getByRole("heading", { name: "How can I help?" })).toBeVisible({
    timeout: 20_000,
  });
  await page.route("**/api/v1/widget/runs/*/events", (route) => route.abort(), { times: 1 });
  await frame.getByLabel("Message", { exact: true }).fill("Recover this portal conversation");
  await frame.getByRole("button", { name: "Send message" }).click();
  await expect(
    frame.getByRole("log").getByText("fake: Recover this portal conversation", { exact: false }),
  ).toBeVisible({ timeout: 30000 });
  await expect(
    frame.getByRole("log").getByText("Recover this portal conversation", { exact: true }),
  ).toHaveCount(1);
});

test("an administrator can configure a portal from the channel form", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as admin@dev.local" }).click();
  await page.goto("/admin/channels");
  await page.getByLabel("Name", { exact: true }).fill("Portal setup review");
  await page.getByLabel("Kind", { exact: true }).selectOption("widget");
  await page.getByLabel("Host signing secret").fill(signingKey);
  await page.getByLabel("Allowed portal origins").fill("https://portal.example/path");
  await page.getByRole("button", { name: "Save channel" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "without a path or wildcard" }),
  ).toBeVisible();
  await page.getByLabel("Allowed portal origins").fill(hostOrigin);
  const response = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/channel-integrations") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Save channel" }).click();
  const created = await response;
  expect(created.ok(), await created.text()).toBeTruthy();
  const id = (await created.json()).id;
  await expect(page.getByRole("heading", { name: "Add chat to your portal" })).toBeVisible();
  await expect(page.locator("pre")).toContainText(`data-integration="${id}"`);
  await expect(page.locator("pre")).not.toContainText(signingKey);
  const cookies = await page.context().cookies();
  const token = cookies.find((cookie) => cookie.name === "ar_csrf")?.value ?? "";
  expect(
    (
      await page.request.delete(`/api/v1/channel-integrations/${id}`, {
        headers: { "x-csrf-token": token, origin: appOrigin },
      })
    ).ok(),
  ).toBeTruthy();
});

test("expired host tokens show a recoverable sign-in error", async ({ page }) => {
  await page.goto(`${hostOrigin}/expired`);
  await page.getByRole("button", { name: "Chat with an agent" }).click();
  const frame = page.frameLocator("iframe");
  await expect(
    frame.getByRole("alert").filter({ hasText: "Your session has expired" }),
  ).toBeVisible();
  await expect(frame.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("the actual frame response refuses an unregistered parent origin", async ({
  page,
  request,
}) => {
  const policy = await request.get(`/widget/${integrationId}`);
  expect(policy.headers()["content-security-policy"]).toBe(`frame-ancestors ${hostOrigin}`);
  await page.goto(hostOrigin.replace("localhost", "127.0.0.1"));
  await page.getByRole("button", { name: "Chat with an agent" }).click();
  await expect(page.locator("iframe")).toBeVisible();
  await expect(
    page.frameLocator("iframe").getByRole("heading", { name: "How can I help?" }),
  ).toHaveCount(0);
});
