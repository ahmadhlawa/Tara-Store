import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import Media from "../components/public/shell/Media.jsx";
import { categoryFixture, page, productFixture, renderApp, settingsFixture, storefrontRoutes, stubApi } from "./utils.jsx";

it("delivers responsive uploads and falls back to the original if delivery fails", () => {
  const src = "/media/0123456789abcdef0123456789abcdef.png";
  render(<Media src={src} alt="Artwork" />);
  const image = screen.getByAltText("Artwork");
  expect(image.getAttribute("srcset")).toContain("width=480 480w");
  fireEvent.error(image);
  expect(image.getAttribute("srcset")).toBeNull();
  expect(image.getAttribute("src")).toBe(src);
});

it("ignores legacy showcase categories without configured Home Sections", async () => {
  // Canvas bounds are unrelated to data loading; jsdom does not implement them.
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  const calls = stubApi({ ...storefrontRoutes,
    "/api/v1/categories": [categoryFixture, { ...categoryFixture, id: 2, slug: "other" }].map(c => ({ ...c, show_on_home: true })),
    "/api/v1/home-showcases": { 1: [productFixture], 2: [{ ...productFixture, id: 2, slug: "other-product" }] },
  });
  renderApp("/ar/");
  await screen.findAllByRole("link", { name: `${settingsFixture.store_name} — الصفحة الرئيسية` });
  await waitFor(() => expect(calls.some(c => c.path.includes("home-sections"))).toBe(true));
  expect(calls.filter(c => c.path.includes("home-showcases"))).toHaveLength(0);
  expect(document.querySelectorAll(".vs-home-showcase")).toHaveLength(0);
  expect(calls.filter(c => c.path.includes("category_id="))).toHaveLength(0);
});

it("does not force a scroll/layout on a homepage already at the top", async () => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  stubApi(storefrontRoutes);
  renderApp("/ar/");
  await screen.findAllByRole("link", { name: `${settingsFixture.store_name} — الصفحة الرئيسية` });
  expect(window.scrollTo).not.toHaveBeenCalled();
});

it.each([
  ["featured_products", "featured", "vs-grid"],
  ["new_products", "new", "vs-grid"],
  ["bestsellers", "bestsellers", "vs-rail"],
])("preserves intentionally configured %s Home Sections", async (type, endpoint, layout) => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  const calls = stubApi({
    ...storefrontRoutes,
    "/api/v1/categories": [{ ...categoryFixture, show_on_home: true }],
    "/api/v1/home-sections": [{ id: 1, section_type: type, title: "Admin selection", config: {} }],
    [`/api/v1/products/${endpoint}`]: page([productFixture, { ...productFixture, id: 2, slug: "second", name: "Second product" }]),
  });
  renderApp("/ar/");
  await screen.findByRole("heading", { name: "Admin selection" });
  await screen.findByText("Second product");
  expect(document.querySelector(`.vs-home .${layout}`)).not.toBeNull();
  expect(calls.filter(c => c.path.includes("home-showcases"))).toHaveLength(0);
});
