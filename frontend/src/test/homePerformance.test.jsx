import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import Media from "../components/public/shell/Media.jsx";
import { categoryFixture, productFixture, renderApp, settingsFixture, storefrontRoutes, stubApi } from "./utils.jsx";

it("delivers responsive uploads and falls back to the original if delivery fails", () => {
  const src = "/media/0123456789abcdef0123456789abcdef.png";
  render(<Media src={src} alt="Artwork" />);
  const image = screen.getByAltText("Artwork");
  expect(image.getAttribute("srcset")).toContain("width=480 480w");
  fireEvent.error(image);
  expect(image.getAttribute("srcset")).toBeNull();
  expect(image.getAttribute("src")).toBe(src);
});

it("renders products for an enabled homepage category", async () => {
  // Canvas bounds are unrelated to data loading; jsdom does not implement them.
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  const calls = stubApi({ ...storefrontRoutes,
    "/api/v1/categories": [{ ...categoryFixture, show_on_home: true }],
    "/api/v1/home-showcases": { 1: [productFixture] },
  });
  renderApp("/ar/");
  await screen.findAllByRole("link", { name: `${settingsFixture.store_name} — الصفحة الرئيسية` });
  await waitFor(() => expect(calls.some(c => c.path.includes("home-sections"))).toBe(true));
  const section = (await screen.findByText(productFixture.name)).closest("section");
  expect(section.querySelector(".vs-home-showcase")).not.toBeNull();
  expect(section.querySelector(".vs-home-showcase__category .vs-cat")).not.toBeNull();
  expect(section.querySelector(".vs-home-showcase__content")).not.toBeNull();
  expect(section.querySelector(".vs-home-showcase__products > .vs-card")).not.toBeNull();
  expect(within(section).getByRole("heading", { name: categoryFixture.name })).toBeInTheDocument();
  expect(within(section).getByRole("link", { name: "عرض الكل" })).toHaveAttribute("href", `/ar/category/${categoryFixture.slug}`);
  expect(calls.filter(c => c.path.includes("home-showcases"))).toHaveLength(1);
});

it("does not render a disabled homepage category", async () => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  const calls = stubApi({
    ...storefrontRoutes,
    "/api/v1/categories": [{ ...categoryFixture, show_on_home: false }],
    "/api/v1/home-showcases": { 1: [productFixture] },
  });
  renderApp("/ar/");
  await waitFor(() => expect(calls.some(call => call.path.includes("home-showcases"))).toBe(true));
  expect(screen.queryByRole("heading", { name: categoryFixture.name })).not.toBeInTheDocument();
});

it("renders two enabled homepage categories as separate sections", async () => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  const secondCategory = { ...categoryFixture, id: 2, slug: "other", name: "قسم آخر" };
  const secondProduct = { ...productFixture, id: 2, slug: "other-product", name: "منتج آخر" };
  stubApi({
    ...storefrontRoutes,
    "/api/v1/categories": [categoryFixture, secondCategory].map(category => ({ ...category, show_on_home: true })),
    "/api/v1/home-showcases": { 1: [productFixture], 2: [secondProduct] },
  });
  renderApp("/ar/");
  const firstSection = (await screen.findByText(productFixture.name)).closest("section");
  const secondSection = (await screen.findByText(secondProduct.name)).closest("section");
  expect(within(firstSection).getByRole("heading", { name: categoryFixture.name })).toBeInTheDocument();
  expect(within(secondSection).getByRole("heading", { name: secondCategory.name })).toBeInTheDocument();
  expect(firstSection).not.toBe(secondSection);
});

it("does not force a scroll/layout on a homepage already at the top", async () => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  stubApi(storefrontRoutes);
  renderApp("/ar/");
  await screen.findAllByRole("link", { name: `${settingsFixture.store_name} — الصفحة الرئيسية` });
  expect(window.scrollTo).not.toHaveBeenCalled();
});

it.each(["featured_products", "new_products", "bestsellers", "packages"])(
  "does not render legacy %s Home Sections",
  async (type) => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  const calls = stubApi({
    ...storefrontRoutes,
    "/api/v1/categories": [{ ...categoryFixture, show_on_home: true }],
    "/api/v1/home-sections": [{ id: 1, section_type: type, title: "Admin selection", config: {} }],
    "/api/v1/home-showcases": {},
  });
  renderApp("/ar/");
  await waitFor(() => expect(calls.some(call => call.path.includes("home-showcases"))).toBe(true));
  expect(screen.queryByRole("heading", { name: "Admin selection" })).not.toBeInTheDocument();
  expect(calls.some(call => call.path.includes(`/products/`))).toBe(false);
  },
);
