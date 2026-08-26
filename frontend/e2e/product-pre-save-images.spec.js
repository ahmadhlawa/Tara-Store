import { expect, test } from "@playwright/test";
import { MANAGER, apiToken, login } from "./helpers.js";

const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLhQAAAAABJRU5ErkJggg==", "base64");

test("new product stages images before its one save and keeps its cover order", async ({ page, request }) => {
  const token = await apiToken(request, MANAGER);
  const headers = { Authorization: `Bearer ${token}` };
  const stamp = Date.now();
  const slug = `e2e-staged-images-${stamp}`;
  const coverFilename = `cover-${stamp}.png`;
  const galleryFilename = `gallery-${stamp}.png`;

  await login(page, MANAGER);
    await page.goto("/admin/products/new");
    await page.getByLabel("اسم المنتج").fill(`منتج صور ${stamp}`);
    await page.getByLabel("الرابط (اختياري)").fill(slug);
    await page.getByLabel("وصف مختصر").fill("وصف مختصر للصور");
    await page.getByLabel("الصورة الرئيسية — رفع من الجهاز").setInputFiles({
      name: coverFilename, mimeType: "image/png", buffer: png,
    });
    await page.getByLabel("صور إضافية — رفع من الجهاز").setInputFiles([
      { name: galleryFilename, mimeType: "image/png", buffer: png },
    ]);

    await expect(page.getByText("صورة رئيسية جديدة")).toBeVisible();
    await expect(page.getByText(galleryFilename)).toBeVisible();
    await expect(page.getByText(/احفظ المنتج أولاً/)).toHaveCount(0);
    await expect(page.getByText("عنوان SEO")).toHaveCount(0);
    await expect(page.getByText("وصف SEO")).toHaveCount(0);

    const created = page.waitForResponse((response) =>
      response.request().method() === "POST" && response.url().endsWith("/api/v1/admin/products"),
    );
    await page.getByRole("button", { name: "حفظ" }).click();
    const product = await created;
    expect(product.status(), await product.text()).toBe(201);
    const productId = (await product.json()).id;
    await expect(page).toHaveURL(new RegExp(`/admin/products/${productId}$`));
    await expect(page.getByText("الصورة الرئيسية", { exact: true })).toBeVisible();

    const saved = await request.get(`/api/v1/admin/products/${productId}`, { headers });
    expect(saved.status(), await saved.text()).toBe(200);
    const row = await saved.json();
    expect(row.images).toHaveLength(2);
    expect(row.images.map((image) => image.sort_order)).toEqual([0, 1]);
    expect(row.images[0].url).toMatch(/^\/media\//);
    expect(row.images[1].url).toMatch(/^\/media\//);
    expect(row.images[0].url).not.toBe(row.images[1].url);
    expect(row.seo_title).toBe(`منتج صور ${stamp}`);
  expect(row.seo_description).toBe("وصف مختصر للصور");
});
