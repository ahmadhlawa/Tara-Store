import { waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { productFixture, renderApp, settingsFixture, storefrontRoutes, stubApi } from "./utils.jsx";

const settings = {
  ...settingsFixture,
  public_base_url: "https://shop.example.com",
};

describe("route SEO", () => {
  it("publishes canonical home metadata and real organization data", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/store/settings": settings });
    renderApp("/");
    await waitFor(() => expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute("href", "https://shop.example.com/"));
    expect(document.querySelector('meta[name="description"]')).toHaveAttribute("content", settingsFixture.seo_description);
    const records = [...document.querySelectorAll('script[type="application/ld+json"]')].map((node) => JSON.parse(node.textContent));
    expect(records.map((record) => record["@type"])).toEqual(["Organization", "WebSite"]);
    expect(records[0]).not.toHaveProperty("aggregateRating");
  });

  it("uses real product fields and replaces stale home JSON-LD", async () => {
    const product = { ...productFixture, seo_title: "SEO Product", seo_description: "Real description" };
    stubApi({
      ...storefrontRoutes,
      "/api/v1/store/settings": settings,
      "/api/v1/products/clear-resin/related": [],
      "/api/v1/products/clear-resin": product,
    });
    renderApp("/product/clear-resin");
    await waitFor(() => expect(document.title).toBe("SEO Product"));
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute("href", "https://shop.example.com/product/clear-resin");
    const records = [...document.querySelectorAll('script[type="application/ld+json"]')].map((node) => JSON.parse(node.textContent));
    expect(records.find((record) => record["@type"] === "Product").offers).toMatchObject({ price: "100", priceCurrency: "ILS", availability: "https://schema.org/InStock" });
    expect(records.some((record) => record["@type"] === "WebSite")).toBe(false);
  });

  it("noindexes search and client-side not-found routes", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/store/settings": settings });
    const view = renderApp("/search?q=resin");
    await waitFor(() => expect(document.querySelector('meta[name="robots"]')).toHaveAttribute("content", "noindex, nofollow"));
    view.unmount();
    renderApp("/missing-route");
    await waitFor(() => expect(document.title).toBe("الصفحة غير موجودة"));
    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute("content", "noindex, nofollow");
  });
});
