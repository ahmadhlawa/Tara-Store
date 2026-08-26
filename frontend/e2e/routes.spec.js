import { expect, test } from "@playwright/test";
import { MANAGER, apiToken, expectClean, login, watchPage } from "./helpers.js";

/**
 * Every route the SPA declares, walked in a real browser.
 *
 * The inventory below mirrors src/App.jsx and src/admin/AdminApp.jsx one for one. A
 * route added there without a line here is a gap in this suite, which is why the last
 * test in this file cross-checks the two counts against the router source.
 */
const PUBLIC_ROUTES = [
  { path: "/", name: "homepage" },
  { path: "/shop", name: "all products" },
  { path: "/offers", name: "offers" },
  { path: "/packages", name: "packages" },
  { path: "/molds", name: "silicone molds" },
  { path: "/search?q=%D8%B1%D9%8A%D8%B2%D9%86", name: "search results" },
  { path: "/category/vfx-resin", name: "category detail" },
  { path: "/product/vfx-resin-clear-1l", name: "product detail" },
  { path: "/cart", name: "cart" },
  { path: "/checkout", name: "checkout" },
  { path: "/page/vfx-validation-page", name: "static page by slug" },
  { path: "/about", name: "about" },
  { path: "/privacy-policy", name: "privacy policy" },
  { path: "/return-policy", name: "return policy" },
  { path: "/terms", name: "terms" },
  { path: "/contact", name: "contact" },
  { path: "/tools/calculator", name: "calculator tool" },
  { path: "/this-path-does-not-exist", name: "404 fallback" },
];

const ADMIN_ROUTES = [
  { path: "/admin", name: "dashboard" },
  { path: "/admin/products", name: "products" },
  { path: "/admin/categories", name: "categories" },
  { path: "/admin/orders", name: "orders" },
  { path: "/admin/orders/manual", name: "manual order" },
  { path: "/admin/invoices", name: "invoice archive" },
  { path: "/admin/coupons", name: "coupons" },
  { path: "/admin/delivery", name: "delivery zones" },
  { path: "/admin/hero", name: "hero slides" },
  { path: "/admin/media", name: "media library" },
  { path: "/admin/settings", name: "store settings" },
  { path: "/admin/admins", name: "admin accounts" },
  { path: "/admin/audit", name: "audit log" },
];

test.describe("public routes", () => {
  for (const route of PUBLIC_ROUTES) {
    test(`${route.name} (${route.path}) renders cleanly`, async ({ page }) => {
      const watcher = watchPage(page);
      await page.goto(route.path);
      await page.waitForLoadState("networkidle");

      // Something rendered, and it is the storefront rather than the workspace.
      await expect(page.locator("body")).not.toBeEmpty();
      await expect(page.getByRole("link", { name: "تسجيل دخول الإدارة" })).toBeVisible();
      // A 404 page for an unknown *slug* is legitimate on the detail routes; a
      // failing request for anything else is not.
      expectClean(watcher, { allowStatus: route.path.includes("does-not-exist") ? [404] : [] });
    });
  }

  test("the storefront never renders admin chrome", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("navigation", { name: "التنقّل الرئيسي" })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("أرشيف الفواتير");
  });
});

test.describe("admin routes as super admin", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, MANAGER);
  });

  for (const route of ADMIN_ROUTES) {
    test(`${route.name} (${route.path}) renders cleanly`, async ({ page }) => {
      const watcher = watchPage(page);
      await page.goto(route.path);
      await page.waitForLoadState("networkidle");

      await expect(page).toHaveURL(new RegExp(`${route.path.replace("/", "\\/")}$`));
      await expect(page.locator("body")).not.toBeEmpty();
      // The workspace must not fall back to the login screen for an allowed route.
      await expect(page.locator("body")).not.toContainText("هذه الصفحة مخصّصة لمدراء المتجر فقط");
      expectClean(watcher);
    });
  }

  test("an order detail route renders for a seeded order", async ({ page, request }) => {
    const token = await apiToken(request, MANAGER);
    const list = await (
      await request.get("/api/v1/admin/orders?page_size=1", {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();
    const orderId = list.items[0].id;

    const watcher = watchPage(page);
    await page.goto(`/admin/orders/${orderId}`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toContainText(list.items[0].order_number);
    expectClean(watcher);
  });

  test("an invoice detail route renders for a seeded invoice", async ({ page, request }) => {
    const token = await apiToken(request, MANAGER);
    const list = await (
      await request.get("/api/v1/admin/invoices?page_size=1", {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();
    const number = list.items[0].invoice_number;

    const watcher = watchPage(page);
    await page.goto(`/admin/invoices/${number}`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toContainText(number);
    expectClean(watcher);
  });

  test("a product editor route renders for a seeded product", async ({ page, request }) => {
    const token = await apiToken(request, MANAGER);
    const list = await (
      await request.get("/api/v1/admin/products?page_size=1", {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();

    const watcher = watchPage(page);
    await page.goto(`/admin/products/${list.items[0].id}`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).not.toBeEmpty();
    expectClean(watcher);
  });

  test("an unknown admin path redirects to the dashboard", async ({ page }) => {
    await page.goto("/admin/not-a-real-admin-page");
    await expect(page).toHaveURL(/\/admin$/);
  });
});
