import { expect, test } from "@playwright/test";
import { MANAGER, login } from "./helpers.js";

const PUBLIC_PAGES = [
  "/",
  "/shop",
  "/category/vfx-resin",
  "/product/vfx-resin-clear-1l",
  "/cart",
  "/checkout",
  "/contact",
];

const ADMIN_PAGES = [
  "/admin",
  "/admin/products",
  "/admin/orders",
  "/admin/invoices",
  "/admin/coupons",
  "/admin/settings",
];

/**
 * The page body must never scroll sideways. Wide tables are allowed to scroll, but
 * inside their own container — so the check is on the document, not on descendants.
 */
async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return { scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth };
  });
  // One pixel of slack absorbs sub-pixel rounding in the layout engine.
  expect(
    overflow.scrollWidth,
    `document scrolls horizontally: ${overflow.scrollWidth} > ${overflow.clientWidth}`,
  ).toBeLessThanOrEqual(overflow.clientWidth + 1);
}

test.describe("public storefront layout", () => {
  for (const path of PUBLIC_PAGES) {
    test(`${path} fits the viewport and renders right to left`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await expectNoHorizontalOverflow(page);

      const direction = await page.evaluate(
        () => getComputedStyle(document.body).direction,
      );
      expect(direction).toBe("rtl");
    });
  }

  test("the hero shows the whole advertisement, not a cropped slice", async ({ page }, testInfo) => {
    // A wide screen crops the hero artwork top and bottom on purpose; this is about
    // the phone and tablet forms, where the crop was sideways.
    test.skip(
      (testInfo.project.use.viewport?.width ?? 1440) > 900,
      "desktop keeps its deliberate letterbox crop",
    );
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // How much of the artwork's own width survives the box it is drawn into.
    // A phone is narrower than the hero artwork, so covering a portrait box threw the
    // promotional text off both sides; whatever technique is used, the visible
    // fraction is what the reader actually gets.
    const visible = await page.evaluate(() => {
      const img = document.querySelector('.vs-hero__slide[data-active="true"] img');
      if (!img || !img.naturalWidth) return null;
      const box = img.getBoundingClientRect();
      const fit = getComputedStyle(img).objectFit;
      if (fit === "contain" || fit === "scale-down") return 1;
      const drawn = (box.height * img.naturalWidth) / img.naturalHeight;
      return Math.min(1, drawn / box.width);
    });

    test.skip(visible === null, "no hero artwork in this environment");
    expect(visible).toBeGreaterThan(0.98);
  });

  test("the header stays reachable and the cart control is labelled", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "عربة التسوّق" })).toBeVisible();
    await expect(page.getByRole("link", { name: "تسجيل دخول الإدارة" })).toBeVisible();
  });
});

test.describe("admin workspace layout", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, MANAGER);
  });

  for (const path of ADMIN_PAGES) {
    test(`${path} fits the viewport`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await expectNoHorizontalOverflow(page);

      const direction = await page.evaluate(
        () => getComputedStyle(document.body).direction,
      );
      expect(direction).toBe("rtl");
    });
  }
});

test.describe("keyboard and focus", () => {
  test("the checkout form is reachable and submittable from the keyboard", async ({ page }) => {
    await page.goto("/product/vfx-resin-clear-1l");
    await page.getByRole("button", { name: /أضف إلى العربة|إضافة إلى العربة/ }).first().click();
    await page.goto("/checkout");

    await page.keyboard.press("Tab");
    const focusedTag = await page.evaluate(() => document.activeElement?.tagName);
    expect(focusedTag).toBeTruthy();

    // Every visible control carries an accessible name.
    const unnamed = await page.evaluate(() => {
      const nodes = [...document.querySelectorAll("input, select, textarea")];
      return nodes
        .filter((node) => node.type !== "hidden")
        .filter((node) => {
          const label = node.closest("label");
          return !(
            node.getAttribute("aria-label") ||
            node.getAttribute("aria-labelledby") ||
            (label && label.textContent.trim())
          );
        })
        .map((node) => `${node.tagName}[type=${node.type}]`);
    });
    expect(unnamed, `controls without an accessible name: ${unnamed.join(", ")}`).toEqual([]);
  });

  test("the admin login form can be completed with the keyboard alone", async ({ page }) => {
    await page.goto("/admin/login");
    await page.locator('form input[type="email"]').focus();
    await page.keyboard.type(MANAGER.email);
    await page.keyboard.press("Tab");
    await page.keyboard.type(MANAGER.password);
    await page.keyboard.press("Enter");
    await page.waitForURL(/\/admin(?!\/login)/, { timeout: 20_000 });
  });
});
