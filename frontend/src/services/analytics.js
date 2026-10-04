import { publicApi } from "../api/publicApi.js";

export function trackVisit(pathname) {
  return publicApi.analyticsVisit({ path: String(pathname || "/") }).catch(() => null);
}

export function trackProductView(product) {
  if (!product?.id) return Promise.resolve(null);
  return publicApi.analyticsProductView({ product_id: product.id }).catch(() => null);
}

function trackEvent(eventType) {
  try {
    return Promise.resolve(publicApi.analyticsEvent({ event_type: eventType })).catch(() => null);
  } catch {
    return Promise.resolve(null);
  }
}

export function trackAddToCart() {
  return trackEvent("add_to_cart");
}

export function trackCheckoutReached() {
  return trackEvent("checkout_reached");
}
