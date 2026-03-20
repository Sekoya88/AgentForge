/**
 * UI smoke + link coverage. Requires backend on NEXT_PUBLIC_API_URL for auth/API flows.
 * Run: cd frontend && npx playwright test
 * With existing dev server: PLAYWRIGHT_SKIP_WEBSERVER=1 npx playwright test
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

test.describe("Public pages", () => {
  test("landing loads and primary CTAs exist", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("link", { name: /get started/i }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /login/i }).first()).toBeVisible();
  });

  test("login page form", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByLabel(/terminal id|email/i)).toBeVisible();
    await expect(page.getByLabel(/access key|password/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /initialize session|sign/i })).toBeVisible();
  });

  test("register page form", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByRole("button", { name: /create account/i })).toBeVisible();
  });
});

test.describe("Header navigation (unauthenticated)", () => {
  test("top nav links navigate (protected routes redirect to login)", async ({ page }) => {
    await page.goto("/");
    const nav = page.locator("header").locator("nav").first();
    const cases: { label: string; expectPath: "sandbox" | "login" }[] = [
      { label: "Agents", expectPath: "login" },
      { label: "Sandbox", expectPath: "sandbox" },
      { label: "Campaigns", expectPath: "login" },
      { label: "Skills", expectPath: "login" },
      { label: "Finetune", expectPath: "login" },
    ];
    for (const { label, expectPath } of cases) {
      await page.goto("/");
      await nav.getByRole("link", { name: label }).click();
      if (expectPath === "sandbox") {
        await expect(page).toHaveURL(/\/sandbox$/);
      } else {
        await expect(page).toHaveURL(/\/login$/);
      }
    }
  });
});

test.describe("Authenticated flows (needs API + DB)", () => {
  test.skip(
    !process.env.E2E_EMAIL || !process.env.E2E_PASSWORD,
    "Set E2E_EMAIL and E2E_PASSWORD to a valid user (register once manually) to run API-backed tests.",
  );

  test("login then agents list and tool pages load", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/terminal id|email/i).fill(process.env.E2E_EMAIL!);
    await page.getByLabel(/access key|password/i).fill(process.env.E2E_PASSWORD!);
    await page.getByRole("button", { name: /initialize session/i }).click();
    await expect(page).toHaveURL(/\/agents/, { timeout: 15_000 });

    for (const path of ["/agents", "/sandbox", "/campaigns", "/skills", "/finetune"]) {
      await page.goto(path);
      await expect(page.locator("body")).toBeVisible();
      const err = consoleErrors.filter((e) => !e.includes("favicon"));
      expect(err, `console errors on ${path}: ${err.join("; ")}`).toHaveLength(0);
    }

    await page.goto("/agents/new");
    await expect(page.getByRole("button", { name: /create/i })).toBeVisible();

    await page.goto("/skills/new");
    await expect(page.getByRole("button", { name: /create/i })).toBeVisible();

    await page.goto("/finetune/new");
    await expect(page.getByRole("button", { name: /create job/i })).toBeVisible();
  });
});
