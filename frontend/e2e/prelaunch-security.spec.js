import { expect, test } from "@playwright/test";
import { EMPLOYEE, MANAGER, apiToken, login } from "./helpers.js";

test.beforeEach(async ({ page }) => {
  // Functional checks do not depend on external font service availability.
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());
});

test("Admin password confirmation blocks mismatch and supports password replacement", async ({ page, request }) => {
  await login(page, MANAGER);
  await page.goto("/admin/admins");
  await page.getByRole("button", { name: "حساب جديد" }).click();
  const dialog = page.getByRole("dialog");
  const email = `sanitation-${Date.now()}@example.com`;
  await dialog.getByLabel("البريد الإلكتروني", { exact: true }).fill(email);
  await dialog.getByLabel("الاسم الكامل", { exact: true }).fill("Disposable Admin");
  await dialog.getByLabel("كلمة المرور", { exact: true }).fill("DisposableOnly!42");
  await dialog.getByLabel("تأكيد كلمة المرور", { exact: true }).fill("MismatchOnly!42");
  await dialog.getByRole("button", { name: "حفظ", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("غير متطابقين");
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("تأكيد كلمة المرور", { exact: true }).fill("DisposableOnly!42");
  const created = page.waitForResponse((response) => response.url().includes("/admin/admins") && response.request().method() === "POST");
  await dialog.getByRole("button", { name: "حفظ", exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  expect(response.request().postDataJSON()).not.toHaveProperty("confirm_password");
  const account = await response.json();
  const token = await apiToken(request, MANAGER);
  try {
    await page.locator("tr", { hasText: email }).getByRole("button", { name: "تعديل" }).click();
    await dialog.getByLabel("كلمة المرور الجديدة", { exact: true }).fill("ReplacementOnly!42");
    await dialog.getByLabel("تأكيد كلمة المرور الجديدة", { exact: true }).fill("ReplacementOnly!42");
    await dialog.getByRole("button", { name: "حفظ", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    const valid = await request.post("/api/v1/auth/login", { data: { email, password: "ReplacementOnly!42" } });
    expect(valid.status()).toBe(200);
    const old = await request.post("/api/v1/auth/login", { data: { email, password: "DisposableOnly!42" } });
    expect(old.status()).toBe(401);
  } finally {
    expect((await request.delete(`/api/v1/admin/admins/${account.id}`, { headers: { Authorization: `Bearer ${token}` } })).status()).toBe(200);
  }
});

test("Admin 401/403 boundaries and inert SEO markup hold in the browser", async ({ page, request }) => {
  expect((await request.get("/api/v1/admin/dashboard")).status()).toBe(401);
  const token = await apiToken(request, EMPLOYEE);
  expect((await request.get("/api/v1/admin/admins", { headers: { Authorization: `Bearer ${token}` } })).status()).toBe(403);
  await login(page, MANAGER);
  const result = await page.evaluate(async () => {
    window.__seoExecuted = false;
    const { automaticSeo } = await import("/src/admin/seo.js");
    const seo = automaticSeo({ title: "Safe", description: '<img src="missing-seo-image" onerror="window.__seoExecuted=true"><b>Safe description</b>' });
    await new Promise((resolve) => setTimeout(resolve, 200));
    return { description: seo.seo_description, executed: window.__seoExecuted };
  });
  expect(result).toEqual({ description: "Safe description", executed: false });
});

for (const width of [390, 768, 1440]) {
  test(`drawer/checkout coupon remains usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1024 });
    await page.goto("/ar/product/vfx-resin-clear-1l", { waitUntil: "domcontentloaded" });
    await page.locator(".vs-pdp").getByRole("button", { name: /أضف إلى العربة|إضافة إلى العربة/ }).click();
    const drawer = page.locator(".vs-drawer");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByRole("link", { name: /عرض العربة/ })).toHaveCount(0);
    const checkout = drawer.locator('a[href$="/checkout"]');
    await expect(checkout).toBeInViewport();
    await checkout.click();
    await expect(page.locator(".vs-summary__line")).toHaveCount(1);
    await expect(page.locator(".vs-summary__thumb img")).toHaveCount(1);
    const coupon = page.locator(".vs-coupon-disclosure");
    await coupon.locator("summary").click();
    await coupon.locator("input").fill("VFXVALID20");
    await coupon.getByRole("button", { name: "تطبيق" }).click();
    await expect(coupon.locator(".is-ok")).toBeVisible();
    await coupon.getByRole("button", { name: "إزالة الكوبون" }).click();
    await coupon.locator("input").fill("NO-SUCH-PRELAUNCH-COUPON");
    await coupon.getByRole("button", { name: "تطبيق" }).click();
    await expect(coupon.locator(".is-bad")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.goto("/en/cart?source=prelaunch#review");
    await expect(page).toHaveURL(/\/en\/checkout\?source=prelaunch#review$/);
  });
}
