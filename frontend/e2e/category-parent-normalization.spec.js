import { expect, test } from "@playwright/test";
import { login, MANAGER } from "./helpers.js";

test("blank category parent serializes as null and persists after refresh", async ({ page }) => {
  const name = `E2E parentless ${Date.now()}`;
  await login(page, MANAGER);
  await page.goto("/admin/categories");
  await page.locator("h1").locator("xpath=../..").getByRole("button").click();
  const editor = page.getByRole("dialog");
  await editor.locator('input:not([type="checkbox"])').first().fill(name);
  const request = page.waitForRequest((entry) =>
    entry.url().includes("/api/v1/admin/categories") && entry.method() === "POST",
  );
  const response = page.waitForResponse((entry) =>
    entry.url().includes("/api/v1/admin/categories") && entry.request().method() === "POST",
  );
  await editor.locator("button").last().click();
  expect(JSON.parse((await request).postData())).toMatchObject({ parent_id: null });
  expect((await response).status()).toBe(201);
  await expect(editor).toHaveCount(0);
  await page.reload();
  const row = page.locator("tr", { hasText: name });
  await expect(row).toHaveCount(1);
  await row.getByRole("button").last().click();
  await page.getByRole("dialog").locator("button").last().click();
  await expect(page.locator("tr", { hasText: name })).toHaveCount(0);
});
