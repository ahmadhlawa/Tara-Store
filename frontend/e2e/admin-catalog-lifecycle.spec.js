import { expect, test } from "@playwright/test";
import { MANAGER, apiToken } from "./helpers.js";

test.describe.configure({ mode: "serial" });

test("an admin catalog record persists, reflects publicly, and is safely removed", async ({ request }) => {
  const token = await apiToken(request, MANAGER);
  const headers = { Authorization: `Bearer ${token}` };
  const stamp = Date.now();
  const categorySlug = `e2e-category-${stamp}`;
  const productSlug = `e2e-product-${stamp}`;
  let categoryId;
  let productId;

  try {
    const category = await request.post("/api/v1/admin/categories", {
      headers,
      data: { name: `تصنيف تحقق ${stamp}`, slug: categorySlug, is_active: true, sort_order: 99 },
    });
    expect(category.status(), await category.text()).toBe(201);
    categoryId = (await category.json()).id;

    const product = await request.post("/api/v1/admin/products", {
      headers,
      data: {
        name: `منتج تحقق ${stamp}`,
        slug: productSlug,
        sku: `E2E-${stamp}`,
        category_id: categoryId,
        price: "17.50",
        stock_quantity: 3,
        description: "وصف تحقق عربي",
        is_active: true,
        is_featured: true,
        specifications: [{ name: "المادة", value: "راتنج" }],
      },
    });
    expect(product.status(), await product.text()).toBe(201);
    productId = (await product.json()).id;

    const edited = await request.patch(`/api/v1/admin/products/${productId}`, {
      headers,
      data: { name: `منتج تحقق محرر ${stamp}`, stock_quantity: 4 },
    });
    expect(edited.status(), await edited.text()).toBe(200);

    const publicVisible = await request.get(`/api/v1/products/${productSlug}`);
    expect(publicVisible.status(), await publicVisible.text()).toBe(200);
    expect((await publicVisible.json()).stock_quantity).toBe(4);

    const inactive = await request.patch(`/api/v1/admin/products/${productId}`, {
      headers,
      data: { is_active: false },
    });
    expect(inactive.status(), await inactive.text()).toBe(200);
    const adminDetail = await request.get(`/api/v1/admin/products/${productId}`, { headers });
    expect(adminDetail.status(), await adminDetail.text()).toBe(200);
    expect((await adminDetail.json()).is_active).toBe(false);

    const publicList = await request.get("/api/v1/products");
    expect(publicList.status(), await publicList.text()).toBe(200);
    expect((await publicList.json()).items.some((item) => item.slug === productSlug)).toBe(false);

    const publicSearch = await request.get(`/api/v1/products?q=${encodeURIComponent(productSlug)}`);
    expect(publicSearch.status(), await publicSearch.text()).toBe(200);
    expect((await publicSearch.json()).items.some((item) => item.slug === productSlug)).toBe(false);
    expect((await request.get(`/api/v1/products/${productSlug}`)).status()).toBe(404);

    const active = await request.patch(`/api/v1/admin/products/${productId}`, {
      headers,
      data: { is_active: true },
    });
    expect(active.status(), await active.text()).toBe(200);
    expect((await request.get(`/api/v1/products/${productSlug}`)).status()).toBe(200);
  } finally {
    if (productId) {
      const removed = await request.delete(`/api/v1/admin/products/${productId}`, { headers });
      expect(removed.status(), await removed.text()).toBe(200);
    }
    if (categoryId) {
      const removed = await request.delete(`/api/v1/admin/categories/${categoryId}`, { headers });
      expect(removed.status(), await removed.text()).toBe(200);
    }
  }
});

test("catalog API rejects invalid numeric product input with the validation contract", async ({ request }) => {
  const token = await apiToken(request, MANAGER);
  const response = await request.post("/api/v1/admin/products", {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: "منتج غير صالح", price: "-1", stock_quantity: -1 },
  });
  expect(response.status(), await response.text()).toBe(422);
  expect((await response.json()).error.code).toBe("validation_error");
});
