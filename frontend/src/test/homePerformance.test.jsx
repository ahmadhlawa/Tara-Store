import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

it("uses one showcase request for multiple categories", async () => {
  // Canvas bounds are unrelated to data loading; jsdom does not implement them.
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  const calls = stubApi({ ...storefrontRoutes,
    "/api/v1/categories": [categoryFixture, { ...categoryFixture, id: 2, slug: "other" }].map(c => ({ ...c, show_on_home: true })),
    "/api/v1/home-showcases": { 1: [productFixture], 2: [{ ...productFixture, id: 2, slug: "other-product" }] },
  });
  renderApp("/ar/");
  await screen.findAllByText(settingsFixture.store_name);
  await waitFor(() => expect(calls.filter(c => c.path.includes("home-showcases"))).toHaveLength(1));
  expect(calls.filter(c => c.path.includes("category_id="))).toHaveLength(0);
});

it("does not force a scroll/layout on a homepage already at the top", async () => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  stubApi(storefrontRoutes);
  renderApp("/ar/");
  await screen.findAllByText(settingsFixture.store_name);
  expect(window.scrollTo).not.toHaveBeenCalled();
});
