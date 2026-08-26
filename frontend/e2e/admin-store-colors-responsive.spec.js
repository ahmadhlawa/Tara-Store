import { expect, test } from "@playwright/test";
import { expectClean, login, MANAGER, watchPage } from "./helpers.js";

const viewports = [
  { width: 320, height: 568 },
  { width: 360, height: 800 },
  { width: 390, height: 844 },
  { width: 430, height: 932 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
];

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

for (const viewport of viewports) {
  test(`Store Colors editor and preview remain usable at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const runtime = watchPage(page);
    await authenticate(page);
    await page.goto("/admin/store-colors");
    await page.waitForLoadState("networkidle");

    const preview = page.locator(".store-theme-preview");
    const previewSection = preview.locator("..");
    const layout = previewSection.locator("..");
    const editor = layout.locator(":scope > div").first();
    const save = page.getByRole("button", { name: "حفظ التغييرات" });
    const reset = page.getByRole("button", { name: "استعادة الألوان الافتراضية" });

    const [layoutBox, editorBox, previewBox, saveBox, resetBox] = await Promise.all([
      layout.boundingBox(), editor.boundingBox(), previewSection.boundingBox(), save.boundingBox(), reset.boundingBox(),
    ]);
    const documentGeometry = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
    }));
    console.log(JSON.stringify({ viewport, documentGeometry, layoutBox, editorBox, previewBox, saveBox, resetBox }));

    expect(documentGeometry.scrollWidth).toBe(documentGeometry.clientWidth);
    expect(documentGeometry.bodyScrollWidth).toBe(documentGeometry.clientWidth);
    for (const actionBox of [saveBox, resetBox]) {
      expect(actionBox.x).toBeGreaterThanOrEqual(0);
      expect(actionBox.x + actionBox.width).toBeLessThanOrEqual(viewport.width);
    }

    if (viewport.width <= 430) {
      expect(editorBox.width).toBeGreaterThanOrEqual(layoutBox.width - 1);
      expect(previewBox.width).toBeGreaterThanOrEqual(layoutBox.width - 1);
      expect(previewBox.y).toBeGreaterThanOrEqual(editorBox.y + editorBox.height + 15);

      const firstHex = page.getByRole("textbox", { name: "اللون الرئيسي", exact: true });
      expect((await firstHex.boundingBox()).width).toBeGreaterThanOrEqual(120);
      await page.getByRole("checkbox", { name: "استخدام لون مخصص للأزرار الرئيسية" }).check();
      expect((await page.getByRole("textbox", { name: "لون الزر", exact: true }).boundingBox()).width).toBeGreaterThanOrEqual(120);
    } else {
      expect(Math.abs(editorBox.y - previewBox.y)).toBeLessThanOrEqual(1);
      expect(previewBox.width).toBeGreaterThanOrEqual(280);
    }

    const navBackground = page.getByRole("textbox", { name: "خلفية شريط التنقل", exact: true });
    const navText = page.getByRole("textbox", { name: "نص شريط التنقل", exact: true });
    await navBackground.fill("#123456");
    await navText.fill("#123456");
    await expect(preview.locator(":scope > div").nth(1)).toHaveCSS("background-color", "rgb(18, 52, 86)");
    const warning = page.getByRole("status").filter({ hasText: "شريط التنقل" }).first();
    await expect(warning).toBeVisible();
    const warningGeometry = await warning.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      whiteSpace: getComputedStyle(element).whiteSpace,
    }));
    expect(warningGeometry.scrollWidth).toBe(warningGeometry.clientWidth);
    expect(warningGeometry.whiteSpace).toBe("normal");

    expectClean(runtime);
  });
}
