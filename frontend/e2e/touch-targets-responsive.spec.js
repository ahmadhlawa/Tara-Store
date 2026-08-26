import { expect, test } from "@playwright/test";
import { MANAGER, login, watchPage, expectClean } from "./helpers.js";

async function authenticate(page) {
  if (process.env.QA_ADMIN_TOKEN) {
    await page.goto("/admin/login");
    await page.evaluate((token) => localStorage.setItem("commerce_admin_auth_v1", JSON.stringify({ token, admin: null })), process.env.QA_ADMIN_TOKEN);
    return;
  }
  await login(page, MANAGER);
}

const box = (locator) => locator.evaluate((element) => {
  const { width, height } = element.getBoundingClientRect();
  return { width, height };
});

for (const viewport of [{ width: 360, height: 800 }, { width: 375, height: 812 }, { width: 390, height: 844 }, { width: 430, height: 932 }]) test(`important mobile controls keep a 44px hit area at ${viewport.width}`, async ({ page }) => {
  await page.setViewportSize(viewport);
  const runtime = watchPage(page);

  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(700);
  const productCta = page.locator(".vs-card__cta").first();
  const packageCta = page.locator(".vs-pkg__cta").first();
  const publicTargets = { productCta: await box(productCta), packageCta: await box(packageCta) };
  await productCta.click();
  await page.goto("/cart");
  await page.waitForLoadState("networkidle");
  const quantityButtons = page.locator(".vs-qty button");
  const quantity = await box(quantityButtons.first());

  await authenticate(page);
  await page.goto("/admin/products");
  await page.waitForLoadState("networkidle");
  const menu = page.locator('button[aria-controls="admin-navigation"]');
  const tableActions = page.locator("table button");
  const adminTargets = { menu: await box(menu), tableAction: await box(tableActions.first()) };

  await page.goto("/admin/media");
  await page.waitForLoadState("networkidle");
  const mediaActions = page.locator(".admin-media-card__body > button");
  const mediaAction = await box(mediaActions.first());

  await page.goto("/admin/products/8");
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: "اختيار من مكتبة الوسائط" }).first().click();
  const pickerClose = page.getByRole("dialog", { name: "مكتبة الوسائط" }).locator('button[aria-label="إغلاق"]');

  const measurements = {
    ...publicTargets,
    quantity,
    ...adminTargets,
    mediaAction,
    pickerClose: await box(pickerClose),
    clientWidth: await page.evaluate(() => document.documentElement.clientWidth),
    scrollWidth: await page.evaluate(() => document.documentElement.scrollWidth),
  };
  console.log(JSON.stringify(measurements));

  for (const target of ["productCta", "packageCta", "quantity", "menu", "tableAction", "mediaAction", "pickerClose"]) {
    expect(measurements[target].width).toBeGreaterThanOrEqual(43);
    expect(measurements[target].height).toBeGreaterThanOrEqual(43);
  }
  expect(measurements.scrollWidth).toBe(measurements.clientWidth);
  expectClean(runtime);
});
