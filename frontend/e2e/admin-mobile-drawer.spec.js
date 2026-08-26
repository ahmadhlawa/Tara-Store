import { expect, test } from "@playwright/test";
import { login, MANAGER } from "./helpers.js";

async function authenticate(page) {
  if (process.env.QA_ADMIN_TOKEN) {
    await page.goto("/admin/login");
    await page.evaluate((token) => {
      localStorage.setItem("commerce_admin_auth_v1", JSON.stringify({ token, admin: null }));
    }, process.env.QA_ADMIN_TOKEN);
    return;
  }
  await login(page, MANAGER);
}

test("mobile Admin navigation is an isolated fixed drawer", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await authenticate(page);
  await page.goto("/admin");
  await page.waitForLoadState("networkidle");

  const trigger = page.getByRole("button", { name: "فتح قائمة الإدارة" });
  const before = await page.evaluate(() => ({
    documentHeight: document.documentElement.scrollHeight,
    mainTop: document.querySelector("main").getBoundingClientRect().top,
  }));
  const triggerBounds = await trigger.boundingBox();
  expect(triggerBounds.width).toBeGreaterThanOrEqual(44);
  expect(triggerBounds.height).toBeGreaterThanOrEqual(44);

  await trigger.click();
  const drawer = page.locator("[data-admin-nav-drawer]");
  const after = await page.evaluate(() => {
    const drawerElement = document.querySelector("[data-admin-nav-drawer]");
    const bounds = drawerElement.getBoundingClientRect();
    return {
      documentHeight: document.documentElement.scrollHeight,
      mainTop: document.querySelector("main").getBoundingClientRect().top,
      bodyOverflow: document.body.style.overflow,
      drawer: {
        top: bounds.top,
        right: bounds.right,
        bottom: bounds.bottom,
        height: bounds.height,
        position: getComputedStyle(drawerElement).position,
        overflowY: getComputedStyle(drawerElement).overflowY,
        scrollHeight: drawerElement.scrollHeight,
        clientHeight: drawerElement.clientHeight,
      },
      mainInert: document.querySelector("main").hasAttribute("inert"),
      headerInert: document.querySelector("header").hasAttribute("inert"),
      backgroundHit: document.elementFromPoint(5, 300)?.closest("[data-admin-nav-scrim]") !== null,
    };
  });

  expect(after.documentHeight).toBe(before.documentHeight);
  expect(after.mainTop).toBe(before.mainTop);
  expect(after.bodyOverflow).toBe("hidden");
  expect(after.drawer.position).toBe("fixed");
  expect(after.drawer.top).toBe(0);
  expect(after.drawer.right).toBe(320);
  expect(after.drawer.bottom).toBeLessThanOrEqual(568);
  expect(after.drawer.height).toBeLessThanOrEqual(568);
  expect(after.drawer.overflowY).toBe("auto");
  expect(after.drawer.scrollHeight).toBeGreaterThan(after.drawer.clientHeight);
  expect(after.mainInert).toBe(true);
  expect(after.headerInert).toBe(true);
  expect(after.backgroundHit).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);

  await drawer.evaluate((element) => { element.scrollTop = element.scrollHeight; });
  expect(await drawer.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);

  await page.getByRole("button", { name: "إغلاق قائمة الإدارة" }).click();
  await expect(page.locator("[data-admin-nav-scrim]")).toHaveCount(0);
  expect(await page.evaluate(() => document.body.style.overflow)).toBe("");
});

test("desktop Admin navigation remains the sticky sidebar", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await authenticate(page);
  await page.goto("/admin");
  await page.waitForLoadState("networkidle");

  const drawer = page.locator("[data-admin-nav-drawer]");
  await expect(drawer).toHaveCSS("position", "sticky");
  await expect(drawer).toBeVisible();
  await expect(page.locator("[data-admin-nav-scrim]")).toHaveCount(0);
});
