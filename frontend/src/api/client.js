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

async function parseError(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const error = body && body.error ? body.error : {};
  return new ApiError(error.message || `HTTP ${response.status}`, {
    status: response.status,
    code: error.code || "http_error",
    fields: error.fields || [],
  });
}

export async function request(path, { method = "GET", body, params, auth = false, signal } = {}) {
  const headers = {};
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
    throw new ApiError("تعذّر الاتصال بالخادم. تحقق من الاتصال وحاول مرة أخرى.", {
      code: "network_error",
    });
  }

  if (response.status === 401 && auth && onUnauthorized) onUnauthorized();
  if (!response.ok) throw await parseError(response);
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
