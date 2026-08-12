import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { page, renderApp, settingsFixture, storefrontRoutes, stubApi } from "./utils.jsx";

/**
 * Tara goes live before the client's catalog arrives, so the zero-product,
 * zero-category state is a shipping configuration and not a transient one. Every
 * catalog endpoint answers an empty page here — exactly what the real API returns
 * today — and the storefront still has to be navigable, honest and free of
 * half-rendered sections.
 */
const EMPTY_CATALOG = {
  ...storefrontRoutes,
  "/api/v1/categories": [],
  "/api/v1/products/featured": page([]),
  "/api/v1/products/new": page([]),
  "/api/v1/products/bestsellers": page([]),
  "/api/v1/products/packages": page([]),
  "/api/v1/products/molds": page([]),
  "/api/v1/products": page([]),
  "/api/v1/home-sections": [
    { id: 1, section_key: "categories", section_type: "categories", title: "تسوّق حسب القسم", description: "", sort_order: 1, config: {} },
    { id: 2, section_key: "featured", section_type: "featured_products", title: "منتجات مختارة", description: "", sort_order: 2, config: {} },
  ],
};

describe("storefront with no catalog", () => {
  it("renders the homepage shell without empty product or category sections", async () => {
    stubApi(EMPTY_CATALOG);
    renderApp("/");

    expect(await screen.findAllByText(settingsFixture.store_name)).not.toHaveLength(0);
    // The gap the dropped sections leave is filled by an honest empty state rather
    // than by invented content. Waiting on it also means every list has resolved.
    expect(await screen.findByText("المتجر قيد التجهيز")).toBeInTheDocument();
    // The sections exist in the database but have nothing to show, so they are
    // absent rather than rendered as empty headings.
    expect(screen.queryByText("تسوّق حسب القسم")).not.toBeInTheDocument();
    expect(screen.queryByText("منتجات مختارة")).not.toBeInTheDocument();
    // The shell is still whole: the store did not fail to load.
    expect(screen.queryByText("تعذّر تحميل بيانات المتجر")).not.toBeInTheDocument();
  });

  it("never claims a stocked store is being prepared", async () => {
    // The baseline fixture has a category and a product but no home sections at
    // all: an unarranged homepage, not an empty store.
    stubApi(storefrontRoutes);
    renderApp("/");

    expect(await screen.findAllByText(settingsFixture.store_name)).not.toHaveLength(0);
    expect(screen.queryByText("المتجر قيد التجهيز")).not.toBeInTheDocument();
  });

  it("shows the shop route's empty state instead of a broken grid", async () => {
    stubApi(EMPTY_CATALOG);
    renderApp("/shop");

    expect(await screen.findByText("لا توجد منتجات مطابقة")).toBeInTheDocument();
  });

  it("keeps the policy pages readable", async () => {
    stubApi({
      ...EMPTY_CATALOG,
      "/api/v1/pages/shipping-policy": {
        id: 5,
        title: "سياسة الشحن والتوصيل",
        slug: "shipping-policy",
        lead: "تكلفة ومدة التوصيل وحدود التوصيل المجاني.",
        content: "تختلف تكلفة ومدة التوصيل حسب المنطقة.\n\nالتوصيل المجاني للطلبات من 220 شيكل.",
      },
    });
    renderApp("/page/shipping-policy");

    expect(
      await screen.findByRole("heading", { name: "سياسة الشحن والتوصيل", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText(/التوصيل المجاني للطلبات من 220 شيكل/)).toBeInTheDocument();
  });
});
