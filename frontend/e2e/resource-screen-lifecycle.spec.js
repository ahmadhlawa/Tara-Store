import { expect, test } from "@playwright/test";
import { login, MANAGER } from "./helpers.js";

test.describe.configure({ mode: "serial" });

// These routes all use ResourceScreen.  The first text control is their required
// identifier; the remaining required controls have configuration defaults.  Exercising
// this once per configuration proves the real modal/create/edit/delete wiring, rather
// than treating a clean route render as CRUD coverage.
const RESOURCES = [
  { path: "/admin/categories", value: (stamp) => `E2E ${stamp}` },
  {
    path: "/admin/coupons",
    value: (stamp) => `E2E${stamp}`,
    editIndex: 1,
    rowAfterEdit: (value) => value,
  },
  { path: "/admin/delivery", value: (stamp) => `E2E ${stamp}` },
  { path: "/admin/hero", value: (stamp) => `E2E ${stamp}` },
  { path: "/admin/banners", value: (stamp) => `E2E ${stamp}` },
  {
    path: "/admin/home",
    value: (stamp) => `e2e-${stamp}`,
    editIndex: 1,
    rowAfterEdit: (value) => value,
  },
  { path: "/admin/articles", value: (stamp) => `E2E ${stamp}` },
  { path: "/admin/pages", value: (stamp) => `E2E ${stamp}` },
  {
    path: "/admin/admins",
    value: (stamp) => `e2e-${stamp}@example.com`,
    fillCreate: async (editor, stamp) => {
      await editor.locator('input:not([type="checkbox"])').nth(1).fill(`E2E ${stamp}`);
      await editor.locator('input:not([type="checkbox"])').nth(2).fill(`E2e!${stamp}Pass`);
    },
    editIndex: 1,
  },
];

for (const resource of RESOURCES) {
  test(`${resource.path} creates, edits, and deletes through its ResourceScreen dialogs`, async ({ page }) => {
    const stamp = String(Date.now());
    const value = resource.value(stamp);
    const renamed = `${value}-edited`;
    await login(page, MANAGER);
    await page.goto(resource.path);
    await page.waitForLoadState("networkidle");

    // The responsive navigation includes a hidden menu button before main content;
    // scope the opener to this screen's PageHeader rather than relying on DOM order.
    await page.locator("h1").locator("xpath=../..").getByRole("button").click();
    const editor = page.getByRole("dialog");
    await expect(editor).toBeVisible();
    await editor.locator('input:not([type="checkbox"]):not([type="color"])').first().fill(value);
    await resource.fillCreate?.(editor, stamp);
    await editor.locator("button").last().click();
    await expect(editor).toHaveCount(0);

    const created = page.locator("tr", { hasText: value });
    await expect(created).toHaveCount(1);
    await created.getByRole("button").first().click();
    const editDialog = page.getByRole("dialog");
    await editDialog.locator('input:not([type="checkbox"]):not([type="color"])').nth(resource.editIndex ?? 0).fill(renamed);
    await editDialog.locator("button").last().click();
    const rowAfterEdit = resource.rowAfterEdit?.(value, renamed) ?? renamed;
    await expect(page.locator("tr", { hasText: rowAfterEdit })).toHaveCount(1);

    const edited = page.locator("tr", { hasText: rowAfterEdit });
    if (resource.editIndex !== undefined) {
      await edited.getByRole("button").first().click();
      await expect(
        page.getByRole("dialog").locator('input:not([type="checkbox"]):not([type="color"])').nth(resource.editIndex),
      ).toHaveValue(renamed);
      await page.getByRole("dialog").getByRole("button").first().click();
    }
    await edited.getByRole("button").last().click();
    const confirm = page.getByRole("dialog");
    await expect(confirm).toBeVisible();
    await confirm.locator("button").last().click();
    await expect(page.locator("tr", { hasText: rowAfterEdit })).toHaveCount(0);
  });
}
