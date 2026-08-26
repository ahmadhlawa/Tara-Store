import { expect, test } from "@playwright/test";

function channel(value) {
  const normalized = value / 255;
  return normalized <= 0.04045
    ? normalized / 12.92
    : ((normalized + 0.055) / 1.055) ** 2.4;
}

function contrast(first, second) {
  const rgb = (value) => value.match(/\d+(?:\.\d+)?/g).slice(0, 3).map(Number);
  const luminance = (value) => {
    const [red, green, blue] = rgb(value).map(channel);
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
  };
  const [lighter, darker] = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
}

async function colors(locator) {
  return locator.evaluate((element) => {
    const style = getComputedStyle(element);
    return { background: style.backgroundColor, foreground: style.color };
  });
}

test("public and Admin primary actions have independent accessible foregrounds", async ({ page }) => {
  await page.goto("/shop");
  const publicAction = page.locator(".vs-btn--primary:visible").first();
  await expect(publicAction).toBeVisible();
  const publicColors = await colors(publicAction);
  expect(contrast(publicColors.background, publicColors.foreground)).toBeGreaterThanOrEqual(4.5);
  await expect(page.locator(".vs-public")).toHaveCSS("font-family", /Alexandria/);

  await page.goto("/admin/login");
  const adminRoot = page.locator(".admin-app");
  await expect(adminRoot).toHaveCount(1);
  await expect(adminRoot).toHaveCSS("font-family", /Cairo/);
  expect(await adminRoot.evaluate((element) => element.closest(".vs-public"))).toBeNull();

  const adminAction = page.locator('form button[type="submit"]');
  const adminColors = await colors(adminAction);
  expect(contrast(adminColors.background, adminColors.foreground)).toBeGreaterThanOrEqual(4.5);
});

test("runtime storefront overrides stay on the public owner and out of Admin", async ({ page }) => {
  await page.goto("/shop");
  await page.locator(".vs-public").evaluate((owner) => {
    owner.style.setProperty("--brand-primary", "#FF0000");
    owner.style.setProperty("--button-primary-background", "#FF0000");
    owner.style.setProperty("--nav-strip-background", "#00FF00");
    owner.style.setProperty("--footer-background", "#0000FF");
  });

  await expect(page.locator(".vs-btn--primary:visible").first()).toHaveCSS("background-color", "rgb(255, 0, 0)");
  await expect(page.locator(".vs-nav")).toHaveCSS("background-color", "rgb(0, 255, 0)");
  await expect(page.locator(".vs-footer")).toHaveCSS("background-color", "rgb(0, 0, 255)");
  expect(await page.evaluate(() => document.documentElement.style.cssText)).not.toContain("--brand-primary");

  await page.evaluate(() => {
    history.pushState({}, "", "/admin/login");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await expect(page.locator(".admin-app")).toHaveCount(1);
  await expect(page.locator('form button[type="submit"]')).toHaveCSS("background-color", "rgb(174, 152, 203)");
  await expect(page.locator('form button[type="submit"]')).toHaveCSS("color", "rgb(24, 24, 24)");
});
