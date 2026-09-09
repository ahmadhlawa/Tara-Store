// The cart lives in the browser. It holds identifiers and a display snapshot only;
// prices are always recomputed by the server before an order is created.
import { readJson, writeJson } from "./safeStorage.js";

const CART_KEY = "commerce_cart_v1";
const VIEWED_KEY = "commerce_viewed_v1";
const SEARCHES_KEY = "commerce_searches_v1";

export const lineKey = (productId, variantId, selectedIds = []) => `${productId}|${variantId ?? ""}|${[...selectedIds].map(Number).sort((a, b) => a - b).join("-")}`;

function sanitize(items) {
  if (!Array.isArray(items)) return [];
  return items
    .filter((item) => item && Number.isFinite(Number(item.productId)) && Number(item.qty) > 0)
    .map((item) => ({
      selectedOptionValueIds: Array.isArray(item.selectedOptionValueIds) ? item.selectedOptionValueIds.map(Number) : [],
      key: item.key || lineKey(item.productId, item.variantId, item.selectedOptionValueIds),
      productId: Number(item.productId),
      variantId: item.variantId == null ? null : Number(item.variantId),
      slug: String(item.slug || ""),
      name: String(item.name || ""),
      unit: Number(item.unit) || 0,
      bg: String(item.bg || ""),
      variation: String(item.variation || ""),
      qty: Math.max(1, Math.min(999, Math.trunc(Number(item.qty)))),
    }));
}

export const cartStorage = {
  load: () => sanitize(readJson(CART_KEY, [])),
  save: (items) => writeJson(CART_KEY, sanitize(items)),
  clear: () => writeJson(CART_KEY, []),
};

export const viewedStorage = {
  load: () => {
    const value = readJson(VIEWED_KEY, []);
    return Array.isArray(value) ? value.filter((slug) => typeof slug === "string") : [];
  },
  push(slug, limit = 8) {
    const next = [slug, ...this.load().filter((item) => item !== slug)].slice(0, limit);
    writeJson(VIEWED_KEY, next);
    return next;
  },
};

export const searchStorage = {
  load: () => {
    const value = readJson(SEARCHES_KEY, []);
    return Array.isArray(value) ? value.filter((term) => typeof term === "string") : [];
  },
  push(term, limit = 5) {
    const next = [term, ...this.load().filter((item) => item !== term)].slice(0, limit);
    writeJson(SEARCHES_KEY, next);
    return next;
  },
};
