import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import App from "../App.jsx";
import { HeroSlidesPage } from "../admin/pages/ContentScreens.jsx";
import { heroDestination } from "../utils/storeRoutes.js";
import { categoryFixture, page, productFixture, renderApp, settingsFixture, storefrontRoutes, stubApi } from "./utils.jsx";

describe("structured hero destinations", () => {
  it("resolves every supported route including a specific category", () => {
    expect(heroDestination({ target_type: "shop" })).toBe("/shop");
    expect(heroDestination({ target_type: "offers" })).toBe("/offers");
    expect(heroDestination({ target_type: "packages" })).toBe("/packages");
    expect(heroDestination({ target_type: "categories" })).toBe("/categories");
    expect(heroDestination({ target_type: "category", target_slug: "شموع" })).toBe("/category/%D8%B4%D9%85%D9%88%D8%B9");
  });

  it("offers an Admin category selector without a URL field", async () => {
    const slide = { id: 7, image_url: "/hero.png", target_type: "none", target_slug: null, sort_order: 0, is_active: true };
    const calls = stubApi({
      "/api/v1/admin/hero-slides": [slide],
      "PATCH /api/v1/admin/hero-slides/7": { ...slide, target_type: "category", target_slug: categoryFixture.slug },
      "/api/v1/admin/categories": { items: [categoryFixture], total: 1, page: 1, pages: 1 },
    });
    render(<MemoryRouter><HeroSlidesPage /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "تعديل" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByLabelText("وجهة الإعلان")).toBeInTheDocument();
    expect(within(dialog).queryByLabelText(/رابط/)).toBeNull();
    await userEvent.selectOptions(within(dialog).getByLabelText("وجهة الإعلان"), "category");
    await userEvent.selectOptions(within(dialog).getByLabelText("القسم"), categoryFixture.slug);
    expect(within(dialog).getByText(/2100×800/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(calls.some((call) => call.method === "PATCH" && JSON.parse(call.body).target_slug === categoryFixture.slug)).toBe(true));
  });

  it("links hero artwork to category and all-categories destinations", async () => {
    stubApi({
      ...storefrontRoutes,
      "/api/v1/hero-slides": [
        { id: 1, image_url: "/hero-category.png", target_type: "category", target_slug: "candles" },
        { id: 2, image_url: "/hero-categories.png", target_type: "categories", target_slug: null },
      ],
    });
    renderApp("/");
    await waitFor(() => expect(document.querySelectorAll(".vs-hero__slide")).toHaveLength(2));
    const slides = document.querySelectorAll(".vs-hero__slide");
    expect(slides[0]).toHaveAttribute("href", "/category/candles");
    expect(slides[1]).toHaveAttribute("href", "/categories");
  });
});

describe("categories navigation", () => {
  it("routes the homepage category View All link to the categories index", async () => {
    stubApi({
      ...storefrontRoutes,
      "/api/v1/categories": [categoryFixture],
      "/api/v1/home-sections": [{ id: 1, section_key: "cats", section_type: "categories", title: "تسوّق حسب القسم", description: "", sort_order: 0, config: {} }],
    });
    renderApp("/");
    expect(await screen.findByRole("link", { name: "عرض الكل" })).toHaveAttribute("href", "/categories");
  });

  it("shows active categories on /categories and excludes inactive rows", async () => {
    stubApi({
      ...storefrontRoutes,
      "/api/v1/settings": settingsFixture,
      "/api/v1/categories": [categoryFixture, { ...categoryFixture, id: 9, slug: "hidden", name: "مخفي", is_active: false }],
    });
    render(<MemoryRouter initialEntries={["/categories"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "كل الأقسام" })).toBeInTheDocument();
    expect(screen.getAllByText(categoryFixture.name).length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.queryByText("مخفي")).toBeNull());
  });

  it("uses visual child cards and keeps the selected child in the URL filter", async () => {
    const candles = {
      ...categoryFixture,
      id: 20,
      slug: "candles",
      name: "Candles",
      image_url: "/candles.jpg",
      product_count: 2,
      children: [
        { ...categoryFixture, id: 21, parent_id: 20, slug: "scented", name: "الشموع العطرية", image_url: "/scented.jpg" },
        { ...categoryFixture, id: 22, parent_id: 20, slug: "drinks", name: "شمعة المشروبات", image_url: "/drinks.jpg" },
      ],
    };
    const calls = stubApi({
      ...storefrontRoutes,
      "/api/v1/categories": [candles],
      "/api/v1/categories/candles": candles,
      "/api/v1/products": page([productFixture]),
    });
    renderApp("/category/candles");

    const all = await screen.findByRole("button", { name: "الكل" });
    expect(all).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "الشموع العطرية" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "الشموع العطرية" })).toHaveAttribute("aria-pressed", "true"));
    await waitFor(() => expect(calls.some((call) => call.path.includes("category=scented"))).toBe(true));
  });

  it("builds Home showcases only for enabled root categories", async () => {
    const enabled = { ...categoryFixture, id: 30, slug: "candles", name: "Candles", show_on_home: true, image_url: "/candles.jpg" };
    const second = { ...categoryFixture, id: 31, slug: "crochet", name: "Crochet", show_on_home: true, image_url: "/crochet.jpg" };
    const disabled = { ...categoryFixture, id: 32, slug: "resin", name: "Resin", show_on_home: false };
    const calls = stubApi({
      ...storefrontRoutes,
      "/api/v1/categories": [enabled, second, disabled],
      "/api/v1/products": page([productFixture]),
    });
    renderApp("/");

    await waitFor(() => expect(document.querySelectorAll(".vs-home-showcase")).toHaveLength(2));
    expect(screen.getByRole("heading", { name: "Candles" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Crochet" })).toBeInTheDocument();
    expect(calls.some((call) => call.path.includes("category=candles"))).toBe(true);
    expect(calls.some((call) => call.path.includes("category=crochet"))).toBe(true);
    expect(calls.some((call) => call.path.includes("category=resin"))).toBe(false);
  });
});
