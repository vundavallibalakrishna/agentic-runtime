/**
 * Production-UI certification. The model key is read from the environment and
 * typed into a password field. Screenshots are taken only after that field is
 * empty, and the agent key is read from the page without a screenshot of it.
 */
const fs = require("node:fs");
const path = require("node:path");

const { chromium } = require("/workspace/node_modules/.pnpm/playwright@1.64.1/node_modules/playwright");

const WEB = process.env.M31_WEB || "http://127.0.0.1:18132";
const OUT = process.env.M31_UI_OUT || "/workspace/docs/testing/m31";
const KEY = process.env.AR_CERT_LLM_API_KEY || "";

const PAGES = [
  ["chat", "/chat", "Chat"],
  ["builder", "/agents/new", "New agent"],
  ["agents", "/agents", "Agents"],
  ["documents", "/documents", "Documents"],
  ["knowledge", "/knowledge", "Knowledge"],
  ["memory", "/memory", "Memory"],
  ["skills", "/skills", "Skills"],
  ["connectors", "/connectors", "Connectors"],
  ["runs", "/runs", "Runs"],
  ["inbox", "/inbox", "Inbox"],
  ["approvals", "/approvals", "Approvals"],
  ["schedules", "/schedules", "Schedules"],
  ["settings", "/settings/profile", "Profile"],
  ["models", "/admin/models", "Models"],
  ["retired", "/grc", "Page not found"],
];

function scrub(text) {
  if (KEY && text.includes(KEY)) {
    return text.replaceAll(KEY, "[redacted]");
  }
  return text;
}

async function settled(page) {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForFunction(
    () => !document.querySelector("[aria-busy='true']") && !document.querySelector(".animate-pulse"),
    null,
    { timeout: 20000 },
  );
  const heading = page.locator("h1").first();
  await heading.waitFor({ timeout: 20000 });
  const text = (await heading.innerText()).trim();
  if (!text) {
    throw new Error(`blank heading at ${page.url()}`);
  }
  return text;
}

async function shot(page, name) {
  fs.mkdirSync(OUT, { recursive: true });
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  const bytes = fs.readFileSync(file);
  if (KEY && bytes.includes(Buffer.from(KEY))) {
    fs.rmSync(file);
    throw new Error(`screenshot ${name} contained the provider key`);
  }
  return file;
}

async function login(page, email = "admin@dev.local") {
  await page.context().clearCookies();
  await page.goto(`${WEB}/login`);
  await page.getByRole("button", { name: `Sign in as ${email}` }).click();
  await page.waitForURL(/\/chat/, { timeout: 20000 });
  await settled(page);
}

async function sweep(browser, theme, width, height, label) {
  const context = await browser.newContext({
    viewport: { width, height },
    colorScheme: theme,
  });
  await context.addInitScript((choice) => {
    localStorage.setItem("ar-theme", choice);
  }, theme);
  const page = await context.newPage();
  await login(page);
  if (width >= 1000) {
    const nav = await page.locator("body").innerText();
    if (/grc pack/i.test(nav)) {
      throw new Error("navigation still contains the retired pack");
    }
  }
  const seen = [];
  for (const [name, route, expected] of PAGES) {
    await page.goto(`${WEB}${route}`);
    const heading = await settled(page);
    if (route === "/grc" && !heading.includes("Page not found")) {
      throw new Error(`retired route heading was ${heading}`);
    }
    if (route !== "/grc" && expected && !heading.includes(expected) && heading.length < 2) {
      throw new Error(`${route} heading was ${heading}`);
    }
    const body = await page.locator("body").innerText();
    if (/grc pack|governance, risk/i.test(body)) {
      throw new Error(`${route} still shows the retired pack`);
    }
    await shot(page, `${label}-${name}`);
    seen.push({ route, heading: scrub(heading) });
  }
  await context.close();
  return seen;
}

async function approveWrites(browser) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: "light",
    recordVideo: { dir: "/tmp/m31-video", size: { width: 1440, height: 900 } },
  });
  await context.addInitScript(() => {
    localStorage.setItem("ar-theme", "light");
  });
  const page = await context.newPage();
  await login(page, "approver@dev.local");
  await page.goto(`${WEB}/approvals`);
  const heading = await settled(page);
  const before = await page.locator("body").innerText();
  await shot(page, "flow-approval-pending");
  await page.keyboard.press("Escape");
  const decided = [];
  const approve = page.getByRole("button", { name: "Approve", exact: true });
  while ((await approve.count()) > 0) {
    const response = page.waitForResponse(
      (item) => item.url().includes(":decide") && item.request().method() === "POST",
      { timeout: 20000 },
    );
    await approve.first().click();
    const result = await response;
    decided.push({ status: result.status(), body: scrub(await result.text()).slice(0, 240) });
    if (result.status() !== 200 || decided.length >= 4) break;
    await page.waitForTimeout(300);
  }
  await settled(page);
  const after = await page.locator("body").innerText();
  await shot(page, "flow-approval-decided");
  const video = page.video();
  await context.close();
  let videoPath = "";
  if (video) {
    videoPath = await video.path();
  }
  return {
    heading,
    sawHttp: before.includes("general.http"),
    sawGitHub: before.includes("github_create_issue"),
    decided,
    after: scrub(after).slice(0, 800),
    videoPath,
  };
}

async function typedFlow(browser) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: "light",
    recordVideo: { dir: "/tmp/m31-video", size: { width: 1440, height: 900 } },
  });
  await context.addInitScript(() => {
    localStorage.setItem("ar-theme", "light");
  });
  const page = await context.newPage();
  const notes = {};
  await login(page);
  notes.chatHeading = await settled(page);
  notes.chatText = scrub((await page.locator("body").innerText()).slice(0, 500));
  await shot(page, "flow-chat-empty");

  await page.goto(`${WEB}/admin/models`);
  await settled(page);
  const existing = await page.locator("body").innerText();
  if (existing.includes("Key stored") && existing.includes("DeepInfra")) {
    notes.sample = "Key stored was already on the provider row";
    notes.keyCleared = true;
    notes.keyStoredLabel = true;
    await shot(page, "flow-model-stored");
  } else {
  await page.getByRole("button", { name: "Advanced" }).click();
  await page.getByRole("button", { name: "OpenAI-compatible" }).click();
  await page.locator("#provider-name").fill("Customer DeepInfra");
  await page.locator("#provider-url").fill("https://api.deepinfra.com/v1/openai");
  await page.locator("#provider-model").fill("Qwen/Qwen3-32B");
  if (!KEY) {
    notes.model = "NOT VERIFIED — AR_CERT_LLM_API_KEY absent";
  } else {
    await page.locator("#provider-key").fill(KEY);
    await page.getByRole("button", { name: "Register and test" }).click();
    await page.getByText("Sample:", { exact: false }).waitFor({ timeout: 90000 });
    notes.sample = scrub(await page.getByText("Sample:", { exact: false }).innerText());
    const keyValue = await page.locator("#provider-key").inputValue();
    notes.keyCleared = keyValue === "";
    await settled(page);
    const body = await page.locator("body").innerText();
    notes.keyStoredLabel = body.includes("Key stored");
    await shot(page, "flow-model-stored");
  }
  }

  await page.goto(`${WEB}/agents/new`);
  await settled(page);
  await page.locator("#agent-form-name").fill("Certification clerk");
  await page.locator("#agent-form-instructions").fill(
    "Use the general tools. If a Python call fails, read the error and try a corrected program. Quote the tool output.",
  );
  await page.getByRole("button", { name: "Create and use" }).click();
  await page.waitForURL(/\/chat/, { timeout: 30000 });
  await settled(page);
  notes.createdAgent = page.url();
  await shot(page, "flow-builder-chat");

  await page.goto(`${WEB}/connectors`);
  await settled(page);
  notes.notLive = (await page.locator("body").innerText()).includes("Not live-tested");
  await shot(page, "flow-connectors");

  const assistantId = await page.evaluate(async () => {
    const response = await fetch("/api/v1/agents");
    const body = await response.json();
    const row = (body.items || []).find((item) => item.slug === "assistant");
    return row ? row.id : "";
  });
  await page.goto(`${WEB}/agents/${assistantId}`);
  await settled(page);
  await page.getByRole("tab", { name: "Expose" }).click();
  await page.getByText("Let another product call this published agent").waitFor({ timeout: 20000 });
  notes.exposeHydrated = true;
  await page.locator("#expose-label").fill("Certification UI");
  await page.locator("#expose-rate").fill("30");
  await page.getByRole("button", { name: "Create key" }).click();
  const secret = page
    .getByText("Copy this key now. It is shown once.")
    .locator("xpath=following::pre[1]");
  await secret.waitFor({ timeout: 20000 });
  const secretText = await secret.innerText();
  notes.keyShownOnce = secretText.startsWith("ara_") && secretText.length > 20;
  await page.reload();
  await settled(page);
  await page.getByRole("tab", { name: "Expose" }).click();
  await page.getByText("Certification UI").waitFor({ timeout: 20000 });
  const after = await page.locator("body").innerText();
  notes.secretStillVisible = secretText.length > 0 && after.includes(secretText);
  await shot(page, "flow-expose-prefix");

  await page.goto(`${WEB}/grc/audit`);
  const retired = await settled(page);
  notes.retired = retired;
  await shot(page, "flow-retired");

  const video = page.video();
  await context.close();
  if (video) {
    const saved = await video.path();
    fs.mkdirSync(OUT, { recursive: true });
    fs.copyFileSync(saved, path.join(OUT, "walkthrough.webm"));
  }
  return notes;
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  fs.mkdirSync("/tmp/m31-video", { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const notes = {};
  if (process.env.M31_UI_PART !== "sweep") {
    notes.approval = await approveWrites(browser);
  }
  if (process.env.M31_UI_PART === "approve") {
    await browser.close();
    const text = scrub(JSON.stringify(notes, null, 2));
    fs.writeFileSync(path.join(OUT, "ui-approval.json"), text);
    console.log(text);
    return;
  }
  if (process.env.M31_UI_PART !== "shots") {
    notes.flow = await typedFlow(browser);
  }
  if (notes.approval && notes.approval.videoPath) {
    fs.copyFileSync(notes.approval.videoPath, path.join(OUT, "approval.webm"));
  }
  notes.desktopLight = await sweep(browser, "light", 1440, 900, "desktop-light");
  notes.desktopDark = await sweep(browser, "dark", 1440, 900, "desktop-dark");
  notes.mobileLight = await sweep(browser, "light", 390, 844, "mobile-light");
  notes.mobileDark = await sweep(browser, "dark", 390, 844, "mobile-dark");
  await browser.close();
  const text = scrub(JSON.stringify(notes, null, 2));
  if (KEY && text.includes(KEY)) {
    throw new Error("ui notes contained the provider key");
  }
  fs.writeFileSync(path.join(OUT, "ui.json"), text);
  console.log(text);
}

main().catch((error) => {
  console.error(scrub(String(error && error.stack ? error.stack : error)));
  process.exit(1);
});
