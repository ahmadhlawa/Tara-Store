import { expect, test } from "@playwright/test";

// Isolated API fixtures: no dependency on, or writes to, the local mirror.
test("one tap reaches checkout and mobile RTL controls remain aligned", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body = [];
    if (path.endsWith("/store/settings")) body = { store_name: "TARA", currency_code: "ILS", currency_symbol: "₪", maintenance_mode: false };
    else if (path.endsWith("/cart/price")) {
      const gift = route.request().postDataJSON().packaging_type === "gift";
      body = { lines: [], subtotal: 100, discount: 0, delivery_fee: 0, packaging_type: gift ? "gift" : "normal", packaging_fee: gift ? 7 : 0, total: gift ? 107 : 100 };
    } else if (path.endsWith("/coupons/validate")) {
      if (route.request().postDataJSON().code === "BAD") {
        await route.fulfill({ status: 422, json: { error: { code: "coupon_invalid", message: "الكود غير صالح أو منتهي الصلاحية" } } });
        return;
      }
      body = { code: "SAVE", label: "خصم الاختبار", discount: 10 };
    }
    else if (path.includes("/products")) body = { items: [], total: 0, page: 1, page_size: 24, pages: 0 };
    else if (path.includes("/analytics/")) body = {};
    await route.fulfill({ json: body });
  });
  await page.addInitScript(() => localStorage.setItem("commerce_cart_v1", JSON.stringify([
    { key: "1|", productId: 1, slug: "test", name: "منتج اختبار", unit: 100, qty: 1 },
  ])));
  await page.goto("/ar/shop");
  await page.locator(".vs-header .vs-cartbtn").tap();
  const drawer = page.getByRole("dialog", { name: "عربة التسوّق" });
  await expect(drawer).toBeVisible();
  expect(await page.evaluate(() => document.body.style.overflow)).toBe("hidden");
  await drawer.getByRole("button", { name: "إتمام الطلب", exact: true }).tap();
  await expect(page).toHaveURL(/\/ar\/checkout$/);
  await expect(drawer).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).not.toBe("hidden");
  expect(await page.evaluate(() => document.activeElement?.isConnected)).toBe(true);

  const gift = page.getByRole("checkbox", { name: /تغليف كهدية/ });
  await expect(gift).not.toBeChecked();
  await gift.check();
  // Deliberately differs from the advertised fee: summary must use the server.
  await expect(page.locator(".vs-summary")).toContainText("7 ₪");
  await gift.uncheck();
  await expect(page.locator(".vs-summary")).not.toContainText("تغليف كهدية");
  await page.locator(".vs-coupon-disclosure summary").tap();
  await page.getByRole("textbox", { name: "كود الخصم" }).fill("SAVE");
  await page.getByRole("button", { name: "تطبيق", exact: true }).tap();
  const remove = page.getByRole("button", { name: "إزالة الكوبون" });
  await expect(remove).toBeVisible();

  for (const width of [390, 320, 768, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    const applyBox = await page.getByRole("button", { name: "تطبيق", exact: true }).boundingBox();
    const removeBox = await remove.boundingBox();
    expect(removeBox.y).toBeGreaterThanOrEqual(applyBox.y + applyBox.height);
    expect(Math.abs(removeBox.x - applyBox.x)).toBeLessThan(1);
    expect(Math.abs(removeBox.width - applyBox.width)).toBeLessThan(1);
    const logo = await page.locator(".vs-header .vs-logo").boundingBox();
    const row = await page.locator(".vs-header__row").boundingBox();
    expect(Math.abs(logo.y + logo.height / 2 - row.y - row.height / 2)).toBeLessThan(2);
    expect(Math.abs(logo.x + logo.width / 2 - row.x - row.width / 2)).toBeLessThan(2);
    const giftBox = await page.locator(".vs-gift-packaging").boundingBox();
    expect(giftBox.x).toBeGreaterThanOrEqual(0);
    expect(giftBox.x + giftBox.width).toBeLessThanOrEqual(width);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.setViewportSize({ width: 320, height: 844 });
  await remove.tap();
  await page.getByRole("textbox", { name: "كود الخصم" }).fill("BAD");
  await page.getByRole("button", { name: "تطبيق", exact: true }).tap();
  await expect(page.locator(".vs-coupon__msg.is-bad")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
