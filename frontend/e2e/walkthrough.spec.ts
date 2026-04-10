import { expect, test } from "@playwright/test";

test.describe("Walkthrough page", () => {
  test("renders try these flows heading", async ({ page }) => {
    await page.goto("/walkthrough");
    await expect(page.getByRole("heading", { name: /try these flows/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /RAG support agent/i })).toBeVisible();
  });
});
