import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderApp, stubApi } from "./utils.jsx";
import { authStorage } from "../storage/authStorage.js";

const ADMIN = {
  id: 1,
  email: "owner@example.com",
  full_name: "مالك المتجر",
  role: "super_admin",
  is_active: true,
  created_at: "2026-07-01T00:00:00Z",
  last_login_at: null,
};

const DASHBOARD = {
  products_total: 0,
  products_active: 0,
  categories_total: 0,
  coupons_active: 0,
  orders_total: 0,
  orders_pending: 0,
  orders_by_status: {},
  revenue_total: 0,
  low_stock_products: 0,
  recent_orders: [],
};

const expectStoreLink = (link) => {
  expect(link.getAttribute("href")).toBe("/");
  expect(link).toHaveAttribute("target", "_blank");
  expect(link.getAttribute("rel")).toContain("noopener");
  expect(link.getAttribute("rel")).toContain("noreferrer");
};

describe("back to store link", () => {
  it("appears in the admin layout without replacing the management nav", async () => {
    authStorage.save("valid-token", ADMIN);
    stubApi({ "/api/v1/auth/me": ADMIN, "/api/v1/admin/dashboard": DASHBOARD });
    renderApp("/admin");

    const link = await screen.findByRole("link", { name: /العودة إلى الموقع/ });
    expectStoreLink(link);
    expect(screen.getByRole("link", { name: "المنتجات" })).toBeInTheDocument();
  });

  it("appears on the admin login page without requiring a session", async () => {
    stubApi({});
    renderApp("/admin/login");

    expect(document.querySelector('img[src="/branding/tara-logo2.png"]')).not.toBeNull();
    expect(await screen.findByRole("heading", { name: "تسجيل دخول الإدارة" })).toBeInTheDocument();
    expectStoreLink(screen.getByRole("link", { name: /العودة إلى الموقع/ }));
    expect(screen.getByRole("button", { name: "دخول" })).toBeInTheDocument();
  });
});
