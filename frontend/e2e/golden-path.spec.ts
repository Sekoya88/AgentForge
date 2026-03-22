/**
 * Full stack: login → create skill → create agent (tool node + attach skill) → sync execute.
 * Requires API + DB + Redis (same as ui-audit authenticated tests).
 */
import { expect, test } from "@playwright/test";

const consoleErrors: string[] = [];

test.beforeEach(async ({ page }) => {
  consoleErrors.length = 0;
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(err.message));
});

test.afterEach(async ({}, testInfo) => {
  if (consoleErrors.length && testInfo.status !== "skipped") {
    await testInfo.attach("console-errors.txt", {
      body: consoleErrors.join("\n"),
      contentType: "text/plain",
    });
  }
});

test.describe("Golden path", () => {
  test.skip(
    !process.env.E2E_EMAIL || !process.env.E2E_PASSWORD,
    "Set E2E_EMAIL and E2E_PASSWORD (CI seeds a user; see .github/workflows/ci.yml).",
  );

  test("skill, agent with tool node, attached skill, sync execution returns uppercased input", async ({
    page,
  }) => {
    const suffix = Date.now();
    const skillName = `gp_skill_${suffix}`;
    const source = `def run(x: str) -> str:\n    return x.upper()\n`;

    await page.goto("/login");
    await page.getByLabel(/terminal id|email/i).fill(process.env.E2E_EMAIL!);
    await page.getByLabel(/access key|password/i).fill(process.env.E2E_PASSWORD!);
    await page.getByRole("button", { name: /initialize session/i }).click();
    await expect(page).toHaveURL(/\/agents/, { timeout: 15_000 });

    await page.goto("/skills/new");
    const skillCard = page.locator(".af-card.max-w-2xl").last();
    await skillCard.locator("input.af-input").first().fill(skillName);
    await skillCard.locator("textarea").fill(source);
    await skillCard.getByRole("button", { name: "Create" }).click();
    await expect(page).toHaveURL(/\/skills$/);

    const graph = {
      nodes: [
        {
          id: "t1",
          type: "tool",
          config: { tool_name: skillName },
        },
      ],
      edges: [],
      entry_point: "t1",
    };

    await page.goto("/agents/new");
    await expect(page.getByRole("checkbox", { name: new RegExp(skillName) })).toBeVisible({
      timeout: 15_000,
    });

    await page.locator("form.af-card textarea").fill(JSON.stringify(graph, null, 2));
    await page.getByRole("checkbox", { name: new RegExp(skillName) }).check();

    await page.locator("form.af-card").getByRole("button", { name: "Create" }).click();
    await expect(page).toHaveURL(/\/agents\/[0-9a-f-]+$/i, { timeout: 20_000 });

    await page.getByLabel(/Stream logs/i).uncheck();
    await page.getByLabel(/User message/i).fill("hello");
    await page.getByRole("button", { name: "Execute" }).click();

    await expect(page.getByText("HELLO")).toBeVisible({ timeout: 45_000 });

    const err = consoleErrors.filter((e) => !e.includes("favicon"));
    expect(err, `console errors: ${err.join("; ")}`).toHaveLength(0);
  });
});
