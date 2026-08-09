import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies the API and the uploaded media so the browser talks to a
// single origin; deep links such as /product/slug fall back to the SPA entry point.
export default defineConfig(({ mode }) => {
  const apiTarget = loadEnv(mode, process.cwd(), "").VITE_DEV_API_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": { target: apiTarget, changeOrigin: true },
        "/media": { target: apiTarget, changeOrigin: true },
        "/health": { target: apiTarget, changeOrigin: true },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.js"],
      css: false,
      include: ["src/**/*.test.{js,jsx}"],
    },
  };
});
