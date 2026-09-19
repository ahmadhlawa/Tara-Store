import { publicApi } from "../api/publicApi.js";

export function trackVisit(pathname) {
  return publicApi.analyticsVisit({ path: String(pathname || "/") }).catch(() => null);
}

export function trackProductView(product) {
  if (!product?.id) return Promise.resolve(null);
  return publicApi.analyticsProductView({ product_id: product.id }).catch(() => null);
}
