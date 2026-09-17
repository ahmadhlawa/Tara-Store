import { getLocale, t } from "../i18n/locale.jsx";
// Single HTTP entry point for the whole application.
// Everything else talks to the API through here, so auth headers, the error shape
// and the 401 recovery path exist in exactly one place.

const RAW_BASE = import.meta.env?.VITE_API_BASE_URL ?? "/api/v1";
export const API_BASE_URL = String(RAW_BASE).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, { status = 0, code = "network_error", fields = [] } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

let authToken = null;
let onUnauthorized = null;

export function setAuthToken(token) {
  authToken = token || null;
}

export function getAuthToken() {
  return authToken;
}

/** Called whenever the API rejects our credentials, so the UI can sign out. */
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

function buildUrl(path, params) {
  const url = `${API_BASE_URL}${path}`;
  if (!params) return url;
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    if (Array.isArray(value)) value.forEach((item) => search.append(key, item));
    else search.append(key, value);
  });
  const query = search.toString();
  return query ? `${url}?${query}` : url;
}

async function parseError(response, locale = "ar") {
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const error = body && body.error ? body.error : {};
  return new ApiError(locale === "en" ? (PUBLIC_ERRORS[error.code] || "Something went wrong. Please try again.") : (error.message || `HTTP ${response.status}`), {
    status: response.status,
    code: error.code || "http_error",
    fields: error.fields || [],
  });
}

export async function request(path, { method = "GET", body, params, auth = false, signal, headers: extraHeaders } = {}) {
  const locale = auth || /^\/(admin|auth)(\/|$)/.test(path) ? "ar" : getLocale();
  const headers = { ...extraHeaders };
  const init = { method, headers, signal };

  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  if (auth && authToken) headers.Authorization = `Bearer ${authToken}`;

  let response;
  try {
    response = await fetch(buildUrl(path, params), init);
  } catch (cause) {
    if (cause?.name === "AbortError") throw cause;
    throw new ApiError(t("تعذّر الاتصال بالخادم. تحقق من الاتصال وحاول مرة أخرى.", [], locale), {
      code: "network_error",
    });
  }

  if (response.status === 401 && auth && onUnauthorized) onUnauthorized();
  if (!response.ok) throw await parseError(response, locale);
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  get: (path, options) => request(path, { ...options, method: "GET" }),
  post: (path, body, options) => request(path, { ...options, method: "POST", body }),
  patch: (path, body, options) => request(path, { ...options, method: "PATCH", body }),
  put: (path, body, options) => request(path, { ...options, method: "PUT", body }),
  delete: (path, options) => request(path, { ...options, method: "DELETE" }),
};

const PUBLIC_ERRORS = {
  validation_error: "Please check the submitted information.", maintenance_mode: "The store is under maintenance.",
  not_found: "The requested item was not found.", order_not_found: "Order not found.",
  invalid_quantity: "Quantity must be greater than zero.", product_not_found: "Product not found.",
  product_inactive: "This product is currently unavailable.", package_empty: "This package has no products.",
  variant_required: "Choose the product options before ordering.", variant_mismatch: "This option does not belong to the product.",
  variant_inactive: "This option is unavailable.", variant_option_mismatch: "The options do not match the selected variant.",
  duplicate_option_value: "An option value cannot be selected twice.", option_value_mismatch: "These options are invalid for the product.",
  duplicate_option_axis: "Choose one value for each option.", insufficient_stock: "The requested quantity is unavailable.",
  coupon_invalid: "Invalid discount code.", coupon_not_started: "This discount code is not active yet.",
  coupon_expired: "This discount code has expired.", coupon_exhausted: "This discount code has been fully used.",
  coupon_min_order: "Your order does not meet the minimum for this code.",
  delivery_area_not_found: "Delivery area not found.", delivery_area_inactive: "This delivery area is unavailable.",
  delivery_min_order: "Your order does not meet the minimum for this delivery area.",
  rate_limited: "Too many requests. Please try again shortly.", empty_order: "Add products before ordering.",
};
