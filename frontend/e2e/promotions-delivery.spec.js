import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });

test("a valid coupon plus a delivery zone uses the server price in checkout", async ({ page }) => {
  await page.addInitScript(() => {
    window.open = () => null;
  });

  await page.goto("/product/vfx-resin-clear-1l");
  await page.getByRole("button", { name: /أضف إلى العربة|إضافة إلى العربة/ }).first().click();
  await page.goto("/cart");
  await page.getByLabel("كود الخصم").fill("VFXVALID20");
  await page.getByRole("button", { name: /تطبيق/ }).click();
  await expect(page.locator(".vs-coupon__msg.is-ok")).toBeVisible();

  // Use SPA navigation: coupon state is deliberately in the shared storefront
  // provider, not durable browser storage.
  await page.getByRole("link", { name: "إتمام الطلب" }).click();
  await page.waitForURL(/\/checkout$/);
  await page.getByLabel("الاسم الكامل").fill(`تسعير قبول ${Date.now()}`);
  await page.getByLabel("رقم الهاتف").fill("0591234567");
  await page.getByLabel("العنوان بالتفصيل").fill("رام الله - اختبار تسعير");
  await page.getByLabel("منطقة التوصيل").selectOption("2");
  await page.getByRole("checkbox").check();

  // 120.00 product - 20% fixture coupon + 35.00 Jerusalem delivery = 131.00.
  await expect(page.locator(".vs-summary__row--good")).toContainText("24");
  await expect(page.locator(".vs-summary__row").filter({ hasText: "التوصيل" })).toContainText("35");
  await expect(page.locator(".vs-summary__total")).toContainText("131");

});
