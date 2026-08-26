import { expect, test } from "@playwright/test";
import { expectClean, login, MANAGER, watchPage } from "./helpers.js";

const viewports = [
  { width: 320, height: 568 },
  { width: 360, height: 800 },
  { width: 375, height: 812 },
  { width: 390, height: 844 },
  { width: 430, height: 932 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
];

async function authenticate(page) {
  if (process.env.QA_ADMIN_TOKEN) {
    await page.goto("/admin/login");
    await page.evaluate((token) => localStorage.setItem("commerce_admin_auth_v1", JSON.stringify({ token, admin: null })), process.env.QA_ADMIN_TOKEN);
    return;
  }
  await login(page, MANAGER);
}

for (const viewport of viewports) {
  test(`storefront mobile density stays practical at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const runtime = watchPage(page);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const geometry = await page.evaluate(() => {
      const footer = document.querySelector(".vs-footer")?.getBoundingClientRect();
      const productSections = [...document.querySelectorAll("section.vs-section")]
        .filter((section) => section.querySelectorAll(".vs-card").length >= 2)
        .map((section) => ({
          height: section.getBoundingClientRect().height,
          cards: section.querySelectorAll(".vs-card").length,
        }));
      const feed = [...document.querySelectorAll(".vs-grid")]
        .find((grid) => grid.querySelectorAll(":scope > .vs-card").length >= 2);
      const card = feed?.querySelector(":scope > .vs-card")?.getBoundingClientRect();
      const cardImage = feed?.querySelector(":scope > .vs-card .vs-media")?.getBoundingClientRect();
      const packageCard = document.querySelector(".vs-pkg")?.getBoundingClientRect();
      return {
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        documentHeight: document.documentElement.scrollHeight,
        footerHeight: footer?.height,
        footerTop: footer?.top,
        productSections,
        card,
        cardImage,
        packageCard,
      };
    });
    console.log(JSON.stringify({ viewport, geometry }));

    expect(geometry.scrollWidth).toBe(geometry.clientWidth);
    expect(geometry.documentHeight).toBeLessThan(viewport.width === 320 ? 9000 : 7600);
    if (viewport.width <= 430) {
      const grid = await page.locator(".vs-grid:has(> .vs-card:nth-child(2))").first().evaluate((element) => ({
        columns: getComputedStyle(element).gridTemplateColumns.split(" ").length,
        gap: Number.parseFloat(getComputedStyle(element).gap),
      }));
      expect(grid.columns).toBe(2);
      expect(grid.gap).toBeLessThanOrEqual(12);
      expect(geometry.card.width).toBeGreaterThanOrEqual(130);
      expect(geometry.card.height).toBeLessThan(310);
      expect(geometry.cardImage.height / geometry.cardImage.width).toBeLessThanOrEqual(1.1);
    }
    expect(Math.max(...geometry.productSections.map((section) => section.height))).toBeLessThan(2100);
    expect(await page.locator(".vs-footer a").count()).toBeGreaterThan(3);
    expect(await page.locator(".vs-card__link").count()).toBeGreaterThan(0);
    expect(await page.locator(".vs-pkg__link").count()).toBeGreaterThan(0);
    expectClean(runtime);
  });
}

for (const viewport of viewports.filter(({ width }) => width <= 430)) {
  test(`admin dashboard keeps summary and recent orders dense at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const runtime = watchPage(page);
    await authenticate(page);
    await page.goto("/admin");
    await page.waitForLoadState("networkidle");

    const geometry = await page.evaluate(() => {
      const grid = document.querySelector(".admin-dashboard-stats");
      const stat = document.querySelector(".admin-dashboard-stat")?.getBoundingClientRect();
      const orders = document.querySelector(".admin-dashboard-orders-mobile")?.getBoundingClientRect();
      return {
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        columns: grid ? getComputedStyle(grid).gridTemplateColumns.split(" ").length : 0,
        stat,
        orders,
      };
    });
    console.log(JSON.stringify({ viewport, dashboard: geometry }));

    expect(geometry.scrollWidth).toBe(geometry.clientWidth);
    expect(geometry.columns).toBe(2);
    expect(geometry.stat.width).toBeGreaterThanOrEqual(130);
    expect(geometry.stat.height).toBeLessThan(130);
    expect(geometry.orders.height).toBeLessThan(520);
    await expect(page.locator(".admin-dashboard-orders-mobile a").first()).toBeVisible();
    expectClean(runtime);
  });
}

for (const viewport of viewports) {
  test(`admin media library uses a dense usable grid at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const runtime = watchPage(page);
    await authenticate(page);
    await page.goto("/admin/media");
    await page.waitForLoadState("networkidle");

    const geometry = await page.evaluate(() => {
      const grid = document.querySelector(".admin-media-grid");
      const card = grid?.querySelector(":scope > div")?.getBoundingClientRect();
      return {
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        documentHeight: document.documentElement.scrollHeight,
        columns: grid ? getComputedStyle(grid).gridTemplateColumns.split(" ").length : 0,
        card,
      };
    });
    console.log(JSON.stringify({ viewport, geometry }));

    expect(geometry.scrollWidth).toBe(geometry.clientWidth);
    expect(geometry.columns).toBeGreaterThanOrEqual(2);
    expect(geometry.card.width).toBeGreaterThanOrEqual(100);
    expect(geometry.card.height).toBeLessThan(viewport.width <= 430 ? 370 : 360);
    expect(geometry.documentHeight).toBeLessThan(6500);
    await expect(page.getByRole("searchbox")).toBeVisible();
    expect(await page.locator(".admin-media-card__body > button").count()).toBeGreaterThanOrEqual(3);
    expect(await page.locator('input[type="file"]').count()).toBeGreaterThan(0);
    expectClean(runtime);
  });
}

test("media picker remains scrollable and returns the selected image at 320px", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  const runtime = watchPage(page);
  await authenticate(page);
  await page.goto("/admin/products/8");
  await page.waitForLoadState("networkidle");

  await page.getByRole("button", { name: "اختيار من مكتبة الوسائط" }).first().click();
  const picker = page.getByRole("dialog", { name: "مكتبة الوسائط" });
  await expect(picker).toBeVisible();
  const grid = picker.locator(".admin-media-picker-grid");
  await expect(grid).toBeVisible();

  const geometry = await grid.evaluate((element) => {
    const before = element.scrollTop;
    element.scrollTop = element.scrollHeight;
    const gridBox = element.getBoundingClientRect();
    const dialogBox = element.closest('[role="dialog"]').getBoundingClientRect();
    return {
      before,
      after: element.scrollTop,
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
      gridBox,
      dialogBox,
    };
  });
  const selectBox = await picker.getByRole("button", { name: "اختيار" }).boundingBox();
  console.log(JSON.stringify({ picker: geometry, selectBox }));

  expect(geometry.dialogBox.top).toBeGreaterThanOrEqual(0);
  expect(geometry.dialogBox.bottom).toBeLessThanOrEqual(568);
  expect(geometry.scrollHeight).toBeGreaterThan(geometry.clientHeight);
  expect(geometry.after).toBeGreaterThan(geometry.before);
  expect(geometry.gridBox.bottom).toBeLessThanOrEqual(selectBox.y);
  expect(selectBox.y + selectBox.height).toBeLessThanOrEqual(568);

  await grid.locator("button").first().click();
  await picker.getByRole("button", { name: "اختيار" }).click();
  await expect(picker).toBeHidden();
  await expect(page.getByText("صورة رئيسية جديدة")).toBeVisible();
  expectClean(runtime);
});
