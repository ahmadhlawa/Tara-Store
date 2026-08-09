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
          image_url: null,
          sort_order: 0,
        },
      ],
      "/api/v1/home-sections": [
        { id: 1, section_key: "categories", section_type: "categories", title: "أقسامنا", description: "تسوّق", sort_order: 1, config: {} },
        { id: 2, section_key: "featured", section_type: "featured_products", title: "مختارات", description: "", sort_order: 2, config: {} },
      ],
    });
    renderApp("/");

    expect(await screen.findByText("عنوان الشريحة")).toBeInTheDocument();
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

  it("renders a product page with its price, specifications and description", async () => {
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

    // Description / specifications / delivery are a real tablist at this width;
    // below 900px the same panels become an accordion.
    await userEvent.click(screen.getByRole("tab", { name: "المواصفات" }));
    expect(await screen.findByText("الوزن")).toBeInTheDocument();
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

  it("restores a saved cart on the cart page", async () => {
    cartStorage.save([
      { key: "1|", productId: 1, variantId: null, slug: "clear-resin", name: "ريزن شفاف", unit: 100, bg: "", variation: "", qty: 2 },
    ]);
    stubApi(storefrontRoutes);
    renderApp("/cart");

    expect(await screen.findByRole("heading", { name: "عربة التسوّق", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("2 منتجاً في عربتك")).toBeInTheDocument();

    // 2 × 100 ₪ appears twice by design: once as the cart line total and once as the
    // order-summary subtotal. Assert each in its own scope instead of ambiguously.
    const line = screen.getByRole("button", { name: "إزالة المنتج" }).closest("div");
    expect(within(line).getByText("200 ₪")).toBeInTheDocument();

    // In the summary it is both the subtotal and the total, since delivery is only
    // priced at checkout. Assert each labelled row separately.
    const summary = screen.getByRole("complementary");
    const subtotalRow = within(summary).getByText("المجموع الفرعي").closest("div");
    expect(within(subtotalRow).getByText("200 ₪")).toBeInTheDocument();
    const totalRow = within(summary).getByText("الإجمالي").closest("div");
    expect(within(totalRow).getByText("200 ₪")).toBeInTheDocument();
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

    const submit = await screen.findByRole("button", { name: /تأكيد الطلب/ });
    await userEvent.click(submit);

    expect(await screen.findAllByText("الرجاء إدخال الاسم الكامل")).not.toHaveLength(0);
    expect(screen.getByText("رقم هاتف غير صالح — مثال 0591234567")).toBeInTheDocument();
    expect(screen.getByText("اختر منطقة التوصيل")).toBeInTheDocument();
    expect(screen.getByText("يجب الموافقة على الشروط قبل إتمام الطلب")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("الرجاء إدخال الاسم الكامل");
    expect(screen.getByPlaceholderText("مثال: سارة أحمد")).toHaveFocus();
    expect(calls.some((call) => call.path === "/api/v1/orders")).toBe(false);
  });

  it("makes an unchecked terms agreement visible and focusable after a valid checkout click", async () => {
    cartStorage.save([
      { key: "1|", productId: 1, variantId: null, slug: "clear-resin", name: "ريزن شفاف", unit: 100, bg: "", variation: "", qty: 1 },
    ]);
    const calls = stubApi({
      ...storefrontRoutes,
      "POST /api/v1/cart/price": {
        lines: [], subtotal: 100, discount: 0, delivery_fee: 20, total: 120,
        coupon_code: null, delivery_area_name: "رام الله",
      },
      "POST /api/v1/orders": respond(500, { error: { code: "must_not_submit", message: "must not be called" } }),
    });
    renderApp("/checkout");

    await userEvent.type(await screen.findByPlaceholderText("مثال: سارة أحمد"), "سارة أحمد");
    await userEvent.type(screen.getByPlaceholderText("05XXXXXXXX"), "0591234567");
    await userEvent.type(screen.getByPlaceholderText("الشارع، رقم البناية، أقرب معلم"), "رام الله، شارع الإرسال");
    await userEvent.selectOptions(screen.getByLabelText(/منطقة التوصيل/), "1");
    await userEvent.click(screen.getByRole("button", { name: /تأكيد الطلب/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("يجب الموافقة على الشروط قبل إتمام الطلب");
    expect(screen.getByRole("checkbox")).toHaveFocus();
    expect(calls.some((call) => call.path === "/api/v1/orders")).toBe(false);
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

    await userEvent.type(await screen.findByPlaceholderText("مثال: سارة أحمد"), "سارة أحمد");
    await userEvent.type(screen.getByPlaceholderText("05XXXXXXXX"), "0591234567");
    await userEvent.type(screen.getByPlaceholderText("الشارع، رقم البناية، أقرب معلم"), "رام الله، شارع الإرسال");
    // Addressed by its own label: the header search field is also a combobox.
    await userEvent.selectOptions(screen.getByLabelText(/منطقة التوصيل/), "1");
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: /تأكيد الطلب/ }));

    expect(await screen.findByRole("heading", { name: "تم استلام طلبك بنجاح" })).toBeInTheDocument();
    expect(screen.getByText("ORD-260731-1234")).toBeInTheDocument();
    expect(cartStorage.load()).toHaveLength(0);
    const orderRequest = calls.find((call) => call.path === "/api/v1/orders");
    expect(JSON.parse(orderRequest.body).client_reference).toMatch(/^[-\w]{8,}$/);
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

    await userEvent.type(await screen.findByPlaceholderText("مثال: سارة أحمد"), "سارة أحمد");
    await userEvent.type(screen.getByPlaceholderText("05XXXXXXXX"), "0591234567");
    await userEvent.type(screen.getByPlaceholderText("الشارع، رقم البناية، أقرب معلم"), "رام الله، شارع الإرسال");
    await userEvent.selectOptions(screen.getByLabelText(/منطقة التوصيل/), "1");
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: /تأكيد الطلب/ }));

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
