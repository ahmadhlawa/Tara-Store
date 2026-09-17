import { expect, test } from "@playwright/test";

// Uses the local Tara catalog and an existing coupon; never creates an order.
for (const locale of ["ar", "en"]) {
  test(`${locale}: drawer to checkout, coupon and legacy redirect`, async ({ page }) => {
    await page.goto(`/${locale}/product/coconut-candle`, { waitUntil: "domcontentloaded" });
    await page.locator(".vs-pdp").getByRole("button", { name: /أضف إلى العربة|إضافة إلى العربة|Add to cart/ }).click();
    await page.goto(`/${locale}/product/pattern-candle`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "coconut scent", exact: true }).click();
    await page.locator(".vs-pdp").getByRole("button", { name: /أضف إلى العربة|إضافة إلى العربة|Add to cart/ }).click();
    await expect(page.locator(".vs-drawer")).toBeVisible();
    const drawer = page.locator(".vs-drawer");
    await expect(drawer.locator(".vs-cartline")).toHaveCount(2);
    await drawer.getByRole("button", { name: /زيادة الكمية|Increase quantity/ }).first().click();
    await expect(drawer.locator(".vs-qty__value").first()).toHaveText("2");
    await drawer.getByRole("button", { name: /إنقاص الكمية|Decrease quantity/ }).first().click();
    await drawer.locator(".vs-cartline__remove").last().click();
    await expect(drawer.locator(".vs-cartline")).toHaveCount(1);
    await drawer.locator(".vs-drawer__close").click();
    await page.locator(".vs-pdp").getByRole("button", { name: /أضف إلى العربة|إضافة إلى العربة|Add to cart/ }).click();
    await expect(page.locator(".vs-drawer")).toBeVisible();
    await expect(drawer.locator(".vs-cartline")).toHaveCount(2);
    await expect(drawer.getByRole("link", { name: /عرض العربة|View cart/i })).toHaveCount(0);
    const checkout = drawer.locator('a[href$="/checkout"]');
    const box = await checkout.boundingBox();
    expect(box.y + box.height).toBeLessThanOrEqual(page.viewportSize().height);
    await checkout.click();
    await expect(page).toHaveURL(new RegExp(`/${locale}/checkout$`));
    await expect(page.locator(".vs-summary__line")).toHaveCount(2);
    await expect(page.locator(".vs-summary")).toContainText("coconut scent");
    await expect(page.locator(".vs-summary__thumb img")).toHaveCount(2);
    const details = page.locator(".vs-coupon-disclosure");
    await expect(details).not.toHaveAttribute("open");
    await details.locator("summary").click();
    await details.locator("input").fill(process.env.E2E_COUPON || "WELCOM10");
    await details.getByRole("button", { name: /تطبيق|Apply/ }).click();
    await expect(details.locator(".is-ok")).toBeVisible();
    await expect(page.locator(".vs-summary__row--good")).toBeVisible();
    await expect(page.locator(".vs-summary__total")).toContainText("75");
    await details.getByRole("button", { name: /إزالة الكوبون|Remove coupon/ }).click();
    await expect(page.locator(".vs-summary__row--good")).toHaveCount(0);
    await expect(page.locator(".vs-summary__total")).toContainText("85");
    await details.locator("input").fill("INVALID-CART-CHECKOUT");
    await details.getByRole("button", { name: /تطبيق|Apply/ }).click();
    await expect(details.locator(".is-bad")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.locator('input[type="text"]').last().fill("Checkout Review");
    await page.locator('input[type="tel"]').fill("0591234567");
    await page.locator(".vs-checkout select").selectOption("1");
    await page.locator(".vs-checkout textarea").first().fill("Local checkout review address");
    await page.locator('.vs-check--terms input').check();
    await expect(page.locator('.vs-checkout button[type="submit"]')).toBeEnabled();
    await page.goto(`/${locale}/cart?source=bookmark#summary`, { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(new RegExp(`/${locale}/checkout\\?source=bookmark#summary$`));
    await expect(page.locator(".vs-summary__line")).toHaveCount(2);
  });
}
