import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

/** Minimal in-memory Storage; jsdom's implementation is not reset between tests. */
function memoryStorage() {
  let data = new Map();
  return {
    getItem: (key) => (data.has(String(key)) ? data.get(String(key)) : null),
    setItem: (key, value) => data.set(String(key), String(value)),
    removeItem: (key) => data.delete(String(key)),
    clear: () => {
      data = new Map();
    },
    key: (index) => Array.from(data.keys())[index] ?? null,
    get length() {
      return data.size;
    },
  };
}

Object.defineProperty(window, "localStorage", { value: memoryStorage(), writable: true });
Object.defineProperty(window, "sessionStorage", { value: memoryStorage(), writable: true });

// Tests never reach the network. Every suite installs its own fetch stub on top
// of this default, which fails loudly if something is left unstubbed.
beforeEach(() => {
  globalThis.fetch = vi.fn(() =>
    Promise.reject(new Error("unexpected network call in a test")),
  );
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.scrollTo = vi.fn();

  // jsdom ships no matchMedia. The default answers "no" to every query, which
  // puts components on their desktop, full-motion path; a test that cares about
  // a breakpoint or reduced motion replaces `window.__mediaMatches`.
  window.__mediaMatches = () => false;
  window.matchMedia = (query) => ({
    media: query,
    get matches() {
      return window.__mediaMatches(query);
    },
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
