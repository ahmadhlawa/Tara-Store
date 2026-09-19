import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AnalyticsPage from "../admin/pages/AnalyticsPage.jsx";
import { adminApi } from "../api/adminApi.js";
import { productFixture, renderApp, settingsFixture, storefrontRoutes, stubApi } from "./utils.jsx";

vi.mock("../api/adminApi.js", async () => {
  const actual = await vi.importActual("../api/adminApi.js");
  return { adminApi: { ...actual.adminApi, analytics: vi.fn() } };
});

const summary = {
  period: "today",
  range_start: "2026-09-18T21:00:00",
  range_end: "2026-09-19T21:00:00",
  location_tracking_configured: true,
  sessions: 14,
  unique_visitors: 9,
  top_locations: [{ name: "القدس", sessions: 5 }, { name: "الداخل", sessions: 4 }],
  top_products: [{ product_id: 1, name: "ريزن شفاف", slug: "clear-resin", views: 7, product_exists: true }],
};

beforeEach(() => {
  adminApi.analytics.mockResolvedValue(summary);
});

describe("storefront analytics tracking", () => {
  it("tracks a public route but never requires a client visitor identifier", async () => {
    const calls = stubApi({ ...storefrontRoutes, "POST /api/v1/analytics/visit": {} });
    renderApp("/ar/");
    await screen.findAllByText(settingsFixture.store_name);
    await waitFor(() => expect(calls.some((call) => call.path.startsWith("/api/v1/analytics/visit"))).toBe(true));
    const call = calls.find((item) => item.path.startsWith("/api/v1/analytics/visit"));
    const body = JSON.parse(call.body);
    expect(body.path).toBe("/ar/");
    expect(body).not.toHaveProperty("visitor_id");
  });

  it("records product view only after a valid PDP loads", async () => {
    const calls = stubApi({
      ...storefrontRoutes,
      "GET /api/v1/products/clear-resin/related": [],
      "GET /api/v1/products/clear-resin": productFixture,
      "POST /api/v1/analytics/visit": {},
      "POST /api/v1/analytics/product-view": {},
    });
    renderApp("/ar/product/clear-resin");
    await screen.findByRole("heading", { name: productFixture.name, level: 1 });
    await waitFor(() => expect(calls.some((call) => call.path.startsWith("/api/v1/analytics/product-view"))).toBe(true));
    const call = calls.find((item) => item.path.startsWith("/api/v1/analytics/product-view"));
    expect(JSON.parse(call.body)).toEqual({ product_id: productFixture.id });
  });
});

describe("Admin analytics page", () => {
  it("shows the approved two metrics and ranked lists", async () => {
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    expect(await screen.findByText("الزيارات")).toBeInTheDocument();
    expect(screen.getByText("الزوار الفريدون")).toBeInTheDocument();
    expect(screen.getByText("أماكن الزوار")).toBeInTheDocument();
    expect(screen.getByText("المنتجات الأكثر مشاهدة")).toBeInTheDocument();
    expect(screen.getByText("القدس")).toBeInTheDocument();
    expect(screen.getByText("ريزن شفاف")).toBeInTheDocument();
  });

  it("reloads the common report when the period changes", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    await screen.findByText("الزيارات");
    await user.click(screen.getByRole("button", { name: "آخر 7 أيام" }));
    await waitFor(() => expect(adminApi.analytics).toHaveBeenLastCalledWith("7d"));
  });
});
