import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import App from "../App.jsx";
import { cartStorage } from "../storage/cartStorage.js";
import { en } from "../i18n/dictionaries.js";
import { localePath, t } from "../i18n/locale.jsx";
import { productFixture, storefrontRoutes, stubApi, page } from "./utils.jsx";

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}{location.hash}</output>;
}
function open(path) {
  render(<MemoryRouter initialEntries={[path]}><App /><LocationProbe /></MemoryRouter>);
}

describe("storefront localization", () => {
  it("switches languages from the menu, indicates the locale and preserves the page", async () => {
    stubApi(storefrontRoutes);
    open("/ar/category/resin?sort=newest#products");
    await userEvent.click(await screen.findByRole("button", { name: "فتح القائمة" }));
    const menu = screen.getByRole("dialog");
    expect(within(menu).getByRole("link", { name: "العربية" })).toHaveAttribute("aria-current", "true");
    const english = within(menu).getByRole("link", { name: "English" });
    expect(english).toHaveAttribute("href", "/en/category/resin?sort=newest#products");
    await userEvent.click(english);
    expect(screen.getByTestId("location")).toHaveTextContent("/en/category/resin?sort=newest#products");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
    const englishMenu = screen.getByRole("dialog");
    expect(within(englishMenu).getByRole("link", { name: "English" })).toHaveAttribute("aria-current", "true");
    await userEvent.click(within(englishMenu).getByRole("link", { name: "العربية" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/ar/category/resin?sort=newest#products");
  });

  it("redirects legacy URLs and preserves the page, query and hash when switching", async () => {
    const calls = stubApi(storefrontRoutes);
    open("/category/resin?sort=newest#products");
    expect(await screen.findByRole("link", { name: "Switch to English" })).toHaveTextContent("EN");
    expect(screen.getByTestId("location")).toHaveTextContent("/ar/category/resin?sort=newest#products");
    await userEvent.click(screen.getByRole("link", { name: "Switch to English" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/en/category/resin?sort=newest#products");
    expect(document.documentElement).toHaveAttribute("lang", "en");
    expect(document.documentElement).toHaveAttribute("dir", "ltr");
    expect(screen.getByRole("link", { name: "التبديل إلى العربية" })).toHaveTextContent("ع");
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
    await waitFor(() => expect(calls.some((call) => call.path.includes("locale=en"))).toBe(true));
    await userEvent.click(screen.getByRole("link", { name: "التبديل إلى العربية" }));
    expect(document.documentElement).toHaveAttribute("dir", "rtl");
  });

  it("keeps stored cart identity and quantities while refreshing localized labels", async () => {
    cartStorage.save([{ key: "1:base", productId: 1, variantId: null, slug: "clear-resin", name: "ريزن شفاف", unit: 100, qty: 2 }]);
    const calls = stubApi({ ...storefrontRoutes,
      "/api/v1/products/clear-resin": ({ path }) => ({ ...productFixture, name: path.includes("locale=en") ? "Clear resin" : "ريزن شفاف" }),
    });
    open("/ar/cart");
    await screen.findByRole("heading", { name: "إتمام الطلب" });
    await userEvent.click(screen.getByRole("link", { name: "Switch to English" }));
    expect(await screen.findByText("Clear resin")).toBeInTheDocument();
    expect(cartStorage.load()[0]).toMatchObject({ productId: 1, qty: 2, unit: 100 });
    expect(screen.getByRole("heading", { name: "Checkout" })).toBeInTheDocument();
    expect(screen.getByText(/Due to the delicate nature of TARA products/)).toBeInTheDocument();
    expect(screen.getByText(/Please contact TARA within 24 hours/)).toBeInTheDocument();
    expect(calls.some((call) => call.path.includes("clear-resin") && call.path.includes("locale=en"))).toBe(true);
  });

  it("preserves scent presentation, selection and galleries across locales", async () => {
    const product = (english) => ({ ...productFixture, name: english ? "Art Candle" : "شمعة فنية", slug: "art-candle", has_options: true,
      options: [{ id: 5, name: english ? "Scent" : "الرائحة", drives_presentation: true, values: [
        { id: 51, value: english ? "Rose" : "ورد", presentation_title: english ? "Rose Candle" : "شمعة الورد", images: [{ id: 511, url: "/rose.webp" }] },
        { id: 52, value: english ? "Lavender" : "لافندر", presentation_title: english ? "Lavender Candle" : "شمعة اللافندر", images: [{ id: 521, url: "/lavender.webp" }] },
      ] }], variants: [] });
    stubApi({ ...storefrontRoutes,
      "/api/v1/products/art-candle/related": [],
      "/api/v1/products/art-candle": ({ path }) => product(path.includes("locale=en")),
    });
    open("/ar/product/art-candle");
    await userEvent.click(await screen.findByRole("button", { name: "لافندر" }));
    await userEvent.click(screen.getByRole("link", { name: "Switch to English" }));
    expect(await screen.findByRole("heading", { name: "Lavender Candle" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Art Candle" })).toHaveAttribute("src", "/lavender.webp");
    await userEvent.click(screen.getByRole("button", { name: "Rose" }));
    expect(screen.getByRole("heading", { name: "Rose Candle" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Art Candle" })).toHaveAttribute("src", "/rose.webp");
  });

  it("renders English static UI with Arabic dynamic fallback and public errors", async () => {
    const fallbackName = "العروض";
    stubApi({ ...storefrontRoutes, "/api/v1/products": page([{ ...productFixture, name: fallbackName }]) });
    open("/en/shop");
    expect(await screen.findByRole("heading", { name: "All products" })).toBeInTheDocument();
    expect(await screen.findByText(fallbackName)).toBeInTheDocument();
    expect(screen.getAllByText("Add to cart").length).toBeGreaterThan(0);
    expect(screen.getByText("Privacy policy")).toBeInTheDocument();
  });

  it("uses source fallback and stable untranslated slugs", () => {
    expect(t("غير معروف", [], "en")).toBe("غير معروف");
    expect(t("بقي {0} فقط", [3], "en")).toBe("Only 3 left");
    expect(localePath("/ar/product/شمعة?q=rose#details", "en")).toBe("/en/product/شمعة?q=rose#details");
    expect(localePath("/admin/products", "en")).toBe("/admin/products");
    expect(Object.keys(en).length).toBeGreaterThan(250);
  });
});
