// Public storefront endpoints. No authentication is ever sent from here.
import { api } from "./client.js";

export const publicApi = {
  settings: () => api.get("/store/settings"),
  categories: (params) => api.get("/categories", { params }),
  category: (slug) => api.get(`/categories/${encodeURIComponent(slug)}`),

  products: (params) => api.get("/products", { params }),
  product: (slug) => api.get(`/products/${encodeURIComponent(slug)}`),
  relatedProducts: (slug, limit = 4) =>
    api.get(`/products/${encodeURIComponent(slug)}/related`, { params: { limit } }),
  featuredProducts: (params) => api.get("/products/featured", { params }),
  newProducts: (params) => api.get("/products/new", { params }),
  bestsellers: (params) => api.get("/products/bestsellers", { params }),
  packages: (params) => api.get("/products/packages", { params }),
  molds: (params) => api.get("/products/molds", { params }),

  heroSlides: () => api.get("/hero-slides"),
  homeSections: () => api.get("/home-sections"),
  deliveryAreas: () => api.get("/delivery-areas"),

  page: (slug) => api.get(`/pages/${encodeURIComponent(slug)}`),

  validateCoupon: (code, subtotal) => api.post("/coupons/validate", { code, subtotal }),
  priceCart: (payload) => api.post("/cart/price", payload),
  createOrder: (payload) => api.post("/orders", payload),
  order: (orderNumber, token) =>
    api.get(`/orders/${encodeURIComponent(orderNumber)}`, { headers: { "X-Order-Token": token } }),
};
