export const STORE_ROUTES = Object.freeze({
  shop: "/shop",
  offers: "/offers",
  packages: "/packages",
  categories: "/categories",
});

export function categoryRoute(slug) {
  return slug ? `/category/${encodeURIComponent(slug)}` : null;
}

export function heroDestination(slide) {
  if (slide?.target_type === "category") return categoryRoute(slide.target_slug);
  if (slide?.target_type === "none") return null;
  if (slide?.target_type && slide.target_type !== "none") {
    return STORE_ROUTES[slide.target_type] || null;
  }
  const legacy = slide?.button_url;
  if (Object.values(STORE_ROUTES).includes(legacy)) return legacy;
  return typeof legacy === "string" && /^\/category\/[^/]+$/.test(legacy) ? legacy : null;
}
