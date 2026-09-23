import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  categoryFixture,
  page,
  productFixture,
  renderApp,
  storefrontRoutes,
  stubApi,
} from "./utils.jsx";
import { cartStorage } from "./../storage/cartStorage.js";

const openCategories = () => screen.getByRole("button", { name: "كل الأقسام" });
const cartButton = () => screen.getByRole("button", { name: "عربة التسوّق" });
const dialogs = () => screen.queryAllByRole("dialog");

describe("public shell", () => {
  it.each(["click", "touch", "keyboard"])("opens checkout with one %s and closes the cart", async (input) => {
    cartStorage.save([{ key: "1|", productId: 1, slug: "clear-resin", name: "Resin", unit: 100, qty: 1 }]);
    stubApi({ ...storefrontRoutes, "POST /api/v1/cart/price": { lines: [], subtotal: 100, discount: 0, delivery_fee: 0, total: 100 } });
    renderApp("/ar/shop");
    await screen.findByRole("heading", { name: "كل المنتجات", level: 1 });
    const user = userEvent.setup();
    await user.click(cartButton());
    const checkout = within(screen.getByRole("dialog", { name: "عربة التسوّق" })).getByRole("link", { name: "إتمام الطلب" });
    expect(checkout).toHaveAttribute("href", "/ar/checkout");
    if (input === "touch") await user.pointer([{ keys: "[TouchA>]", target: checkout }, { keys: "[/TouchA]", target: checkout }]);
    else if (input === "keyboard") { checkout.focus(); await user.keyboard("{Enter}"); }
    else await user.click(checkout);
    await waitFor(() => expect(document.querySelector(".vs-checkout")).toBeInTheDocument());
    expect(dialogs()).toHaveLength(0);
    expect(document.body.style.overflow).not.toBe("hidden");
  });

  it("gives the storefront its landmarks and a skip link", async () => {
    stubApi(storefrontRoutes);
    renderApp("/");

    expect(await screen.findByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "التنقّل الرئيسي" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "تخطَّ إلى المحتوى" })).toHaveAttribute(
      "href",
      "#vs-content",
    );
  });

  it("keeps the storefront chrome out of the admin workspace", async () => {
    stubApi(storefrontRoutes);
    const { container } = renderApp("/admin");

    await waitFor(() => expect(container.querySelector(".vs-public")).toBeNull());
    expect(screen.queryByRole("button", { name: "عربة التسوّق" })).not.toBeInTheDocument();
    expect(screen.queryByRole("contentinfo")).not.toBeInTheDocument();
  });

  it("sends the header icon beside the cart to the isolated admin login", async () => {
    stubApi(storefrontRoutes);
    renderApp("/");

    const adminLogin = await screen.findByRole("link", { name: "تسجيل دخول الإدارة" });
    expect(adminLogin).toHaveAttribute("href", "/admin/login");

    await userEvent.click(adminLogin);
    expect(await screen.findByRole("heading", { name: "تسجيل دخول الإدارة" })).toBeInTheDocument();
    expect(screen.queryByRole("banner")).not.toBeInTheDocument();
    expect(screen.queryByRole("contentinfo")).not.toBeInTheDocument();
  });

  it("renders the real footer without an order-tracking entry", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/store/settings": { ...storefrontRoutes["/api/v1/store/settings"], email: "hello@example.com", address: "عنوان المتجر", location_url: "https://maps.example.com/store" } });
    renderApp("/");

    const footer = await screen.findByRole("contentinfo");
    expect(within(footer).queryByText("تتبّع الطلب")).not.toBeInTheDocument();
    expect(footer.querySelectorAll('a[href="/track-order"]')).toHaveLength(0);
    await waitFor(() => expect(within(footer).getByRole("link", { name: "hello@example.com" })).toHaveAttribute("href", "mailto:hello@example.com"));
    expect(within(footer).getByRole("link", { name: "0590000000" })).toHaveAttribute("href", "tel:0590000000");
    expect(within(footer).getByRole("link", { name: "عنوان المتجر" })).toHaveAttribute("href", "https://maps.example.com/store");
  });

  it("keeps duplicate contact details out of the header and payment note out of the footer", async () => {
    stubApi(storefrontRoutes);
    renderApp("/");

    const header = await screen.findByRole("banner");
    const footer = screen.getByRole("contentinfo");
    expect(header.querySelector('a[href^="tel:"]')).toBeNull();
    expect(within(footer).queryByText("لا يتم إدخال بيانات بطاقات بنكية في هذا المتجر.")).not.toBeInTheDocument();
  });

  it("shows category links alongside normal links in the mobile navigation", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/categories": [{ ...categoryFixture, children: [{ ...categoryFixture, id: 2, slug: "child", name: "قسم فرعي", children: [] }] }] });
    renderApp("/");

    const header = await screen.findByRole("banner");
    expect(header.querySelectorAll('a[href="/track-order"]')).toHaveLength(0);
    expect(screen.getByRole("link", { name: "تسجيل دخول الإدارة" })).toHaveAttribute("href", "/admin/login");

    await userEvent.click(screen.getByRole("button", { name: "فتح القائمة" }));
    const mobileNavigation = screen.getByRole("dialog", { name: "قائمة التنقّل" });
    expect(within(mobileNavigation).getByRole("link", { name: "كل المنتجات" })).toBeInTheDocument();
    expect(within(mobileNavigation).getByRole("link", { name: categoryFixture.name })).toHaveAttribute("href", "/ar/category/resin");
    expect(within(mobileNavigation).getByText("أقسام")).toBeInTheDocument();
    expect(Array.from(mobileNavigation.querySelector(".vs-menu").children).filter((node) => node.matches("a, button")).map((node) => node.textContent.trim())).toEqual(["الرئيسية", "أقسام", "العروض", "البكجات", "كل المنتجات", "تواصل معنا"]);
    expect(mobileNavigation.querySelectorAll('a[href="/track-order"]')).toHaveLength(0);
    expect(within(mobileNavigation).queryByText("تتبّع الطلب")).not.toBeInTheDocument();
    expect(within(mobileNavigation).getByRole("link", { name: "الرئيسية" })).toHaveAttribute("aria-current", "page");
    await userEvent.click(within(mobileNavigation).getByRole("button", { name: `الأقسام الفرعية لـ ${categoryFixture.name}` }));
    expect(within(mobileNavigation).getByRole("link", { name: "قسم فرعي" })).toHaveAttribute("href", "/ar/category/child");
    await userEvent.click(within(mobileNavigation).getByRole("button", { name: "أقسام", exact: true }));
    expect(within(mobileNavigation).queryByRole("link", { name: "قسم فرعي" })).not.toBeInTheDocument();
    await userEvent.click(within(mobileNavigation).getByRole("button", { name: "أقسام", exact: true }));
    await userEvent.click(within(mobileNavigation).getByRole("link", { name: "قسم فرعي" }));
    await waitFor(() => expect(dialogs()).toHaveLength(0));
  });

  it.each(["/track-order", "/track", "/order-tracking"])("treats %s as a public not-found route", async (path) => {
    stubApi(storefrontRoutes);
    renderApp(path);

    expect(await screen.findByRole("heading", { name: "الصفحة غير موجودة" })).toBeInTheDocument();
  });
});

describe("category navigation", () => {
  it("opens the category drawer from the header, locks the page and closes on escape", async () => {
    stubApi(storefrontRoutes);
    renderApp("/");

    const trigger = await screen.findByRole("button", { name: "كل الأقسام" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(trigger);
    expect(openCategories()).toHaveAttribute("aria-expanded", "true");

    const panel = screen.getByRole("dialog", { name: "تصنيفات المنتجات" });
    expect(panel).toHaveAttribute("aria-modal", "true");
    // Every category comes from the API, never from a hard-coded list.
    expect(within(panel).getByText(categoryFixture.name)).toBeInTheDocument();
    expect(document.body.style.overflow).toBe("hidden");
    // Focus moved into the dialog rather than staying behind it.
    expect(panel).toContainElement(document.activeElement);

    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(dialogs()).toHaveLength(0));
    expect(document.body.style.overflow).not.toBe("hidden");
    expect(openCategories()).toHaveFocus();
  });

  it("links each category to its own route and closes the drawer on navigation", async () => {
    stubApi(storefrontRoutes);
    renderApp("/");

    await userEvent.click(await screen.findByRole("button", { name: "كل الأقسام" }));
    const panel = screen.getByRole("dialog", { name: "تصنيفات المنتجات" });
    const link = within(panel).getByText(categoryFixture.name).closest("a");
    expect(link).toHaveAttribute("href", `/ar/category/${categoryFixture.slug}`);

    await userEvent.click(link);
    await waitFor(() => expect(dialogs()).toHaveLength(0));
  });
});

describe("drawers", () => {
  it("opens the cart drawer, traps it as a dialog and restores focus to the trigger", async () => {
    stubApi(storefrontRoutes);
    renderApp("/");

    const trigger = await screen.findByRole("button", { name: "عربة التسوّق" });
    trigger.focus();
    await userEvent.click(trigger);

    const drawer = screen.getByRole("dialog", { name: "عربة التسوّق" });
    expect(drawer).toHaveAttribute("aria-modal", "true");
    expect(drawer).not.toContainElement(document.body);
    expect(document.body.style.overflow).toBe("hidden");
    // Focus moved inside the drawer rather than staying behind it.
    expect(drawer).toContainElement(document.activeElement);

    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(dialogs()).toHaveLength(0));
    expect(cartButton()).toHaveFocus();
    expect(document.body.style.overflow).not.toBe("hidden");
  });

  it("never leaves two overlays open at once", async () => {
    stubApi(storefrontRoutes);
    renderApp("/");

    await userEvent.click(await screen.findByRole("button", { name: "فتح القائمة" }));
    expect(screen.getByRole("dialog", { name: "قائمة التنقّل" })).toBeInTheDocument();

    await userEvent.click(cartButton());
    expect(dialogs()).toHaveLength(1);
    expect(screen.getByRole("dialog", { name: "عربة التسوّق" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "فتح البحث" }));
    expect(dialogs()).toHaveLength(1);
    expect(screen.getByRole("dialog", { name: "البحث" })).toBeInTheDocument();
  });

  it("shows an empty cart drawer before anything is added", async () => {
    stubApi(storefrontRoutes);
    renderApp("/");

    await userEvent.click(await screen.findByRole("button", { name: "عربة التسوّق" }));
    const drawer = screen.getByRole("dialog", { name: "عربة التسوّق" });
    expect(within(drawer).getByText("لا توجد منتجات بعد")).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "تصفّح المتجر" })).toHaveAttribute(
      "href",
      "/ar/shop",
    );
  });

  it("edits and removes a line from the drawer", async () => {
    cartStorage.save([
      {
        key: "1|",
        productId: 1,
        variantId: null,
        slug: "clear-resin",
        name: "ريزن شفاف",
        unit: 100,
        bg: "",
        variation: "",
        qty: 1,
      },
    ]);
    stubApi(storefrontRoutes);
    renderApp("/");

    await userEvent.click(await screen.findByRole("button", { name: "عربة التسوّق" }));
    const drawer = screen.getByRole("dialog", { name: "عربة التسوّق" });

    await userEvent.click(within(drawer).getByRole("button", { name: /زيادة الكمية/ }));
    await waitFor(() => expect(cartStorage.load()[0].qty).toBe(2));
    // The line total and the drawer subtotal both read 200 ₪; assert the line.
    const line = within(drawer).getByRole("listitem");
    expect(within(line).getByText("200 ₪")).toBeInTheDocument();

    await userEvent.click(within(drawer).getByRole("button", { name: /إزالة ريزن شفاف/ }));
    await waitFor(() => expect(cartStorage.load()).toHaveLength(0));
    expect(await within(drawer).findByText("لا توجد منتجات بعد")).toBeInTheDocument();
  });
});

describe("search", () => {
  it("suggests products as the visitor types and routes to the results page", async () => {
    const calls = stubApi({
      ...storefrontRoutes,
      "/api/v1/products/clear-resin/related": [],
      "/api/v1/products/clear-resin": productFixture,
    });
    renderApp("/");

    const field = await screen.findByRole("combobox", { name: "ابحث في المتجر" });
    await userEvent.type(field, "ريزن");

    expect(await screen.findByRole("option", { name: /ريزن شفاف/ })).toBeInTheDocument();
    await waitFor(() =>
      expect(calls.some((call) => call.path.includes("q=%D8%B1%D9%8A%D8%B2%D9%86"))).toBe(true),
    );

    await userEvent.click(screen.getByRole("option", { name: /ريزن شفاف/ }));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      productFixture.name,
    );
  });

  it("asks for a term instead of listing the whole catalogue", async () => {
    stubApi(storefrontRoutes);
    renderApp("/search");

    expect(await screen.findByRole("heading", { name: "ابدأ بالبحث" })).toBeInTheDocument();
    expect(screen.queryByText(productFixture.name)).not.toBeInTheDocument();
  });
});

describe("catalogue states", () => {
  it("keeps an intentional empty state when a filter matches nothing", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/products": page([]) });
    renderApp("/shop?sale=1");

    expect(await screen.findByText("لا توجد منتجات مطابقة")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "المخفّضة فقط ✕" })).toBeInTheDocument();
  });

  it("degrades to an error panel rather than a blank page", async () => {
    stubApi({
      ...storefrontRoutes,
      "/api/v1/products": () => {
        throw new Error("boom");
      },
    });
    renderApp("/shop");

    expect(await screen.findByRole("alert")).toHaveTextContent("تعذّر تحميل المنتجات");
  });

  it("carries a chosen sort in the URL so the listing can be shared", async () => {
    const calls = stubApi(storefrontRoutes);
    renderApp("/shop");

    await screen.findByRole("heading", { name: "كل المنتجات", level: 1 });
    await userEvent.selectOptions(screen.getByLabelText(/ترتيب حسب/), "price-asc");

    await waitFor(() =>
      expect(calls.some((call) => call.path.includes("sort=price-asc"))).toBe(true),
    );
  });
});
