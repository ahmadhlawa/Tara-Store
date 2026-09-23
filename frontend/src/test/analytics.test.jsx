import { render, screen, waitFor, within } from "@testing-library/react";
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
  it("charts views relative to the largest value and keeps linked rankings below", async () => {
    adminApi.analytics.mockResolvedValueOnce({ ...summary, top_products: [summary.top_products[0], { product_id: 2, name: "منتج طويل ".repeat(20), views: 14, product_exists: false }, { product_id: 3, name: "بلا مشاهدات", views: 0, product_exists: false }] });
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    const chart = await screen.findByRole("figure", { name: "مقارنة مشاهدات المنتجات" });
    expect(within(chart).getByText("7 مشاهدة")).toBeInTheDocument();
    expect(Array.from(chart.querySelectorAll("[data-view-bar]")).map((bar) => bar.style.width)).toEqual(["50%", "100%", "0%"]);
    expect(screen.getByRole("link", { name: "ريزن شفاف" })).toHaveAttribute("href", "/admin/products/1");
    expect(chart.nextElementSibling.tagName).toBe("OL");
  });

  it.each([{ rows: [] }, { rows: [{ product_id: 1, name: "صفر", views: 0 }] }])("handles empty and zero views: %j", async ({ rows }) => {
    adminApi.analytics.mockResolvedValueOnce({ ...summary, top_products: rows });
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    await screen.findByText("الزيارات");
    if (!rows.length) expect(screen.getByText("لا توجد مشاهدات منتجات ضمن هذه الفترة بعد.")).toBeInTheDocument();
    else expect(screen.getByRole("figure").querySelector("[data-view-bar]")).toHaveStyle({ width: "0%" });
  });
  it("shows merchant-facing analytics copy without technical implementation details", async () => {
    adminApi.analytics.mockResolvedValueOnce({ ...summary, location_tracking_configured: false });
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    expect(await screen.findByText("الزيارات")).toBeInTheDocument();
    expect(screen.getByText("الزوار الفريدون")).toBeInTheDocument();
    expect(screen.getByText("أماكن الزوار")).toBeInTheDocument();
    expect(screen.getByText("المنتجات الأكثر مشاهدة")).toBeInTheDocument();
    expect(screen.getByText("ملخص لحركة الزوار والمنتجات الأكثر مشاهدة خلال الفترة المحددة.")).toBeInTheDocument();
    expect(screen.getByText("قد لا تتوفر بيانات الموقع الجغرافي لبعض الزيارات.")).toBeInTheDocument();
    expect(screen.getByText("إجمالي الزيارات خلال الفترة المحددة.")).toBeInTheDocument();
    expect(screen.getByText("عدد الزوار المختلفين خلال الفترة المحددة.")).toBeInTheDocument();
    expect(screen.getByText("أكثر الأماكن التي جاءت منها الزيارات.")).toBeInTheDocument();
    expect(screen.getByText("المنتجات التي حازت على أكبر عدد من المشاهدات.")).toBeInTheDocument();
    expect(screen.getByText("القدس")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ريزن شفاف" })).toBeInTheDocument();
    expect(screen.getAllByText("زيارة")).not.toHaveLength(0);
    expect(screen.getAllByText("مشاهدة")).not.toHaveLength(0);

    const pageText = document.body.textContent;
    for (const technicalCopy of ["Cloudflare", "AOP", "fingerprinting", "first-party", "30 دقيقة"]) {
      expect(pageText).not.toContain(technicalCopy);
    }
  });

  it("reloads the common report when the period changes", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    await screen.findByText("الزيارات");
    await user.click(screen.getByRole("button", { name: "آخر 7 أيام" }));
    await waitFor(() => expect(adminApi.analytics).toHaveBeenLastCalledWith("7d"));
    await user.click(screen.getByRole("button", { name: "آخر 30 يوم" }));
    await waitFor(() => expect(adminApi.analytics).toHaveBeenLastCalledWith("30d"));
    await user.click(screen.getByRole("button", { name: "اليوم" }));
    await waitFor(() => expect(adminApi.analytics).toHaveBeenLastCalledWith("today"));
  });
});
