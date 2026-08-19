import { expect, test } from "@playwright/test";
import { MANAGER, apiToken, login } from "./helpers.js";

const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLhQAAAAABJRU5ErkJggg==", "base64");

test("new product stages images before its one save and keeps its cover order", async ({ page, request }) => {
  const token = await apiToken(request, MANAGER);
  const headers = { Authorization: `Bearer ${token}` };
  const stamp = Date.now();
  const slug = `e2e-staged-images-${stamp}`;
  let productId;

  try {
    await login(page, MANAGER);
    await page.goto("/admin/products/new");
    await page.getByLabel("اسم المنتج").fill(`منتج صور ${stamp}`);
    await page.getByLabel("الرابط (اختياري)").fill(slug);
    await page.getByLabel("وصف مختصر").fill("وصف مختصر للصور");
    await page.getByLabel("الصورة الرئيسية — رفع من الجهاز").setInputFiles({
      name: "cover.png", mimeType: "image/png", buffer: png,
    });
    await page.getByLabel("صور إضافية — رفع من الجهاز").setInputFiles([
      { name: "gallery.png", mimeType: "image/png", buffer: png },
    ]);

    await expect(page.getByText("صورة رئيسية جديدة")).toBeVisible();
    await expect(page.getByText("gallery.png")).toBeVisible();
    await expect(page.getByText(/احفظ المنتج أولاً/)).toHaveCount(0);
    await expect(page.getByText("عنوان SEO")).toHaveCount(0);
    await expect(page.getByText("وصف SEO")).toHaveCount(0);

    const created = page.waitForResponse((response) =>
      response.request().method() === "POST" && response.url().endsWith("/api/v1/admin/products"),
    );
    await page.getByRole("button", { name: "حفظ" }).click();
    const product = await created;
    expect(product.status(), await product.text()).toBe(201);
    productId = (await product.json()).id;
    await page.waitForURL(new RegExp(`/admin/products/${productId}$`));
    await expect(page.getByText("الصورة الرئيسية")).toBeVisible();

    const saved = await request.get(`/api/v1/admin/products/${productId}`, { headers });
    expect(saved.status(), await saved.text()).toBe(200);
    const row = await saved.json();
    expect(row.images).toHaveLength(2);
    expect(row.images[0].url).toContain("cover");
    expect(row.images[1].url).toContain("gallery");
    expect(row.seo_title).toBe(`منتج صور ${stamp}`);
    expect(row.seo_description).toBe("وصف مختصر للصور");
  } finally {
    if (productId) await request.delete(`/api/v1/admin/products/${productId}`, { headers });
  }
});
