import { expect, test } from "@playwright/test";
import { DISABLED, EMPLOYEE, MANAGER, apiToken, expectClean, login, watchPage } from "./helpers.js";

test.describe("global technical smoke", () => {
  test("the storefront loads with no console error and no failed request", async ({ page }) => {
    const watcher = watchPage(page);
    await page.goto("/");
    await expect(page.getByRole("link", { name: /الصفحة الرئيسية/ })).toBeVisible();
    await page.waitForLoadState("networkidle");
    expectClean(watcher);
  });

  test("the admin workspace loads clean after signing in", async ({ page }) => {
    const watcher = watchPage(page);
    await login(page, MANAGER);
    await page.waitForLoadState("networkidle");
    expectClean(watcher);
  });

  test("the session survives a reload on a nested admin route", async ({ page }) => {
    await login(page, MANAGER);
    await page.goto("/admin/invoices");
    await page.reload();
    await expect(page).toHaveURL(/\/admin\/invoices$/);
    await expect(page.locator("body")).not.toContainText("تسجيل دخول الإدارة");
  });

  test("a deep public link resolves without a server round trip failure", async ({ page }) => {
    const watcher = watchPage(page);
    await page.goto("/shop");
    await page.waitForLoadState("networkidle");
    expectClean(watcher);
  });

  test("an unauthenticated admin route redirects to the login screen", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/admin/orders");
    await expect(page).toHaveURL(/\/admin\/login$/);
  });

  test("logging out clears access to the workspace", async ({ page }) => {
    await login(page, MANAGER);
    await page.evaluate(() => window.localStorage.clear());
    await page.goto("/admin/orders");
    await expect(page).toHaveURL(/\/admin\/login$/);
  });

  test("a deactivated account cannot sign in and is told so in Arabic", async ({ page }) => {
    await page.goto("/admin/login");
    await page.locator('form input[type="email"]').fill(DISABLED.email);
    await page.locator('form input[type="password"]').fill(DISABLED.password);
    await page.getByRole("button", { name: "دخول" }).click();
    await expect(page.getByText(/البريد الإلكتروني أو كلمة المرور غير صحيحة/)).toBeVisible();
    await expect(page).toHaveURL(/\/admin\/login$/);
  });

  test("an unknown public path renders the storefront 404, not admin chrome", async ({ page }) => {
    await page.goto("/this-route-does-not-exist");
    await expect(page.locator("body")).not.toContainText("لوحة التحكم");
  });

  test("public order tracking is gone from the storefront", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: /تتبع|تتبّع/ })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "تسجيل دخول الإدارة" })).toBeVisible();
  });

  test("the API rejects an anonymous admin call", async ({ request }) => {
    const response = await request.get("/api/v1/admin/orders");
    expect(response.status()).toBe(401);
  });

  test("both acceptance accounts authenticate against the API", async ({ request }) => {
    expect(await apiToken(request, MANAGER)).toBeTruthy();
    expect(await apiToken(request, EMPLOYEE)).toBeTruthy();
  });

  test("the running API is the merged build on the validation database", async ({ request }) => {
    const spec = await (await request.get("/api/v1/openapi.json")).json();
    expect(Object.keys(spec.paths)).toContain("/api/v1/admin/orders/manual");
    expect(Object.keys(spec.paths)).toContain("/api/v1/admin/invoices");

    const products = await (await request.get("/api/v1/products?page_size=100")).json();
    const fixture = products.items.filter((item) => item.slug.startsWith("vfx-"));
    expect(fixture.length).toBeGreaterThan(0);
    // The deliberately inactive fixture product must never reach the storefront.
    expect(products.items.some((item) => item.slug === "vfx-inactive-product")).toBe(false);
  });
});
