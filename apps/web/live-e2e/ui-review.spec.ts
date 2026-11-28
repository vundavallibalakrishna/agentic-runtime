import { randomUUID } from "node:crypto";
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { primaryScreens } from "../e2e/support/management-screens";
import messages from "../src/messages/en.json";

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(process.env.E2E_LOGIN_EMAIL ?? "");
  await page.getByLabel("Password", { exact: true }).fill(process.env.E2E_LOGIN_PASSWORD ?? "");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/chat(?:\?|$)/);
  const response = await page.request.get("/api/v1/auth/session");
  expect(response.ok()).toBe(true);
  const session = (await response.json()) as { user: { displayName?: string; email: string } };
  return `${session.user.displayName ?? ""} ${session.user.email}`.trim();
}

async function checkView(page: Page, label: string, expectedErrors: string[] = []) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
  // Next.js announces a route title through its own alert after client navigation.
  // Request errors belong to the app content or notification region.
  const alerts = page
    .getByRole("main")
    .getByRole("alert")
    .or(page.getByRole("dialog").getByRole("alert"))
    .or(page.getByRole("region", { name: "Notifications alt+T", exact: true }).getByRole("alert"));
  const errors = (await alerts.allTextContents()).filter((value) => value.trim());
  expect
    .soft([...errors].sort(), `${label}: visible request errors`)
    .toEqual([...expectedErrors].sort());
  expect
    .soft(
      await page.evaluate(() => {
        const main = document.querySelector("main");
        return (
          document.documentElement.scrollWidth <= window.innerWidth &&
          (main?.id !== "main-content" ||
            document.documentElement.scrollHeight <= window.innerHeight + 1) &&
          Boolean(main) &&
          (main?.scrollWidth ?? 0) <= (main?.clientWidth ?? 0)
        );
      }),
      `${label}: page overflow`,
    )
    .toBe(true);
  expect
    .soft((await new AxeBuilder({ page }).analyze()).violations, `${label}: accessibility`)
    .toEqual([]);
}

async function inspectRun(page: Page, label: string) {
  await expect(
    page.getByRole("heading", { name: "Run trace", exact: true, level: 1 }),
  ).toBeVisible();
  await checkView(page, `${label} activity`);
  const tool = page.getByTestId("tool-call");
  if (await tool.count()) {
    await tool.first().locator("summary").first().click();
    await checkView(page, `${label} recorded tool result`);
    const argumentsSummary = tool.first().getByText("Arguments", { exact: true });
    if (await argumentsSummary.count()) {
      await argumentsSummary.click();
      await checkView(page, `${label} recorded arguments`);
    }
    await page.screenshot({
      path: test.info().outputPath(`tool-${label.replace(/\W+/g, "-")}.png`),
      fullPage: true,
      animations: "disabled",
    });
    await tool.first().locator("summary").first().click();
  }

  const searchBounds = await page
    .getByRole("searchbox", {
      name: "Find activity by name, type, status or reference",
      exact: true,
    })
    .boundingBox();
  expect(searchBounds?.height).toBeGreaterThanOrEqual(36);
  expect(searchBounds?.width).toBeGreaterThanOrEqual(200);
  await page
    .getByRole("searchbox", {
      name: "Find activity by name, type, status or reference",
      exact: true,
    })
    .fill("no matching activity reference");
  await checkView(page, `${label} activity search`);
  await page
    .getByRole("searchbox", {
      name: "Find activity by name, type, status or reference",
      exact: true,
    })
    .fill("");
  await page.getByRole("tab", { name: "Subagents", exact: true }).click();
  await checkView(page, `${label} subagents`);
  await page.getByRole("tab", { name: "Events", exact: true }).click();
  const reading = page.getByRole("button", { name: "Stop loading", exact: true });
  await expect(page.getByRole("searchbox", { name: "Search this event page" })).toBeVisible();
  const events = page.getByRole("region", { name: "Events", exact: true });
  await expect
    .poll(
      async () => (await events.locator("summary").count()) > 0 || (await reading.count()) === 0,
      { timeout: 20_000 },
    )
    .toBe(true);
  // A live stream may stay open; ending this read never cancels the run.
  if (await reading.count()) await reading.click();
  await checkView(page, `${label} events`);
  const eventSummary = page.getByRole("region", { name: "Events", exact: true }).locator("summary");
  if (await eventSummary.count()) {
    await eventSummary.first().click();
    await checkView(page, `${label} event payload`);
    await page.screenshot({
      path: test.info().outputPath(`events-${label.replace(/\W+/g, "-")}.png`),
      fullPage: true,
      animations: "disabled",
    });
  }
  await page
    .getByRole("searchbox", { name: "Search this event page" })
    .fill("no matching event reference");
  await checkView(page, `${label} event search`);
  await page.getByRole("tab", { name: "Graph", exact: true }).click();
  await checkView(page, `${label} graph`);
  await expect(page.getByRole("button", { name: "Zoom In", exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Activity", exact: true }).click();
  await page.screenshot({
    path: test.info().outputPath(`${label.replace(/\W+/g, "-")}.png`),
    fullPage: true,
    animations: "disabled",
  });
}

async function inspectSavedChatDetails(page: Page) {
  const response = await page.request.get("/api/v1/conversations");
  expect(response.ok()).toBe(true);
  const conversations = ((await response.json()) as { items?: { id: string }[] }).items ?? [];
  type Candidate = { conversationId: string; messageId: string };
  let review: Candidate | undefined;
  let sources: Candidate | undefined;
  let grounding: Candidate | undefined;
  let reply: Candidate | undefined;
  let checked = 0;
  for (const conversation of conversations) {
    const response = await page.request.get(
      `/api/v1/conversations/${encodeURIComponent(conversation.id)}`,
    );
    expect(response.ok()).toBe(true);
    const detail = (await response.json()) as {
      messages?: {
        id?: string;
        role?: string;
        isActiveBranch?: boolean;
        content?: { type?: string; rows?: unknown[] }[];
      }[];
    };
    checked++;
    for (const message of detail.messages ?? []) {
      if (
        !message.id ||
        message.isActiveBranch === false ||
        message.role !== "assistant" ||
        !Array.isArray(message.content)
      )
        continue;
      const candidate = { conversationId: conversation.id, messageId: message.id };
      reply ??= candidate;
      if (message.content.some((part) => part?.type === "grounding")) grounding ??= candidate;
      if (message.content.some((part) => part?.type === "citation_ref")) sources ??= candidate;
      if (
        message.content.some(
          (part) =>
            part?.type === "review" &&
            Array.isArray(part.rows) &&
            part.rows.some((row) => row && typeof row === "object" && !Array.isArray(row)),
        )
      )
        review ??= candidate;
    }
  }
  async function open(candidate: Candidate) {
    await page.goto(`/chat?conversation=${encodeURIComponent(candidate.conversationId)}`);
    const message = page.getByTestId(`message-${candidate.messageId}`);
    await expect(message).toBeVisible();
    return message;
  }
  if (review) {
    const message = await open(review);
    await message.getByText(/^Review results · [\d,]+ rows?$/).click();
    const search = message.getByRole("searchbox", { name: "Search review results" });
    await expect(search).toBeVisible();
    await checkView(page, "saved review result");
    await search.fill("no matching review row reference");
    await checkView(page, "saved review result search");
    await search.fill("");
    await page.screenshot({
      path: test.info().outputPath("saved-review-results.png"),
      fullPage: true,
      animations: "disabled",
    });
  }
  test.info().annotations.push({
    type: "review coverage",
    description: review
      ? `Opened a returned saved review part from ${checked} conversations.`
      : `No saved review rows in ${checked} returned conversations. Large-review rendering is unit coverage only.`,
  });
  if (sources) {
    const message = await open(sources);
    const sourceButton = message.getByRole("button", { name: /^[\d,]+ sources?$/ });
    const sourceCount = Number((await sourceButton.innerText()).replace(/[^\d]/g, ""));
    await sourceButton.click();
    const dialog = page.getByRole("dialog", { name: "Sources", exact: true });
    await expect(dialog).toBeVisible();
    await checkView(page, "saved sources");
    if (sourceCount <= 25) {
      await expect(dialog.getByRole("combobox")).toHaveCount(0);
      await expect(dialog.getByRole("button", { name: "Next", exact: true })).toHaveCount(0);
    }
    await page.screenshot({
      path: test.info().outputPath("saved-source-list.png"),
      fullPage: true,
      animations: "disabled",
    });
    expect(await dialog.getByRole("list").getByRole("button").count()).toBeLessThanOrEqual(25);
    await dialog.getByRole("list").getByRole("button").first().click();
    await checkView(page, "saved source passage");
    await page.screenshot({
      path: test.info().outputPath("saved-source-preview.png"),
      fullPage: true,
      animations: "disabled",
    });
    await dialog.getByRole("button", { name: "Back to sources", exact: true }).click();
    await dialog.getByRole("checkbox", { name: "Verified only", exact: true }).check();
    await checkView(page, "saved verified source filter");
    await dialog.getByRole("checkbox", { name: "Verified only", exact: true }).uncheck();
    await dialog.getByRole("searchbox").fill("no matching source reference");
    await checkView(page, "saved source search");
    await dialog.getByRole("button", { name: "Close", exact: true }).click();
  }
  const candidate = grounding ?? reply;
  if (candidate) {
    const message = await open(candidate);
    await message.getByRole("button", { name: "Why", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Grounding details", exact: true });
    await expect(dialog).toBeVisible();
    await checkView(page, "saved grounding details");
    const claim = dialog.locator("summary");
    if (await claim.count()) {
      await claim.first().click();
      await checkView(page, "saved claim payload");
      await dialog
        .getByRole("searchbox", { name: "Search saved claims" })
        .fill("no matching saved claim reference");
      await checkView(page, "saved claim search");
      await dialog.getByRole("searchbox", { name: "Search saved claims" }).fill("");
    }
    await page.screenshot({
      path: test.info().outputPath("saved-grounding.png"),
      fullPage: true,
      animations: "disabled",
    });
    await dialog.getByRole("button", { name: "Close", exact: true }).click();
    await checkView(page, "saved grounding closed");
    await expect(message.getByRole("button", { name: "Why", exact: true })).toBeFocused();
  }
  test.info().annotations.push({
    type: "source coverage",
    description: `Checked ${checked} conversations; saved citation part: ${Boolean(sources)}; saved grounding part: ${Boolean(grounding)}; inspected Why: ${Boolean(candidate)}.`,
  });
}

async function inspectLinkedDetail(page: Page, path: string) {
  const routes: Record<string, { prefix: string; template: string; excluded?: string }> = {
    "/agents": { prefix: "/agents/", template: "/agents/[id]", excluded: "/agents/new" },
    "/knowledge": { prefix: "/knowledge/", template: "/knowledge/[collectionId]" },
    "/documents": {
      prefix: "/documents/",
      template: "/documents/[documentId]",
      excluded: "/documents/compare",
    },
    "/approvals": { prefix: "/approvals/", template: "/approvals/[id]" },
    "/reviews": { prefix: "/reviews/", template: "/reviews/[id]" },
    "/routines": { prefix: "/routines/", template: "/routines/[routineId]" },
    "/connectors": { prefix: "/connectors/", template: "/connectors/[slug]" },
  };
  const route = routes[path];
  if (!route) return;
  const links = await page.getByRole("main").locator(`a[href^="${route.prefix}"]`).all();
  let href: string | undefined;
  for (const link of links) {
    const candidate = await link.getAttribute("href");
    if (
      candidate &&
      candidate !== route.excluded &&
      !candidate.slice(route.prefix.length).includes("/")
    ) {
      href = candidate;
      break;
    }
  }
  if (!href) {
    test.info().annotations.push({
      type: "detail coverage",
      description: `${route.template}: no visible saved-record link; not visually certified.`,
    });
    return;
  }
  async function inspect(target: string, template: string) {
    await page.goto(target);
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
    await checkView(page, template);
    await page.screenshot({
      path: test.info().outputPath(`detail-${template.replace(/\W+/g, "-")}.png`),
      fullPage: true,
      animations: "disabled",
    });
    test.info().annotations.push({
      type: "detail coverage",
      description: `${template}: opened from a genuine saved-record link.`,
    });
  }
  await inspect(href, route.template);
  if (path === "/agents") await inspect(`${href}/evals`, "/agents/[id]/evals");
  if (path === "/knowledge") {
    const source = page.getByRole("main").locator(`a[href="${href}/sources/new"]`);
    if (await source.count())
      await inspect(`${href}/sources/new`, "/knowledge/[collectionId]/sources/new");
  }
  await page.goto(path);
  await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
}

async function inspectEntryRoutes(page: Page) {
  for (const path of ["/forgot-password", "/select-tenant", "/guest"]) {
    await page.goto(path);
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
    await checkView(page, `${path} entry form`);
    await page.screenshot({
      path: test.info().outputPath(`entry-${path.replace(/\W+/g, "-")}.png`),
      fullPage: true,
      animations: "disabled",
    });
    test.info().annotations.push({
      type: "entry coverage",
      description: `${path}: readonly entry form checked; no request/session/reset submitted.`,
    });
  }
  await page.goto("/");
  await expect(page).toHaveURL(/\/chat(?:\?|$)/);
  await expect(page.getByRole("heading", { name: "Chat", level: 1, exact: true })).toBeVisible();
  await checkView(page, "workspace redirect");
  test.info().annotations.push({
    type: "entry coverage",
    description: "/: authenticated workspace redirect reached /chat.",
  });
}

async function inspectPackView(page: Page) {
  const response = await page.request.get("/api/v1/tenant/packs");
  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    items?: { packId: string; enabled: boolean; version?: string }[];
    data?: { packId: string; enabled: boolean; version?: string }[];
  };
  const packs = body.items ?? body.data ?? [];
  for (const pack of packs) {
    await page.goto(`/packs/${encodeURIComponent(pack.packId)}`);
    await expect(page.getByRole("main").getByText(pack.packId, { exact: true })).toBeVisible();
    await expect(
      page.getByRole("main").getByText(pack.enabled ? "Enabled" : "Disabled", { exact: true }),
    ).toBeVisible();
    if (pack.version)
      await expect(page.getByRole("main").getByText(pack.version, { exact: true })).toBeVisible();
    await checkView(page, "installed pack details");
  }
  // An opaque URL is a negative route check, never an inserted pack or a substitute for one.
  const missingId = randomUUID();
  expect(packs.some((pack) => pack.packId === missingId)).toBe(false);
  await page.goto(`/packs/${missingId}`);
  await expect(page.getByText("Pack not found in this workspace", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to chat", exact: true })).toHaveAttribute(
    "href",
    "/chat",
  );
  await checkView(page, "pack not found");
  await page.screenshot({
    path: test.info().outputPath("pack-not-found.png"),
    fullPage: true,
    animations: "disabled",
  });
  test.info().annotations.push({
    type: "pack coverage",
    description: `/packs/[packId]: missing view checked; ${packs.length} installed pack detail views checked. No enable/disable submitted.`,
  });
}

async function inspectRetiredDocumentViews(page: Page) {
  const reference = randomUUID();
  const removedRequests: string[] = [];
  const observe = (request: { url(): string }) => {
    const path = new URL(request.url()).pathname;
    if (/^\/api\/v1\/document-(comparisons|checks|rewrites)/.test(path)) removedRequests.push(path);
  };
  page.on("request", observe);
  try {
    for (const [path, template] of [
      ["/documents/compare", "/documents/compare"],
      [`/documents/compare?comparisonId=${reference}`, "/documents/compare"],
      [`/documents/checks/${reference}`, "/documents/checks/[checkId]"],
      [`/documents/rewrites/${reference}`, "/documents/rewrites/[rewriteId]"],
    ]) {
      await page.goto(path);
      await expect(
        page.getByRole("heading", { name: "Document work", exact: true, level: 1 }),
      ).toBeVisible();
      await expect(
        page.getByRole("link", { name: "Work with documents in chat", exact: true }),
      ).toHaveAttribute("href", "/chat");
      await expect(page.getByRole("button", { name: /Accept all|Reject all/ })).toHaveCount(0);
      await checkView(page, `${template} compatibility guidance`);
      await page.screenshot({
        path: test.info().outputPath(`retired-${template.replace(/\W+/g, "-")}.png`),
        fullPage: true,
        animations: "disabled",
      });
      test.info().annotations.push({
        type: "compatibility coverage",
        description: `${template}: retired-view guidance only; no saved result or API reinstated.`,
      });
    }
    expect(removedRequests).toEqual([]);
  } finally {
    page.off("request", observe);
  }
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1280, 375]) {
    test(`live UI ${theme} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      const accountName = await signIn(page);
      for (const [path, title] of primaryScreens) {
        await test.step(`${path}: ${title}`, async () => {
          await page.goto(path);
          await expect(
            page.getByRole("heading", { name: title, exact: true, level: 1 }),
          ).toBeVisible();
          await expect(page.getByRole("button", { name: accountName, exact: true })).toBeVisible();
          await checkView(page, `${path} ${theme} ${width}`);
          await page.screenshot({
            path: test.info().outputPath(`${path.replace(/\W+/g, "-")}.png`),
            fullPage: true,
            animations: "disabled",
          });
          if (path === "/chat" && width >= 768) {
            const history = page
              .getByRole("navigation", { name: "Conversations", exact: true })
              .getByRole("button");
            if (await history.count()) {
              await history.last().click();
              await checkView(page, `saved chat ${theme} ${width}`);
              const details = page.getByRole("button", { name: "Run details", exact: true });
              if (await details.count()) {
                await details.click();
                await expect(
                  page.getByRole("complementary", { name: "Run details", exact: true }),
                ).toBeVisible();
                await checkView(page, `saved chat run inspector ${theme} ${width}`);
                await page.screenshot({
                  path: test.info().outputPath("chat-run-inspector.png"),
                  fullPage: true,
                  animations: "disabled",
                });
                await details.click();
              }
            }
          }
          if (path === "/chat") await inspectSavedChatDetails(page);
          if (path === "/skills") {
            const open = page.getByRole("link", { name: "Open", exact: true });
            if (await open.count()) {
              await open.first().click();
              const instructions = page.getByRole("textbox", { name: "Instructions", exact: true });
              await expect(instructions).toBeVisible();
              await checkView(page, `skill instructions ${theme} ${width}`);
              const original = await instructions.inputValue();
              const editable = await instructions.isEditable();
              if (editable) await instructions.fill(`${original}\n `);
              await page.getByRole("tab", { name: "Versions", exact: true }).click();
              await checkView(page, `skill history ${theme} ${width}`);
              const version = page.getByRole("button", { name: /^View version / });
              if (await version.count()) {
                await version.first().click();
                await checkView(page, `saved skill version ${theme} ${width}`);
                await page.screenshot({
                  path: test.info().outputPath("skill-version.png"),
                  fullPage: true,
                  animations: "disabled",
                });
                await page
                  .getByRole("dialog")
                  .getByRole("button", { name: "Close", exact: true })
                  .click();
              }
              await page.getByRole("tab", { name: "Where used", exact: true }).click();
              await checkView(page, `skill dependants ${theme} ${width}`);
              await page
                .getByRole("group", { name: "Settings detail", exact: true })
                .getByRole("button", { name: "Advanced", exact: true })
                .click();
              await page.getByRole("tab", { name: "Tools and files", exact: true }).click();
              await checkView(page, `skill resources ${theme} ${width}`);
              await page.screenshot({
                path: test.info().outputPath("skill-resources.png"),
                fullPage: true,
                animations: "disabled",
              });
              const picker = page.getByRole("button", { name: "Required tools", exact: true });
              if (await picker.isEnabled()) {
                await picker.click();
                await checkView(page, `skill tool picker ${theme} ${width}`);
                const dialog = page.getByRole("dialog", { name: "Required tools", exact: true });
                expect(await dialog.getByRole("checkbox").count()).toBeLessThanOrEqual(25);
                await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
              }
              await page
                .getByRole("group", { name: "Settings detail", exact: true })
                .getByRole("button", { name: "Simple", exact: true })
                .click();
              await expect(
                page.getByRole("tab", { name: "Instructions", exact: true }),
              ).toHaveAttribute("aria-selected", "true");
              await expect(instructions).toHaveValue(editable ? `${original}\n ` : original);
              if (editable) await instructions.fill(original);
              await page.screenshot({
                path: test.info().outputPath("skill-editor.png"),
                fullPage: true,
                animations: "disabled",
              });
              await page.getByRole("link", { name: "Back to skills", exact: true }).click();
            }
          }
          if (path === "/runs") {
            const trace = page.getByRole("link", { name: "View trace", exact: true });
            if (await trace.count()) {
              await trace.first().click();
              await inspectRun(page, `run detail ${theme} ${width}`);
              await page.getByRole("link", { name: "Back to runs", exact: true }).click();
            }
          }
          if (path === "/admin/evals") {
            const run = page.getByRole("button", { name: "Run suite", exact: true });
            if (await run.count()) {
              await run.first().click();
              const setup = page.getByRole("dialog", { name: "Run evaluation", exact: true });
              await expect(
                setup.getByRole("button", { name: "Start evaluation", exact: true }),
              ).toBeDisabled();
              await checkView(page, `evaluation setup ${theme} ${width}`);
              await setup.getByRole("button", { name: "Close", exact: true }).click();
            }
            await page.getByRole("tab", { name: "Runs", exact: true }).click();
            await checkView(page, `evaluation history ${theme} ${width}`);
            const results = page.getByRole("button", { name: /^View results for run / });
            if (await results.count()) {
              await results.first().click();
              const inspector = page.getByRole("dialog", {
                name: "Evaluation results",
                exact: true,
              });
              await expect(inspector).toBeVisible();
              await checkView(page, `saved evaluation results ${theme} ${width}`);
              await page.screenshot({
                path: test.info().outputPath("evaluation-results.png"),
                fullPage: true,
                animations: "disabled",
              });
              const caseLink = inspector.getByRole("link", { name: "Open case run", exact: true });
              const caseHref = (await caseLink.count())
                ? await caseLink.first().getAttribute("href")
                : null;
              await inspector.getByRole("searchbox").fill("no matching case reference");
              await checkView(page, `evaluation result filter ${theme} ${width}`);
              await inspector.getByRole("button", { name: "Close", exact: true }).click();
              if (caseHref) {
                await page.goto(caseHref);
                await inspectRun(page, `evaluation case run ${theme} ${width}`);
                await page.goto(path);
              }
            }
            await page.getByRole("tab", { name: "Feedback inbox", exact: true }).click();
            await checkView(page, `evaluation feedback ${theme} ${width}`);
            await page.getByRole("tab", { name: "Suites", exact: true }).click();
          }
          if (path === "/admin/channels") {
            const form = page.getByRole("main").getByRole("complementary");
            for (const kind of ["slack", "teams", "email", "widget"]) {
              await form.getByRole("combobox", { name: "Kind", exact: true }).selectOption(kind);
              await checkView(page, `channel ${kind} setup ${theme} ${width}`);
            }
            await form.getByRole("combobox", { name: "Kind", exact: true }).selectOption("slack");
            await form
              .getByRole("button", { name: "Default agent: Choose existing", exact: true })
              .click();
            const picker = page.getByRole("dialog", { name: "Default agent", exact: true });
            await expect(picker).toBeVisible();
            await checkView(page, `channel agent picker ${theme} ${width}`);
            const choices = picker.getByRole("list").getByRole("button");
            if (await choices.count()) {
              await choices.first().click();
              await checkView(page, `channel agent choice ${theme} ${width}`);
            } else {
              await picker.getByRole("button", { name: "Cancel", exact: true }).click();
            }
            const edit = page
              .getByRole("main")
              .getByRole("button", { name: "Edit setup", exact: true });
            if (await edit.count()) {
              await edit.first().click();
              await checkView(page, `channel edit ${theme} ${width}`);
              await form
                .getByRole("checkbox", { name: "Replace saved credentials", exact: true })
                .check();
              await checkView(page, `channel replacement fields ${theme} ${width}`);
              await form
                .getByRole("checkbox", { name: "Replace saved credentials", exact: true })
                .uncheck();
              await form.getByRole("button", { name: "Cancel edit", exact: true }).click();
            }
          }
          if (path === "/schedules") {
            await page.getByRole("button", { name: /^Agent:/ }).click();
            const picker = page.getByRole("dialog", { name: "Agent", exact: true });
            await expect(picker).toBeVisible();
            await checkView(page, `agent picker ${theme} ${width}`);
            const choices = picker.getByRole("list").getByRole("button");
            if (await choices.count()) {
              await choices.first().click();
              await checkView(page, `selected schedule agent ${theme} ${width}`);
            } else {
              await picker.getByRole("button", { name: "Cancel", exact: true }).click();
            }
          }
          if (path === "/admin/quotas") {
            const form = page.getByRole("main").getByRole("complementary");
            for (const [scope, label] of [
              ["agent", "Agent"],
              ["team", "Team"],
              ["person", "One person"],
            ] as const) {
              await form
                .getByRole("combobox", { name: "Applies to", exact: true })
                .selectOption(scope);
              await form
                .getByRole("button", { name: `${label}: Choose existing`, exact: true })
                .click();
              const picker = page.getByRole("dialog", { name: label, exact: true });
              await expect(picker).toBeVisible();
              await checkView(page, `quota ${scope} picker ${theme} ${width}`);
              const directory = await page.request.get(
                `/api/v1/${scope === "agent" ? "agents" : scope === "person" ? "users" : "teams"}`,
              );
              expect(directory.ok()).toBe(true);
              const directoryPage = (await directory.json()) as { items: unknown[] };
              expect(Array.isArray(directoryPage.items)).toBe(true);
              const choices = picker.getByRole("list").getByRole("button");
              await expect(choices).toHaveCount(Math.min(25, directoryPage.items.length));
              if (directoryPage.items.length) {
                await choices.first().click();
                await checkView(page, `quota ${scope} target ${theme} ${width}`);
              } else {
                await picker.getByRole("button", { name: "Cancel", exact: true }).click();
              }
            }
            await form
              .getByRole("combobox", { name: "Applies to", exact: true })
              .selectOption("tenant");
            await checkView(page, `workspace quota target ${theme} ${width}`);
            await form
              .getByRole("combobox", { name: "What to limit", exact: true })
              .selectOption("cost_micros");
            await form
              .getByRole("textbox", { name: messages.quotas.spendLimit, exact: true })
              .fill("1");
            await expect(
              form.getByText(messages.quotas.limitHelp.cost_micros, { exact: true }),
            ).toBeVisible();
            await checkView(page, `quota spend explanation ${theme} ${width}`);
            await form
              .getByRole("combobox", { name: "What to limit", exact: true })
              .selectOption("model_tokens");
            await form.getByRole("spinbutton", { name: "Limit", exact: true }).fill("10000");
            const edit = page.getByRole("main").getByRole("button", { name: /^Edit quota / });
            if (await edit.count()) {
              await edit.first().click();
              await checkView(page, `quota edit ${theme} ${width}`);
              await form.getByRole("button", { name: "Cancel edit", exact: true }).click();
            }
          }
          await inspectLinkedDetail(page, path);
          const mode = page.getByRole("group", { name: "Settings detail", exact: true });
          if (await mode.count()) {
            await mode.getByRole("button", { name: "Advanced", exact: true }).click();
            await checkView(page, `${path} advanced ${theme} ${width}`);
            await mode.getByRole("button", { name: "Simple", exact: true }).click();
          }
        });
      }
      await inspectEntryRoutes(page);
      await inspectRetiredDocumentViews(page);
      await inspectPackView(page);
    });
  }
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1280, 375]) {
    test(`review detail ${theme} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      await signIn(page);
      const response = await page.request.get("/api/v1/review-items?scope=all");
      expect(response.ok()).toBe(true);
      const body = (await response.json()) as { items: { id: string }[] };
      const first = body.items[0];
      if (first) {
        const detail = await page.request.get(
          `/api/v1/review-items/${encodeURIComponent(first.id)}`,
        );
        expect(detail.ok()).toBe(true);
        const saved = (await detail.json()) as { statementText: string; status: string };
        await page.goto(`/reviews/${encodeURIComponent(first.id)}`);
        await expect(page.getByRole("heading", { name: "Statement", exact: true })).toBeVisible();
        await expect(
          page.getByRole("main").getByText(saved.statementText, { exact: true }),
        ).toBeVisible();
        await expect(page.getByRole("main").getByText(saved.status, { exact: true })).toBeVisible();
        await checkView(page, "saved review detail");
        await page.screenshot({
          path: test.info().outputPath("saved-review.png"),
          fullPage: true,
          animations: "disabled",
        });
      }
      const missingId = randomUUID();
      expect((await page.request.get(`/api/v1/review-items/${missingId}`)).status()).toBe(404);
      await page.goto(`/reviews/${missingId}`);
      await expect(page.getByText("Review not found", { exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "Sign", exact: true })).toHaveCount(0);
      await checkView(page, "review not found");
      await page.screenshot({
        path: test.info().outputPath("review-not-found.png"),
        fullPage: true,
        animations: "disabled",
      });
      await page.getByRole("link", { name: "Back to reviews", exact: true }).click();
      await expect(page).toHaveURL(/\/reviews$/);
      await checkView(page, "return to reviews");
      test.info().annotations.push({
        type: "review coverage",
        description: `/reviews/[id]: missing view and return link checked; ${first ? 1 : 0} saved detail checked from ${body.items.length} returned items. No decision submitted.`,
      });
    });
  }
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1280, 375]) {
    test(`widget unavailable ${theme} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      const id = randomUUID();
      const policyPath = `/api/v1/widget/integrations/${id}`;
      expect((await page.request.get(policyPath)).status()).toBe(404);
      await page.goto(`/widget/${id}`);
      await expect(
        page.getByRole("heading", { name: "Agent chat", exact: true, level: 1 }),
      ).toBeVisible();
      await expect(page.getByRole("main").getByRole("alert")).toHaveText(
        messages.widget.unavailable,
      );
      await expect(page.getByRole("button", { name: "Send message", exact: true })).toHaveCount(0);
      await expect(page.getByRole("textbox")).toHaveCount(0);
      await checkView(page, "widget unavailable", [messages.widget.unavailable]);
      const retried = page.waitForResponse(
        (response) =>
          new URL(response.url()).pathname === policyPath && response.request().method() === "GET",
      );
      await page.getByRole("button", { name: "Try again", exact: true }).click();
      expect((await retried).status()).toBe(404);
      await expect(page.getByRole("main").getByRole("alert")).toHaveText(
        messages.widget.unavailable,
      );
      await checkView(page, "widget unavailable retry", [messages.widget.unavailable]);
      await page.screenshot({
        path: test.info().outputPath("widget-unavailable.png"),
        fullPage: true,
        animations: "disabled",
      });
      test.info().annotations.push({
        type: "widget coverage",
        description:
          "/widget/[integrationId]: real unavailable policy and retry checked anonymously; no integration, host token, session or model result manufactured. Configured embed flow unverified.",
      });
    });
  }
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1280, 375]) {
    test(`guest entry ${theme} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      const writes: string[] = [];
      page.on("request", (request) => {
        if (
          request.method() !== "GET" &&
          new URL(request.url()).pathname.startsWith("/api/v1/auth/guest/")
        )
          writes.push(request.method());
      });
      await page.goto("/guest");
      const requestTab = page.getByRole("tab", { name: "Request a link", exact: true });
      const signInTab = page.getByRole("tab", { name: "Use a link", exact: true });
      await expect(requestTab).toHaveAttribute("aria-selected", "true");
      await expect(page.getByLabel("Email", { exact: true })).toHaveAttribute("type", "email");
      await expect(page.getByLabel("Link token", { exact: true })).toHaveCount(0);
      await checkView(page, "guest link request pane");
      await page.screenshot({
        path: test.info().outputPath("guest-request.png"),
        fullPage: true,
        animations: "disabled",
      });
      await requestTab.focus();
      await page.keyboard.press("ArrowRight");
      await expect(signInTab).toHaveAttribute("aria-selected", "true");
      await expect(page.getByLabel("Email", { exact: true })).toHaveCount(0);
      await expect(page.getByLabel("Link token", { exact: true })).toHaveAttribute(
        "type",
        "password",
      );
      await expect(
        page.getByLabel("Authenticator code (if set up)", { exact: true }),
      ).toHaveAttribute("inputmode", "numeric");
      await checkView(page, "guest token pane");
      await page.screenshot({
        path: test.info().outputPath("guest-token.png"),
        fullPage: true,
        animations: "disabled",
      });
      await signInTab.focus();
      await page.keyboard.press("ArrowLeft");
      await expect(requestTab).toHaveAttribute("aria-selected", "true");
      await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
      expect(writes).toEqual([]);
      const apiReads: string[] = [];
      const track = (request: import("@playwright/test").Request) => {
        if (new URL(request.url()).pathname.startsWith("/api/v1/"))
          apiReads.push(new URL(request.url()).pathname);
      };
      page.on("request", track);
      await page.goto("/guest/portal");
      await expect(
        page.getByRole("heading", { name: messages.guestAccess.contentUnavailable, level: 1 }),
      ).toBeVisible();
      await expect(
        page.getByText(messages.guestAccess.contentHostHelp, { exact: true }),
      ).toBeVisible();
      await expect(page.getByRole("list")).toHaveCount(0);
      await checkView(page, "guest portal unavailable guidance");
      expect(apiReads).toEqual([]);
      await page.screenshot({
        path: test.info().outputPath("guest-portal-unavailable.png"),
        fullPage: true,
        animations: "disabled",
      });
      const back = page.getByRole("link", { name: messages.guestAccess.backToAccess, exact: true });
      await back.focus();
      await page.keyboard.press("Enter");
      await expect(page).toHaveURL(/\/guest$/);
      await expect(page.getByRole("tab", { name: "Request a link", exact: true })).toBeVisible();
      page.off("request", track);
      expect(writes).toEqual([]);
      test.info().annotations.push({
        type: "guest entry coverage",
        description:
          "/guest: request/token panes, keyboard navigation and native controls checked. /guest/portal: unavailable-address guidance and return navigation checked without any content/catalogue API request. No link request, guest session or granted content access submitted.",
      });
    });
  }
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1280, 375]) {
    test(`model registry lists ${theme} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      await signIn(page);
      const [providerResponse, modelResponse] = await Promise.all([
        page.request.get("/api/v1/model-providers"),
        page.request.get("/api/v1/models"),
      ]);
      expect(providerResponse.ok()).toBe(true);
      expect(modelResponse.ok()).toBe(true);
      const providers = (
        (await providerResponse.json()) as {
          items: { id: string; name: string; baseUrl: string }[];
        }
      ).items;
      const models = (
        (await modelResponse.json()) as {
          items: {
            id: string;
            providerId: string;
            name: string;
            upstreamModel: string;
            kind: string;
          }[];
        }
      ).items;
      const writes: string[] = [];
      page.on("request", (request) => {
        if (
          request.method() !== "GET" &&
          /^\/api\/v1\/(models|model-providers|model-aliases)(?:\/|$)/.test(
            new URL(request.url()).pathname,
          )
        )
          writes.push(request.method());
      });
      await page.goto("/admin/models");
      await expect(
        page.getByRole("heading", { name: "Models", exact: true, level: 1 }),
      ).toBeVisible();
      await page
        .getByRole("group", { name: "Settings detail", exact: true })
        .getByRole("button", { name: "Simple", exact: true })
        .click();
      const setupGuide = page.getByText(messages.models.setupOrder, { exact: true });
      if (providers.length) {
        await expect(setupGuide).not.toBeVisible();
        const addProvider = page.locator("summary").filter({ hasText: /^Add a provider$/ });
        await addProvider.click();
        await expect(setupGuide).toBeVisible();
        await addProvider.click();
      } else {
        await expect(setupGuide).toBeVisible();
      }
      await checkView(page, "model registry lists");
      await page.screenshot({
        path: test.info().outputPath("model-registry.png"),
        fullPage: true,
        animations: "disabled",
      });
      const saved = models.find((model) =>
        providers.some((provider) => provider.id === model.providerId),
      );
      if (providers.length) {
        const search = page.getByRole("searchbox", {
          name: "Find a provider, model or model ID",
          exact: true,
        });
        if (saved) {
          const provider = providers.find((item) => item.id === saved.providerId);
          if (!provider) throw new Error("Returned model's provider was not found");
          await search.fill(saved.upstreamModel);
          await page
            .getByRole("combobox", { name: "Model type", exact: true })
            .selectOption(saved.kind);
          const card = page
            .getByRole("list", { name: "Providers and models", exact: true })
            .locator(":scope > li")
            .filter({ has: page.getByRole("heading", { name: provider.name, exact: true }) })
            .filter({ hasText: provider.baseUrl })
            .first();
          const details = card.locator("details");
          if (!(await details.evaluate((element) => (element as HTMLDetailsElement).open)))
            await card.locator("summary").click();
          await expect(
            card
              .getByRole("list", { name: `Models under ${provider.name}`, exact: true })
              .getByText(saved.name, { exact: true }),
          ).toBeVisible();
          await checkView(page, "saved model lookup and kind filter");
          await card.screenshot({
            path: test.info().outputPath("saved-model.png"),
            animations: "disabled",
          });
        }
        await search.fill(`unavailable-${randomUUID()}`);
        await expect(
          page.getByText("No results match these filters.", { exact: true }),
        ).toBeVisible();
        await checkView(page, "model registry no matches");
        await page.getByRole("button", { name: "Clear filters", exact: true }).click();
        await expect(search).toHaveValue("");
        await expect(page.getByRole("combobox", { name: "Model type", exact: true })).toHaveValue(
          "",
        );
      }
      await page
        .getByRole("group", { name: "Settings detail", exact: true })
        .getByRole("button", { name: "Advanced", exact: true })
        .click();
      await expect(page.getByRole("heading", { name: "Other aliases", exact: true })).toBeVisible();
      const aliasSearch = page.getByRole("searchbox", {
        name: "Find an alias or its assigned model",
        exact: true,
      });
      if (await aliasSearch.count()) {
        await aliasSearch.fill(`unavailable-${randomUUID()}`);
        await expect(
          page
            .getByRole("list", { name: "Other aliases", exact: true })
            .getByText("No results match these filters.", { exact: true }),
        ).toBeVisible();
        await aliasSearch.clear();
      }
      await checkView(page, "additional aliases");
      expect(writes).toEqual([]);
      test.info().annotations.push({
        type: "model list coverage",
        description: `Saved catalogue: ${providers.length} providers, ${models.length} models; saved model lookup ${saved ? "checked" : "unavailable"}, empty filters/clear and Advanced aliases checked. No assignment/test/save/delete submitted.`,
      });
    });
  }
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1280, 375]) {
    test(`model pickers ${theme} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      await signIn(page);
      const [modelResponse, aliasResponse] = await Promise.all([
        page.request.get("/api/v1/models"),
        page.request.get("/api/v1/model-aliases"),
      ]);
      expect(modelResponse.ok()).toBe(true);
      expect(aliasResponse.ok()).toBe(true);
      const models = (
        (await modelResponse.json()) as {
          items: {
            id: string;
            name: string;
            kind: string;
            capabilities?: string[];
            upstreamModel: string;
          }[];
        }
      ).items;
      const standard = (
        (await aliasResponse.json()) as {
          standard: {
            alias: string;
            kind: string;
            capability?: string | null;
            aliasId?: string | null;
            modelId?: string | null;
            platform?: boolean;
          }[];
        }
      ).standard;
      const writes: string[] = [];
      const reads: string[] = [];
      page.on("request", (request) => {
        const path = new URL(request.url()).pathname;
        if (!/^\/api\/v1\/(models|model-providers|model-aliases)(?:\/|$)/.test(path)) return;
        if (request.method() === "GET") reads.push(path);
        else writes.push(request.method());
      });
      await page.goto("/admin/models");
      await expect(
        page.getByRole("heading", { name: "Model defaults", exact: true }),
      ).toBeVisible();
      await checkView(page, "closed model choices");
      const use = standard.find((item) =>
        models.some(
          (model) =>
            model.kind === item.kind &&
            (!item.capability || model.capabilities?.includes(item.capability)),
        ),
      );
      let checkedDefault = false;
      if (use) {
        const title = (messages.models.uses as Record<string, { title: string }>)[use.alias]?.title;
        expect(title).toBeTruthy();
        const label = `Model for ${title}`;
        const trigger = page.getByRole("button", { name: new RegExp(`^${label}:`) });
        const before = await trigger.getAttribute("aria-label");
        const readCount = reads.length;
        await trigger.focus();
        await page.keyboard.press("Enter");
        const picker = page.getByRole("dialog", { name: label, exact: true });
        await expect(picker).toBeVisible();
        await expect(
          picker.getByText(messages.models.pickerImmediateHelp, { exact: true }),
        ).toBeVisible();
        const choices = models.filter(
          (model) =>
            model.kind === use.kind &&
            (!use.capability || model.capabilities?.includes(use.capability)),
        );
        await expect(picker.getByRole("listitem")).toHaveCount(Math.min(choices.length, 25));
        await picker.getByRole("searchbox").fill(choices.at(-1)?.upstreamModel ?? "");
        await expect(picker.getByRole("listitem").first()).toBeVisible();
        await checkView(page, "default model picker");
        await page.screenshot({
          path: test.info().outputPath("default-model-picker.png"),
          fullPage: true,
          animations: "disabled",
        });
        await picker.getByRole("button", { name: "Cancel", exact: true }).click();
        await expect(picker).toHaveCount(0);
        await expect(trigger).toBeFocused();
        await expect(trigger).toHaveAttribute("aria-label", before ?? "");
        const assigned = choices.find((model) => model.id === use.modelId);
        if (assigned) {
          await trigger.click();
          await picker.getByRole("searchbox").fill(assigned.id);
          const current = picker.locator('button[aria-current="true"]');
          await expect(current).toHaveCount(1);
          await expect(current).toHaveAttribute(
            "aria-description",
            messages.referencePicker.currentSelection,
          );
          await checkView(page, "current default model selection");
          await page.screenshot({
            path: test.info().outputPath("selected-default-model.png"),
            fullPage: true,
            animations: "disabled",
          });
          await current.click();
          await expect(picker).toHaveCount(0);
          await expect(trigger).toBeFocused();
          await expect(trigger).toHaveAttribute("aria-label", before ?? "");
          expect(writes).toEqual([]);
          test.info().annotations.push({
            type: "current choice",
            description:
              "The real assigned default is marked; choosing it closes without an assignment request.",
          });
        }
        expect(reads.length).toBe(readCount);
        checkedDefault = true;
      }
      await page
        .getByRole("group", { name: "Settings detail", exact: true })
        .getByRole("button", { name: "Advanced", exact: true })
        .click();
      const unmet = standard.find(
        (item) =>
          item.aliasId &&
          !item.platform &&
          item.kind === "chat" &&
          item.capability &&
          !models.some(
            (model) =>
              model.kind === item.kind && model.capabilities?.includes(item.capability ?? ""),
          ),
      );
      let checkedCapabilityEmpty = false;
      if (unmet) {
        const title = (messages.models.uses as Record<string, { title: string }>)[unmet.alias]
          ?.title;
        const optionsButton = page.getByRole("button", {
          name: messages.models.optionsNamed.replace("{name}", title ?? ""),
          exact: true,
        });
        await expect(optionsButton).toBeVisible();
        await optionsButton.click();
        const options = page.getByRole("dialog", {
          name: `Options for ${unmet.alias}`,
          exact: true,
        });
        await expect(options.getByRole("button", { name: /^Model:/ })).toBeDisabled();
        await expect(
          options.getByText(
            (messages.models.needs as Record<string, string>)[unmet.capability ?? ""],
            { exact: true },
          ),
        ).toBeVisible();
        await checkView(page, "unmet model capability options");
        await page.keyboard.press("Escape");
        await expect(options).not.toBeVisible();
        await expect(optionsButton).toBeFocused();
        checkedCapabilityEmpty = true;
      }
      const readCount = reads.length;
      const addAliasTrigger = page.getByRole("button", { name: "Add alias", exact: true });
      await addAliasTrigger.focus();
      await page.keyboard.press("Enter");
      const outer = page.getByRole("dialog", { name: "Add alias", exact: true });
      await expect(outer).toBeVisible();
      let checkedDraft = false;
      if (models.length) {
        await outer
          .getByRole("combobox", { name: "Kind", exact: true })
          .selectOption(models[0].kind);
        const trigger = outer.getByRole("button", { name: /^Model:/ });
        await trigger.click();
        const picker = page.getByRole("dialog", { name: "Model", exact: true });
        await expect(
          picker.getByText(messages.models.pickerDraftHelp, { exact: true }),
        ).toBeVisible();
        await checkView(page, "nested alias model picker");
        test.info().annotations.push({
          type: "nested picker geometry",
          description: JSON.stringify(
            await page.evaluate(() => ({
              viewport: innerHeight,
              document: document.documentElement.scrollHeight,
              documentClient: document.documentElement.clientHeight,
              body: document.body.scrollHeight,
              bodyOverflow: getComputedStyle(document.body).overflow,
              scrollY,
              main: document.querySelector("main")?.clientHeight,
              mainScroll: document.querySelector("main")?.scrollHeight,
              dialogs: [...document.querySelectorAll('[role="dialog"]')].map((node) => ({
                height: node.getBoundingClientRect().height,
                top: node.getBoundingClientRect().top,
              })),
            })),
          ),
        });
        await page.screenshot({
          path: test.info().outputPath("alias-model-picker.png"),
          fullPage: true,
          animations: "disabled",
        });
        const choice = picker.getByRole("list").getByRole("button").first();
        const label = (await choice.innerText()).split("\n")[0] ?? "";
        expect(label).not.toBe("");
        await choice.click();
        await expect(picker).toHaveCount(0);
        await expect(outer).toBeVisible();
        await expect(trigger).toBeFocused();
        await expect(trigger).toContainText(label);
        checkedDraft = true;
      }
      await outer.getByRole("button", { name: "Cancel", exact: true }).click();
      await expect(addAliasTrigger).toBeFocused();
      await expect(outer).toHaveCount(0);
      test.info().annotations.push({
        type: "closed picker geometry",
        description: JSON.stringify(
          await page.evaluate(() => ({
            viewport: innerHeight,
            document: document.documentElement.scrollHeight,
            body: document.body.scrollHeight,
            bodyOverflow: getComputedStyle(document.body).overflow,
            scrollY,
          })),
        ),
      });
      test.info().annotations.push({
        type: "hidden label geometry",
        description: JSON.stringify(
          await page.evaluate(() =>
            [...document.querySelectorAll<HTMLElement>(".sr-only")]
              .map((node) => ({
                tag: node.tagName,
                parent: node.parentElement?.tagName,
                parentFor: node.parentElement?.getAttribute("for"),
                top: node.getBoundingClientRect().top,
                bottom: node.getBoundingClientRect().bottom,
                containingBlock: (node.offsetParent as HTMLElement | null)?.tagName,
                containingClass: (node.offsetParent as HTMLElement | null)?.className,
              }))
              .filter((row) => row.bottom > innerHeight),
          ),
        ),
      });
      expect(reads.length).toBe(readCount);
      expect(writes).toEqual([]);
      test.info().annotations.push({
        type: "model picker coverage",
        description: `${models.length} saved models; default search/cancel/focus ${checkedDefault ? "checked" : "unavailable"}, nested alias draft choice/cancel ${checkedDraft ? "checked" : "unavailable"}, capability-empty options ${checkedCapabilityEmpty ? "checked" : "unavailable"}. No added metadata read, assignment, alias save or model test.`,
      });
    });
  }
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1280, 375]) {
    test(`authoring choices ${theme} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      await signIn(page);
      const writes: string[] = [];
      const reads: string[] = [];
      page.on("request", (request) => {
        const path = new URL(request.url()).pathname;
        if (!/^\/api\/v1\/(agents|routines|model-aliases)(?:\/|:|$)/.test(path)) return;
        (request.method() === "GET" ? reads : writes).push(`${request.method()} ${path}`);
      });
      const coverage: string[] = [];
      for (const screen of [
        { path: "/agents/new", label: messages.agents.modelAlias },
        { path: "/routines", label: messages.routines.agent },
      ]) {
        await page.goto(screen.path);
        if (screen.path === "/agents/new") {
          await page.getByText(messages.agents.createForm, { exact: true }).click();
        }
        await checkView(page, `authoring ${screen.path}`);
        const trigger = page.getByRole("main").getByRole("button", {
          name: new RegExp(`^${screen.label}:`),
        });
        await expect(trigger).toBeVisible();
        if (await trigger.isDisabled()) {
          coverage.push(`${screen.path}: no saved eligible choices`);
          continue;
        }
        const before = await trigger.getAttribute("aria-label");
        const readCount = reads.length;
        await trigger.focus();
        await page.keyboard.press("Enter");
        const picker = page.getByRole("dialog", { name: screen.label, exact: true });
        await expect(picker).toBeVisible();
        const count = await picker.getByRole("listitem").count();
        expect(count).toBeGreaterThan(0);
        expect(count).toBeLessThanOrEqual(25);
        await checkView(page, `authoring picker ${screen.path}`);
        await page.screenshot({
          path: test
            .info()
            .outputPath(
              `${screen.path === "/routines" ? "routine-agent" : "builder-alias"}-picker.png`,
            ),
          fullPage: true,
          animations: "disabled",
        });
        const query = picker.getByRole("searchbox");
        await query.fill(`unmatched-${randomUUID()}`);
        await expect(
          picker.getByText(messages.referencePicker.noMatches, { exact: true }),
        ).toBeVisible();
        await query.fill("");
        await expect(picker.getByRole("listitem")).toHaveCount(count);
        await picker.getByRole("button", { name: "Cancel", exact: true }).click();
        await expect(trigger).toBeFocused();
        await expect(trigger).toHaveAttribute("aria-label", before ?? "");
        expect(reads.length).toBe(readCount);
        await checkView(page, `authoring after cancel ${screen.path}`);
        coverage.push(
          `${screen.path}: ${count} rendered saved choices, search/reset/Cancel/focus checked`,
        );
      }
      expect(writes).toEqual([]);
      test
        .info()
        .annotations.push({ type: "authoring choice coverage", description: coverage.join("; ") });
    });
  }
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1280, 375]) {
    test(`chat choices ${theme} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      await signIn(page);
      const agentPage = await page.request.get("/api/v1/agents");
      expect(agentPage.ok()).toBe(true);
      const agentRecords = (
        (await agentPage.json()) as {
          items: { slug?: string; name?: string; status?: string; disabled?: boolean }[];
        }
      ).items;
      const defaultAgentName =
        agentRecords.find(
          (agent) =>
            agent.slug === "assistant" && agent.status === "published" && agent.disabled === false,
        )?.name || messages.chat.defaultAgent;
      const writes: string[] = [];
      const reads: string[] = [];
      page.on("request", (request) => {
        const path = new URL(request.url()).pathname;
        if (!/^\/api\/v1\/(agents|model-aliases|conversations)(?:\/|:|$)/.test(path)) return;
        (request.method() === "GET" ? reads : writes).push(`${request.method()} ${path}`);
      });
      await checkView(page, "chat before options");
      await page.getByText(messages.chat.chatOptions, { exact: true }).click();
      const main = page.getByRole("main");
      const coverage: string[] = [];
      for (const choice of [
        {
          label: messages.chat.agent,
          reset: messages.chat.useDefaultAgent,
          defaultValue: defaultAgentName,
          help: `${messages.chat.agentChoiceHelp} ${messages.agentAvailability.help}`,
        },
        {
          label: messages.chat.model,
          reset: messages.chat.useAgentModel,
          defaultValue: messages.chat.modelDefault,
          help: messages.chat.modelChoiceHelp,
        },
      ]) {
        const trigger = main.getByRole("button", { name: new RegExp(`^${choice.label}:`) });
        await expect(trigger).toBeEnabled();
        await expect(trigger).toHaveAttribute(
          "aria-label",
          `${choice.label}: ${choice.defaultValue}`,
        );
        const readCount = reads.length;
        await trigger.focus();
        await page.keyboard.press("Enter");
        let picker = page.getByRole("dialog", { name: choice.label, exact: true });
        await expect(picker.getByText(choice.help, { exact: true })).toBeVisible();
        const count = await picker.getByRole("listitem").count();
        expect(count).toBeLessThanOrEqual(25);
        await checkView(page, `chat ${choice.label} choice`);
        await page.screenshot({
          path: test.info().outputPath(`chat-${choice.label.toLowerCase()}-picker.png`),
          fullPage: true,
          animations: "disabled",
        });
        const search = picker.getByRole("searchbox");
        await search.fill(`unmatched-${randomUUID()}`);
        await expect(
          picker.getByText(messages.referencePicker.noMatches, { exact: true }),
        ).toBeVisible();
        await search.fill("");
        await expect(picker.getByRole("listitem")).toHaveCount(count);
        await picker.getByRole("button", { name: "Cancel", exact: true }).click();
        await expect(trigger).toBeFocused();
        if (count) {
          await trigger.click();
          picker = page.getByRole("dialog", { name: choice.label, exact: true });
          await picker.getByRole("listitem").first().getByRole("button").click();
          await expect(picker).not.toBeVisible();
          await trigger.click();
          picker = page.getByRole("dialog", { name: choice.label, exact: true });
          await picker.getByRole("button", { name: choice.reset, exact: true }).click();
          await expect(trigger).toHaveAttribute(
            "aria-label",
            `${choice.label}: ${choice.defaultValue}`,
          );
        }
        expect(reads.length).toBe(readCount);
        coverage.push(
          `${choice.label}: ${count} saved choices, search/reset/Cancel${count ? "/draft selection/default reset" : ""}`,
        );
      }
      await expect(page.getByText(messages.chat.modelSaved, { exact: true })).toHaveCount(0);
      const listed = await page.request.get("/api/v1/conversations");
      expect(listed.ok()).toBe(true);
      const conversations = ((await listed.json()) as { items: { id: string }[] }).items;
      let restored = 0;
      let activeSnapshots = 0;
      for (const item of conversations.slice(0, 2)) {
        const response = await page.request.get(`/api/v1/conversations/${item.id}`);
        expect(response.ok()).toBe(true);
        const data = (await response.json()) as {
          modelAlias?: string | null;
          activeRunId?: string | null;
        };
        if (data.activeRunId) activeSnapshots += 1;
        await page.goto(`/chat?conversation=${encodeURIComponent(item.id)}`);
        await checkView(page, "saved chat loaded");
        await page.getByText(messages.chat.chatOptions, { exact: true }).click();
        const trigger = main.getByRole("button", { name: /^Model:/ });
        await expect(trigger).toBeEnabled();
        await expect(trigger).toHaveAttribute(
          "aria-label",
          `Model: ${data.modelAlias || messages.chat.modelDefault}`,
        );
        await trigger.click();
        const picker = page.getByRole("dialog", { name: messages.chat.model, exact: true });
        await picker.getByRole("button", { name: "Cancel", exact: true }).click();
        await expect(trigger).toBeFocused();
        restored += 1;
      }
      await checkView(page, "chat after choices");
      expect(writes).toEqual([]);
      test.info().annotations.push({
        type: "chat choice coverage",
        description: `${coverage.join("; ")}; ${restored} saved conversation model choices restored from the real API; ${activeSnapshots} snapshots with an active run. No mutation or added picker read.`,
      });
    });
  }
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1280, 375]) {
    test(`chat edit form ${theme} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      await signIn(page);
      const writes: string[] = [];
      page.on("request", (request) => {
        const path = new URL(request.url()).pathname;
        if (/^\/api\/v1\/(conversations|runs)(?:\/|:|$)/.test(path) && request.method() !== "GET")
          writes.push(`${request.method()} ${path}`);
      });
      const list = await page.request.get("/api/v1/conversations");
      expect(list.ok()).toBe(true);
      const records = ((await list.json()) as { items: { id: string }[] }).items;
      type Saved = {
        id: string;
        role: string;
        text?: string;
        status?: string;
        isActiveBranch?: boolean;
        error?: { message?: string };
      };
      let selected: { id: string; messages: Saved[]; message: Saved } | undefined;
      for (const record of records) {
        const response = await page.request.get(`/api/v1/conversations/${record.id}`);
        expect(response.ok()).toBe(true);
        const data = (await response.json()) as { messages: Saved[] };
        const message = data.messages.find(
          (message) =>
            message.role === "user" &&
            message.isActiveBranch !== false &&
            typeof message.text === "string",
        );
        if (message) {
          selected = { id: record.id, messages: data.messages, message };
          break;
        }
      }
      if (!selected) {
        await checkView(page, "chat without a saved editable message");
        test.info().annotations.push({
          type: "edit form coverage",
          description:
            "No saved user message was returned; filled edit form remains unit evidence.",
        });
        return;
      }
      await page.goto(`/chat?conversation=${encodeURIComponent(selected.id)}`);
      const main = page.getByRole("main");
      // Only known saved failed replies are expected alerts, never new request failures.
      const storedFailures = new Set(
        selected.messages
          .filter(
            (message) =>
              message.role === "assistant" &&
              message.status === "failed" &&
              message.isActiveBranch !== false,
          )
          .map(
            (message) =>
              `${messages.chat.failedTitle}${message.error?.message || messages.chat.runFailed}${messages.chat.tryAgain}`,
          ),
      );
      const checkEditView = async (label: string) => {
        const displayed = await main.getByRole("alert").allTextContents();
        await checkView(
          page,
          label,
          displayed.filter((text) => storedFailures.has(text)),
        );
      };
      await checkEditView("saved chat for editing");
      await page.getByTestId("message-scroll").evaluate((node) => {
        node.scrollTop = 0;
      });
      const opener = main
        .getByTestId(`message-${selected.message.id}`)
        .getByRole("button", { name: messages.chat.edit, exact: true });
      await expect(opener).toBeVisible();
      await opener.click();
      const field = main.getByRole("textbox", { name: messages.chat.editMessage, exact: true });
      await expect(field).toBeFocused();
      const original = await field.inputValue();
      expect(original).toBe(selected.message.text);
      await field.fill(`${original}\nUnsubmitted edit preview`);
      await expect(
        main.getByRole("button", { name: messages.chat.saveEdit, exact: true }),
      ).toBeEnabled();
      await checkEditView("saved-message edit form");
      await page.screenshot({
        path: test.info().outputPath("chat-edit-form.png"),
        fullPage: true,
        animations: "disabled",
      });
      await main.getByRole("button", { name: messages.chat.cancelEdit, exact: true }).click();
      await expect(field).toHaveCount(0);
      await expect(opener).toBeFocused();
      await checkEditView("saved-message edit cancelled");
      expect(writes).toEqual([]);
      test.info().annotations.push({
        type: "edit form coverage",
        description:
          "Real saved user text matched the editor; field focus, local editing, Cancel/return focus and responsive accessibility checked without a write. Saved failed replies were matched only against their real API errors.",
      });
    });
  }
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1280, 375]) {
    test(`agent availability ${theme} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      await signIn(page);
      const response = await page.request.get("/api/v1/agents");
      expect(response.ok()).toBe(true);
      const records = (
        (await response.json()) as {
          items: { id: string; status?: string; disabled?: boolean; slug?: string }[];
        }
      ).items;
      const available = records.filter(
        (agent) => agent.status === "published" && agent.disabled === false,
      );
      const writes: string[] = [];
      const reads: string[] = [];
      page.on("request", (request) => {
        const path = new URL(request.url()).pathname;
        if (
          !/^\/api\/v1\/(agents|conversations|routines|channel-integrations)(?:\/|:|$)/.test(path)
        )
          return;
        (request.method() === "GET" ? reads : writes).push(`${request.method()} ${path}`);
      });
      for (const screen of [
        { path: "/chat", label: messages.chat.agent, local: true },
        { path: "/routines", label: messages.routines.agent, local: true },
        { path: "/schedules", label: messages.schedules.agent, local: false },
        { path: "/admin/channels", label: messages.channels.agent, local: false },
      ]) {
        await page.goto(screen.path);
        if (screen.path === "/chat")
          await page.getByText(messages.chat.chatOptions, { exact: true }).click();
        await checkView(page, `agent availability ${screen.path}`);
        const trigger = page
          .getByRole("main")
          .getByRole("button", { name: new RegExp(`^${screen.label}:`) });
        await expect(trigger).toBeVisible();
        if (!available.length && (await trigger.isDisabled())) continue;
        await expect(trigger).toBeEnabled();
        const before = await trigger.getAttribute("aria-label");
        const readCount = reads.length;
        await trigger.click();
        const picker = page.getByRole("dialog", { name: screen.label, exact: true });
        await expect(picker.getByRole("listitem")).toHaveCount(Math.min(available.length, 25));
        await expect(
          picker.getByText(messages.agentAvailability.help, { exact: false }),
        ).toBeVisible();
        await checkView(page, `eligible agents ${screen.path}`);
        if (screen.path === "/routines")
          await page.screenshot({
            path: test.info().outputPath("routine-available-agents.png"),
            fullPage: true,
            animations: "disabled",
          });
        await picker.getByRole("button", { name: "Cancel", exact: true }).click();
        await expect(trigger).toBeFocused();
        await expect(trigger).toHaveAttribute("aria-label", before ?? "");
        if (screen.local) expect(reads.length).toBe(readCount);
      }
      await page.goto(`/chat?agent=unavailable-${randomUUID()}`);
      await expect(
        page.getByText(messages.agentAvailability.requestedUnavailable, { exact: true }),
      ).toBeVisible();
      const newChat = page
        .getByRole("complementary", { name: "Conversations", exact: true })
        .locator(":scope > div")
        .getByRole("button", { name: "New chat", exact: true });
      const defaultAgent = available.find((agent) => agent.slug === "assistant");
      await checkView(page, "unavailable URL agent", [
        `${messages.agentAvailability.requestedUnavailable}${defaultAgent ? messages.chat.useDefaultAgent : ""}`,
      ]);
      const showHistory = page.getByRole("button", {
        name: messages.chat.historyToggle,
        exact: true,
      });
      if (width === 375) await showHistory.click();
      await expect(newChat).toBeDisabled();
      if (width === 375)
        await page.getByRole("button", { name: messages.chat.hideHistory, exact: true }).click();
      if (defaultAgent) {
        await page
          .getByRole("button", { name: messages.chat.useDefaultAgent, exact: true })
          .click();
        await expect(
          page.getByText(messages.agentAvailability.requestedUnavailable, { exact: true }),
        ).toHaveCount(0);
        expect(new URL(page.url()).searchParams.has("agent")).toBe(false);
        if (width === 375) await showHistory.click();
        await expect(newChat).toBeEnabled();
      }
      expect(writes).toEqual([]);
      test.info().annotations.push({
        type: "agent availability coverage",
        description: `${available.length} of ${records.length} real catalogue agents published/enabled; chat, routine, schedule and channel choice counts/Cancel checked. Unavailable URL agent required an explicit choice${defaultAgent ? "/confirmed default" : ""}. No new-work mutation.`,
      });
    });
  }
}
