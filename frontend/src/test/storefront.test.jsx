import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  categoryFixture,
  page,
  productFixture,
  renderApp,
  respond,
  settingsFixture,
  storefrontRoutes,
  stubApi,
} from "./utils.jsx";
import { cartStorage } from "../storage/cartStorage.js";

describe("public storefront", () => {
  it("renders the shell with store identity from the API", async () => {
    stubApi(storefrontRoutes);
    renderApp("/");

    expect(await screen.findAllByText(settingsFixture.store_name)).not.toHaveLength(0);
    expect(screen.getByRole("search")).toBeInTheDocument();
    expect(screen.getByText(settingsFixture.announcement)).toBeInTheDocument();
    expect(document.querySelector(".vs-footer")).toHaveTextContent("الدفع عند الاستلام");
    expect(screen.queryByText(/تحويل بنكي|تحويل يدوي/)).not.toBeInTheDocument();
    expect(screen.queryByText("من الساعة العاشرة صباحاً حتى السابعة مساءً")).not.toBeInTheDocument();
  });

  it("always shows the fixed delivery trust copy", async () => {
    stubApi({
      ...storefrontRoutes,
      "/api/v1/delivery-areas": [],
    });
    renderApp("/");

    expect(await screen.findByText("التوصيل إلى جميع المناطق")).toBeInTheDocument();
    expect(screen.getByText("تُحتسب رسوم التوصيل عند إتمام الطلب")).toBeInTheDocument();
  });

  it("renders the homepage sections the admin has made visible", async () => {
    stubApi({
      ...storefrontRoutes,
      "/api/v1/hero-slides": [
        {
          id: 1,
          title: "عنوان الشريحة",
          subtitle: "جديد",
          description: "وصف",
          button_label: "تسوّق",
          button_url: "/shop",
          image_url: "/media/hero.png",
          sort_order: 0,
        },
      ],
      "/api/v1/home-sections": [
        { id: 1, section_key: "categories", section_type: "categories", title: "أقسامنا", description: "تسوّق", sort_order: 1, config: {} },
        { id: 2, section_key: "featured", section_type: "featured_products", title: "مختارات", description: "", sort_order: 2, config: {} },
      ],
    });
    renderApp("/");

    await waitFor(() =>
      expect(document.querySelector(".vs-hero img")).toHaveAttribute("src", "/media/hero.png"),
    );
    expect(screen.queryByText("عنوان الشريحة")).not.toBeInTheDocument();
    expect(await screen.findByText("أقسامنا")).toBeInTheDocument();
    expect(await screen.findAllByText(categoryFixture.name)).not.toHaveLength(0);
  });

  it("lists products on the shop route", async () => {
    stubApi(storefrontRoutes);
    renderApp("/shop");

    expect(await screen.findByRole("heading", { name: "كل المنتجات", level: 1 })).toBeInTheDocument();
    expect(await screen.findAllByText(productFixture.name)).not.toHaveLength(0);
    expect(await screen.findByText("1 منتجاً")).toBeInTheDocument();
  });

  it("shows an intentional empty state when nothing matches", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/products": page([]) });
    renderApp("/shop");

    expect(await screen.findByText("لا توجد منتجات مطابقة")).toBeInTheDocument();
  });

  it("renders a focused product page without specifications or delivery guidance", async () => {
    stubApi({
      ...storefrontRoutes,
      "/api/v1/products/clear-resin/related": [],
      "/api/v1/products/clear-resin": productFixture,
    });
    renderApp("/product/clear-resin");

    expect(await screen.findByRole("heading", { name: productFixture.name, level: 1 })).toBeInTheDocument();
    expect(screen.getByText("100 ₪")).toBeInTheDocument();
    expect(screen.getByText("130 ₪")).toBeInTheDocument();
    expect(screen.getByText("فقرة أولى.")).toBeInTheDocument();
    const pdp = within(document.querySelector(".vs-pdp"));
    expect(pdp.queryByText("المواصفات")).not.toBeInTheDocument();
    expect(pdp.queryByText("الوزن")).not.toBeInTheDocument();
    expect(pdp.queryByText("التوصيل والدفع")).not.toBeInTheDocument();
    expect(pdp.queryByText("الدفع عند الاستلام")).not.toBeInTheDocument();
  });

  it("keeps a missing product on an intentional not-found page", async () => {
    stubApi({
      ...storefrontRoutes,
      "/api/v1/products/ghost": respond(404, { error: { code: "not_found", message: "غير موجود" } }),
    });
    renderApp("/product/ghost");

    expect(await screen.findByRole("heading", { name: "الصفحة غير موجودة" })).toBeInTheDocument();
  });

  it("renders an intentional Not Found page for unknown routes", async () => {
    stubApi(storefrontRoutes);
    renderApp("/no-such-page");

    expect(await screen.findByRole("heading", { name: "الصفحة غير موجودة" })).toBeInTheDocument();
    expect(screen.getByText("404")).toBeInTheDocument();
  });

  it("adds a product to the cart and persists it in local storage", async () => {
    stubApi(storefrontRoutes);
    renderApp("/shop");

    const card = (await screen.findAllByText(productFixture.name))[0].closest("div");
    await userEvent.click(within(card.parentElement).getByRole("button", { name: /أضف إلى العربة/ }));

    await waitFor(() => expect(cartStorage.load()).toHaveLength(1));
    const [line] = cartStorage.load();
    expect(line.productId).toBe(productFixture.id);
    expect(line.unit).toBe(100); // the charged price, not compare_at_price
    expect(line.qty).toBe(1);
  });

  it.each(["ar", "en"])("redirects the legacy %s cart to checkout", async (locale) => {
    cartStorage.save([{ key: "1|", productId: 1, slug: "clear-resin", name: "Resin", imageUrl: "/rose.jpg", unit: 100, variation: "Rose", qty: 2 }]);
    stubApi({ ...storefrontRoutes, "POST /api/v1/cart/price": { lines: [], subtotal: 200, discount: 0, delivery_fee: 0, total: 200 } });
    renderApp(`/${locale}/cart?source=bookmark#summary`);
    await waitFor(() => expect(document.querySelector(".vs-checkout")).toBeInTheDocument());
    const summary = document.querySelector(".vs-summary");
    expect(summary.querySelector("img")).toHaveAttribute("src", "/rose.jpg");
    expect(summary).toHaveTextContent("Rose");
    expect(summary).toHaveTextContent("×2");
    await waitFor(() => expect(summary.querySelector(".vs-summary__total")).toHaveTextContent("200"));
  });

  it("applies, removes and rejects coupons directly in checkout", async () => {
    const user = userEvent.setup();
    cartStorage.save([{ key: "1|", productId: 1, slug: "clear-resin", name: "Resin", unit: 100, variation: "Rose", qty: 2 }]);
    stubApi({ ...storefrontRoutes,
      "POST /api/v1/cart/price": ({ init }) => ({ lines: [], subtotal: 200, discount: JSON.parse(init.body).coupon_code ? 20 : 0, delivery_fee: 0, total: JSON.parse(init.body).coupon_code ? 180 : 200 }),
      "POST /api/v1/coupons/validate": ({ init }) => JSON.parse(init.body).code === "SAVE" ? { code: "SAVE", label: "Save", discount: 20 } : respond(422, { error: { code: "coupon_invalid", message: "Invalid coupon" } }),
    });
    renderApp("/en/checkout");
    const disclosure = await screen.findByText("Have a discount coupon?");
    expect(disclosure.closest("details")).not.toHaveAttribute("open");
    await user.click(disclosure);
    await user.type(screen.getByRole("textbox", { name: "Discount code" }), "SAVE");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(document.querySelector(".vs-summary__total")).toHaveTextContent("180"));
    expect(document.querySelector(".vs-coupon__msg")).toHaveTextContent("Save");
    await user.click(screen.getByRole("button", { name: "Remove coupon" }));
    await waitFor(() => expect(document.querySelector(".vs-summary__total")).toHaveTextContent("200"));
    await user.type(screen.getByRole("textbox", { name: "Discount code" }), "BAD");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByText("Invalid discount code.")).toBeInTheDocument();
  });

  it("blocks checkout until the customer fields are valid", async () => {
    cartStorage.save([
      { key: "1|", productId: 1, variantId: null, slug: "clear-resin", name: "ريزن شفاف", unit: 100, bg: "", variation: "", qty: 1 },
    ]);
    const calls = stubApi({
      ...storefrontRoutes,
      "POST /api/v1/cart/price": {
        lines: [],
        subtotal: 100,
        discount: 0,
        delivery_fee: 20,
        total: 120,
        coupon_code: null,
        delivery_area_name: "رام الله",
      },
      "POST /api/v1/orders": respond(500, { error: { code: "boom", message: "should not be called" } }),
    });
    renderApp("/checkout");

    await userEvent.click(await screen.findByRole("checkbox"));
    const submit = screen.getByRole("button", { name: /تأكيد وإرسال الطلب/ });
    await userEvent.click(submit);

    expect(await screen.findAllByText("الرجاء إدخال الاسم الكامل")).not.toHaveLength(0);
    expect(screen.getByText("رقم هاتف غير صالح — مثال 0591234567")).toBeInTheDocument();
    expect(screen.getByText("اختر منطقة التوصيل")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("الرجاء إدخال الاسم الكامل");
    expect(screen.getByPlaceholderText("مثال: محمد أحمد")).toHaveFocus();
    expect(calls.some((call) => call.path.split("?")[0] === "/api/v1/orders")).toBe(false);
  });

  it("requires return-policy acknowledgement before enabling final confirmation", async () => {
    cartStorage.save([
      { key: "1|", productId: 1, variantId: null, slug: "clear-resin", name: "ريزن شفاف", unit: 100, bg: "", variation: "", qty: 1 },
    ]);
    stubApi({
      ...storefrontRoutes,
      "POST /api/v1/cart/price": {
        lines: [], subtotal: 100, discount: 0, delivery_fee: 20, total: 120,
        coupon_code: null, delivery_area_name: "رام الله",
      },
    });
    renderApp("/checkout");

    expect(await screen.findByText("نظراً لطبيعة منتجات تارا وحساسية القطع، وكونها مصنوعة ومجهزة يدوياً بعناية، لا يمكن استبدال أو إرجاع المنتجات بعد تأكيد الطلب أو استلامه.")).toBeInTheDocument();
    const acknowledgement = screen.getByRole("checkbox", { name: /قرأت سياسة الإرجاع والاستبدال وأوافق عليها/ });
    const submit = screen.getByRole("button", { name: /تأكيد وإرسال الطلب/ });
    expect(acknowledgement).not.toBeChecked();
    expect(submit).toBeDisabled();
    expect(screen.getByRole("link", { name: "سياسة الإرجاع والاستبدال" })).toHaveAttribute("href", "/ar/page/return-policy");

    await userEvent.click(acknowledgement);
    expect(submit).toBeEnabled();
  });

  it("submits a valid checkout and moves to the confirmation route", async () => {
    cartStorage.save([
      { key: "1|", productId: 1, variantId: null, slug: "clear-resin", name: "ريزن شفاف", unit: 100, bg: "", variation: "", qty: 1 },
    ]);
    const created = {
      id: 42,
      order_number: "ORD-260731-1234",
      public_token: "token-value-123456",
      status: "new",
      source: "website",
      customer_phone: "0591234567",
      address: "Ramallah server address",
      customer_notes: "Server note",
      customer_name: "سارة أحمد",
      delivery_area_name: "رام الله",
      delivery_fee: 20,
      subtotal: 100,
      discount: 0,
      total: 120,
      coupon_code: null,
      payment_method: "cash_on_delivery",
      created_at: "2026-07-31T10:00:00Z",
      items: [{ id: 1, product_name: "ريزن شفاف", quantity: 1, unit_price: 100, line_total: 100 }],
    };
    const calls = stubApi({
      ...storefrontRoutes,
      "POST /api/v1/cart/price": {
        lines: [],
        subtotal: 100,
        discount: 0,
        delivery_fee: 20,
        total: 120,
        coupon_code: null,
        delivery_area_name: "رام الله",
      },
      "POST /api/v1/orders": respond(201, created),
      "/api/v1/orders/ORD-260731-1234": created,
    });
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    renderApp("/checkout");

    await userEvent.type(await screen.findByPlaceholderText("مثال: محمد أحمد"), "سارة أحمد");
    await userEvent.type(screen.getByPlaceholderText("05XXXXXXXX"), "0591234567");
    await userEvent.type(screen.getByPlaceholderText("الشارع، رقم البناية، أقرب معلم"), "رام الله، شارع الإرسال");
    // Addressed by its own label: the header search field is also a combobox.
    await userEvent.selectOptions(screen.getByLabelText(/منطقة التوصيل/), "1");
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: /تأكيد وإرسال الطلب/ }));

    expect(await screen.findByRole("heading", { name: "تم استلام طلبك بنجاح" })).toBeInTheDocument();
    expect(screen.getByText("ORD-260731-1234")).toBeInTheDocument();
    expect(cartStorage.load()).toHaveLength(0);
    const orderRequest = calls.find((call) => call.path.split("?")[0] === "/api/v1/orders");
    expect(JSON.parse(orderRequest.body).client_reference).toMatch(/^[-\w]{8,}$/);
    const lookupRequest = calls.find((call) => call.path.split("?")[0] === "/api/v1/orders/ORD-260731-1234");
    expect(lookupRequest.headers["X-Order-Token"]).toBe("token-value-123456");
    expect(open).toHaveBeenCalledTimes(1);
    const message = decodeURIComponent(open.mock.calls[0][0].split("?text=")[1]);
    expect(message).toContain("ORD-260731-1234");
    expect(message).toContain("Server note");
    open.mockRestore();
  });

  it("keeps the cart and does not open WhatsApp when order creation fails", async () => {
    cartStorage.save([
      { key: "1|", productId: 1, variantId: null, slug: "clear-resin", name: "ريزن شفاف", unit: 100, bg: "", variation: "", qty: 1 },
    ]);
    stubApi({
      ...storefrontRoutes,
      "POST /api/v1/cart/price": {
        lines: [], subtotal: 100, discount: 0, delivery_fee: 20, total: 120,
        coupon_code: null, delivery_area_name: "رام الله",
      },
      "POST /api/v1/orders": respond(500, { error: { code: "create_failed", message: "تعذر الحفظ" } }),
    });
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    renderApp("/checkout");

    await userEvent.type(await screen.findByPlaceholderText("مثال: محمد أحمد"), "سارة أحمد");
    await userEvent.type(screen.getByPlaceholderText("05XXXXXXXX"), "0591234567");
    await userEvent.type(screen.getByPlaceholderText("الشارع، رقم البناية، أقرب معلم"), "رام الله، شارع الإرسال");
    await userEvent.selectOptions(screen.getByLabelText(/منطقة التوصيل/), "1");
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: /تأكيد وإرسال الطلب/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("تعذر الحفظ");
    expect(cartStorage.load()).toHaveLength(1);
    expect(open).not.toHaveBeenCalled();
    open.mockRestore();
  });

  it("keeps the storefront usable when the API is unreachable", async () => {
    stubApi({});
    renderApp("/");

    expect(await screen.findByRole("alert")).toHaveTextContent("تعذّر تحميل بيانات المتجر");
  });
});
