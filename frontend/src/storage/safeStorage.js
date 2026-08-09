// localStorage/sessionStorage are unavailable in private modes and in some
// embedded browsers. Reads fall back to a default, writes fail silently — a
// storefront must keep working without persistence.

function backend(kind) {
  try {
    return kind === "session" ? window.sessionStorage : window.localStorage;
  } catch {
    return null;
  }
}

export function readJson(key, fallback, kind = "local") {
  const store = backend(kind);
  if (!store) return fallback;
  try {
    const raw = store.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export function writeJson(key, value, kind = "local") {
  const store = backend(kind);
  if (!store) return false;
  try {
    store.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function remove(key, kind = "local") {
  const store = backend(kind);
  if (!store) return;
  try {
    store.removeItem(key);
  } catch {
    /* ignore */
  }
}
