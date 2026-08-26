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

async function usePackageSnapshotFixture(page) {
  await page.route("**/api/v1/admin/orders/1", async (route) => {
    const response = await route.fetch();
    const order = await response.json();
    order.items[0] = {
      ...order.items[0],
      product_name: "باقة اختبار طويلة الاسم",
      package_components: [
        { id: 9001, product_name: "مكوّن الباقة الأول", variant_description: "لون ليلكي", total_quantity: 2 },
        { id: 9002, product_name: "مكوّن الباقة الثاني", variant_description: null, total_quantity: 1 },
      ],
    };
    await route.fulfill({ response, json: order });
  });
}

for (const viewport of viewports) {
  test(`order items stay page-contained at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const runtime = watchPage(page);
    await authenticate(page);
    await usePackageSnapshotFixture(page);
    await page.goto("/admin/orders/1");
    await page.waitForLoadState("networkidle");

    const section = page.getByRole("heading", { name: "أصناف الطلب" }).locator("..");
    const table = section.locator("table");
    const wrapper = table.locator("..");
    const snapshot = section.getByText(/^محتويات الباقة وقت الطلب:/).locator("..");
    const backAction = page.getByRole("button", { name: "رجوع" });

    const geometry = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
    }));
    expect(geometry.scrollWidth).toBe(geometry.clientWidth);
    expect(geometry.bodyScrollWidth).toBe(geometry.clientWidth);

    const [sectionBox, wrapperBox, tableBox, snapshotBox, actionBox] = await Promise.all([
      section.boundingBox(), wrapper.boundingBox(), table.boundingBox(), snapshot.boundingBox(), backAction.boundingBox(),
    ]);
    console.log(JSON.stringify({ viewport, geometry, wrapperBox, tableBox, snapshotBox }));
    expect(wrapperBox.x).toBeGreaterThanOrEqual(sectionBox.x);
    expect(wrapperBox.x + wrapperBox.width).toBeLessThanOrEqual(sectionBox.x + sectionBox.width);
    expect(snapshotBox.x).toBeGreaterThanOrEqual(sectionBox.x);
    expect(snapshotBox.x + snapshotBox.width).toBeLessThanOrEqual(sectionBox.x + sectionBox.width);
    expect(snapshotBox.y).toBeGreaterThan(tableBox.y + tableBox.height);
    expect(actionBox.x).toBeGreaterThanOrEqual(0);
    expect(actionBox.x + actionBox.width).toBeLessThanOrEqual(viewport.width);

    if (viewport.width <= 430) {
      await expect(wrapper).toHaveCSS("overflow-x", "auto");
      expect(await wrapper.evaluate((element) => element.scrollWidth)).toBeGreaterThan(await wrapper.evaluate((element) => element.clientWidth));
      await wrapper.evaluate((element) => { element.scrollLeft = -element.scrollWidth; });
      const totalCell = table.locator("tbody tr").first().locator("td").last();
      const [cellBox, scrollerBox] = await Promise.all([totalCell.boundingBox(), wrapper.boundingBox()]);
      expect(cellBox.x + cellBox.width).toBeGreaterThan(scrollerBox.x);
      expect(cellBox.x).toBeLessThan(scrollerBox.x + scrollerBox.width);

      const editableRow = page.locator('section[aria-label="أصناف الطلب"] fieldset').first();
      const deleteAction = editableRow.getByRole("button", { name: /^حذف / });
      const [rowBox, deleteBox] = await Promise.all([editableRow.boundingBox(), deleteAction.boundingBox()]);
      expect(rowBox.x).toBeGreaterThanOrEqual(0);
      expect(rowBox.x + rowBox.width).toBeLessThanOrEqual(viewport.width);
      expect(deleteBox.x).toBeGreaterThanOrEqual(rowBox.x);
      expect(deleteBox.x + deleteBox.width).toBeLessThanOrEqual(rowBox.x + rowBox.width);
    }

    expectClean(runtime);
  });
}
