// Authenticated admin endpoints. Every call carries the bearer token.
import { api, request } from "./client.js";

const authed = { auth: true };
const withParams = (params) => ({ auth: true, params });

export const adminApi = {
  login: (email, password) => api.post("/auth/login", { email, password }),
  me: () => api.get("/auth/me", authed),

  dashboard: () => api.get("/admin/dashboard", authed),

  listProducts: (params) => api.get("/admin/products", withParams(params)),
  getProduct: (id) => api.get(`/admin/products/${id}`, authed),
  createProduct: (payload) => api.post("/admin/products", payload, authed),
  updateProduct: (id, payload) => api.patch(`/admin/products/${id}`, payload, authed),
  deleteProduct: (id) => api.delete(`/admin/products/${id}`, authed),

  addProductImage: (id, payload) => api.post(`/admin/products/${id}/images`, payload, authed),
  deleteProductImage: (id, imageId) =>
    api.delete(`/admin/products/${id}/images/${imageId}`, authed),
  // The whole image set, in the order it should be stored: position decides the cover.
  reorderProductImages: (id, imageIds) =>
    api.put(`/admin/products/${id}/images/reorder`, { image_ids: imageIds }, authed),
  replaceSpecifications: (id, payload) =>
    api.put(`/admin/products/${id}/specifications`, payload, authed),
  replaceOptions: (id, payload) => api.put(`/admin/products/${id}/options`, payload, authed),
  createVariant: (id, payload) => api.post(`/admin/products/${id}/variants`, payload, authed),
  updateVariant: (id, variantId, payload) =>
    api.patch(`/admin/products/${id}/variants/${variantId}`, payload, authed),
  deleteVariant: (id, variantId) =>
    api.delete(`/admin/products/${id}/variants/${variantId}`, authed),
  addPackageItem: (id, payload) => api.post(`/admin/products/${id}/package-items`, payload, authed),
  deletePackageItem: (id, itemId) =>
    api.delete(`/admin/products/${id}/package-items/${itemId}`, authed),

  listCategories: (params) => api.get("/admin/categories", withParams(params)),
  createCategory: (payload) => api.post("/admin/categories", payload, authed),
  updateCategory: (id, payload) => api.patch(`/admin/categories/${id}`, payload, authed),
  deleteCategory: (id) => api.delete(`/admin/categories/${id}`, authed),

  listHeroSlides: () => api.get("/admin/hero-slides", authed),
  createHeroSlide: (payload) => api.post("/admin/hero-slides", payload, authed),
  updateHeroSlide: (id, payload) => api.patch(`/admin/hero-slides/${id}`, payload, authed),
  deleteHeroSlide: (id) => api.delete(`/admin/hero-slides/${id}`, authed),

  listBanners: () => api.get("/admin/banners", authed),
  createBanner: (payload) => api.post("/admin/banners", payload, authed),
  updateBanner: (id, payload) => api.patch(`/admin/banners/${id}`, payload, authed),
  deleteBanner: (id) => api.delete(`/admin/banners/${id}`, authed),

  listCoupons: (params) => api.get("/admin/coupons", withParams(params)),
  createCoupon: (payload) => api.post("/admin/coupons", payload, authed),
  updateCoupon: (id, payload) => api.patch(`/admin/coupons/${id}`, payload, authed),
  deleteCoupon: (id) => api.delete(`/admin/coupons/${id}`, authed),

  listDeliveryAreas: () => api.get("/admin/delivery-areas", authed),
  createDeliveryArea: (payload) => api.post("/admin/delivery-areas", payload, authed),
  updateDeliveryArea: (id, payload) => api.patch(`/admin/delivery-areas/${id}`, payload, authed),
  deleteDeliveryArea: (id) => api.delete(`/admin/delivery-areas/${id}`, authed),

  listOrders: (params) => api.get("/admin/orders", withParams(params)),
  getOrder: (id) => api.get(`/admin/orders/${id}`, authed),
  createManualOrder: (payload) => api.post("/admin/orders/manual", payload, authed),
  updateOrder: (id, payload) => api.patch(`/admin/orders/${id}`, payload, authed),
  updateOrderStatus: (id, status, note) =>
    api.post(`/admin/orders/${id}/status`, { status, note }, authed),
  completeOrder: (id, payload) => api.post(`/admin/orders/${id}/complete`, payload, authed),
  reopenOrder: (id, reason) => api.post(`/admin/orders/${id}/reopen`, { reason }, authed),
  updateOrderNotes: (id, adminNotes) =>
    api.patch(`/admin/orders/${id}/notes`, { admin_notes: adminNotes }, authed),

  // Invoices are read-only by design: they are issued by the backend when an order is
  // confirmed, and the only write here is a cancellation.
  listInvoices: (params) => api.get("/admin/invoices", withParams(params)),
  getInvoice: (invoiceNumber) => api.get(`/admin/invoices/${invoiceNumber}`, authed),
  getOrderInvoice: (orderId) => api.get(`/admin/orders/${orderId}/invoice`, authed),
  updateInvoicePayment: (invoiceNumber, payload) =>
    api.patch(`/admin/invoices/${invoiceNumber}/payment`, payload, authed),
  cancelInvoice: (invoiceNumber, reason) =>
    api.post(`/admin/invoices/${invoiceNumber}/cancel`, { reason }, authed),

  listArticles: (params) => api.get("/admin/articles", withParams(params)),
  createArticle: (payload) => api.post("/admin/articles", payload, authed),
  updateArticle: (id, payload) => api.patch(`/admin/articles/${id}`, payload, authed),
  deleteArticle: (id) => api.delete(`/admin/articles/${id}`, authed),

  listPages: () => api.get("/admin/pages", authed),
  createPage: (payload) => api.post("/admin/pages", payload, authed),
  updatePage: (id, payload) => api.patch(`/admin/pages/${id}`, payload, authed),
  deletePage: (id) => api.delete(`/admin/pages/${id}`, authed),

  listMedia: (params) => api.get("/admin/media", withParams(params)),
  uploadMedia: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/admin/media", { method: "POST", body: form, auth: true });
  },
  renameMedia: (id, payload) => api.patch(`/admin/media/${id}`, payload, authed),
  deleteMedia: (id) => api.delete(`/admin/media/${id}`, authed),

  getSettings: () => api.get("/admin/settings", authed),
  updateSettings: (payload) => api.patch("/admin/settings", payload, authed),

  listAdmins: (params) => api.get("/admin/admins", withParams(params)),
  createAdmin: (payload) => api.post("/admin/admins", payload, authed),
  updateAdmin: (id, payload) => api.patch(`/admin/admins/${id}`, payload, authed),
  deleteAdmin: (id) => api.delete(`/admin/admins/${id}`, authed),

  listAuditLogs: (params) => api.get("/admin/audit-logs", withParams(params)),
};
