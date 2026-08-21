import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import App from "../App.jsx";

/**
 * Installs a fetch stub that answers from a route table. Anything not listed
 * fails the test rather than silently hitting the network.
 */
export function stubApi(routes) {
  const calls = [];
  globalThis.fetch = vi.fn((url, init = {}) => {
    const path = String(url).replace(/^https?:\/\/[^/]+/, "");
    calls.push({ path, method: init.method || "GET", headers: init.headers || {}, body: init.body });

    // Longest pattern first so /products/featured wins over /products.
    const match = Object.keys(routes)
      .sort((a, b) => b.length - a.length)
      .find((pattern) => {
        const [method, rest] = pattern.includes(" ") ? pattern.split(" ") : ["GET", pattern];
        return method === (init.method || "GET") && path.startsWith(rest);
      });

    if (!match) {
      return Promise.resolve(
        new Response(JSON.stringify({ error: { code: "not_found", message: "no stub" } }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }

    const handler = routes[match];
    const result = typeof handler === "function" ? handler({ path, init }) : handler;
    const { status = 200, body = result } = result && result.__response ? result : { body: result };
    return Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
  return calls;
}

export const respond = (status, body) => ({ __response: true, status, body });

export const page = (items = [], extra = {}) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 24,
  pages: items.length ? 1 : 0,
  ...extra,
});

export const settingsFixture = {
  store_name: "متجر الاختبار",
  store_tagline: "مستلزمات حرفية",
  phone: "0590000000",
  whatsapp: "0590000000",
  working_hours: "٩:٠٠ – ١٩:٠٠",
  announcement: "توصيل سريع",
  currency_code: "ILS",
  currency_symbol: "₪",
  seo_title: "متجر الاختبار",
  seo_description: "وصف المتجر",
  maintenance_mode: false,
};

export const productFixture = {
  id: 1,
  name: "ريزن شفاف",
  slug: "clear-resin",
  short_description: "منتج اختبار",
  description: "فقرة أولى.\n\nفقرة ثانية.",
  sku: "RES-1000",
  product_type: "standard",
  category_id: 1,
  category_name: "ريزن",
  category_slug: "resin",
  price: 100,
  compare_at_price: 130,
  stock_quantity: 5,
  track_inventory: true,
  in_stock: true,
  is_featured: true,
  is_new: false,
  is_bestseller: false,
  primary_image_url: null,
  images: [],
  specifications: [{ id: 1, name: "الوزن", value: "١ كغم", sort_order: 0 }],
  options: [],
  variants: [],
  package_items: [],
};

export const categoryFixture = {
  id: 1,
  name: "ريزن",
  slug: "resin",
  description: "قسم الريزن",
  image_url: null,
  parent_id: null,
  is_active: true,
  is_featured: true,
  sort_order: 0,
  product_count: 1,
  children: [],
};

/** Baseline routes every storefront screen needs during bootstrap. */
export const storefrontRoutes = {
  "/api/v1/store/settings": settingsFixture,
  "/api/v1/categories": [categoryFixture],
  "/api/v1/delivery-areas": [
    { id: 1, name: "رام الله", delivery_fee: 20, free_delivery_threshold: 500, estimated_days: "يومان", sort_order: 0 },
  ],
  "/api/v1/banners": [],
  "/api/v1/hero-slides": [],
  "/api/v1/home-sections": [],
  "/api/v1/articles": page([]),
  "/api/v1/products/featured": page([productFixture]),
  "/api/v1/products/new": page([]),
  "/api/v1/products/bestsellers": page([]),
  "/api/v1/products/packages": page([]),
  "/api/v1/products/molds": page([]),
  "/api/v1/products": page([productFixture]),
};

export function renderApp(initialEntry = "/") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <App />
    </MemoryRouter>,
  );
}
