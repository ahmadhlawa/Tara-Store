import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStorage } from "../storage/authStorage.js";
import { page, renderApp, stubApi } from "./utils.jsx";

const manager = { id: 1, email: "owner@example.com", full_name: "مالك المتجر", role: "super_admin" };
const admin = { ...manager, role: "admin" };
const product = { id: 7, name: "راتنج شفاف", sku: "RES-1000", price: "12.50" };
const dashboard = { products_total: 0, products_active: 0, categories_total: 0, coupons_active: 0, orders_total: 0, orders_pending: 0, revenue_total: 0, low_stock_products: 0, recent_orders: [] };
const mixedOfflineOrder = {
  id: 18, order_number: "ORD-18", source: "whatsapp", status: "ready", is_locked: false,
  customer_name: "سارة أحمد", customer_phone: "0591234567", customer_email: null, address: "رام الله، شارع الإرسال 10",
  payment_method: "cash_on_delivery", payment_status: "unpaid", customer_notes: null, admin_notes: null,
  discount: "0.00", delivery_fee: "0.00", created_at: "2026-08-04T10:00:00Z", activities: [],
  items: [
    { id: 71, item_kind: "catalog", product_id: 7, variant_id: null, product_name: "راتنج شفاف", sku: "RES-1000", quantity: 1, unit_price: "12.50", line_total: "12.50" },
    { id: 72, item_kind: "manual", product_id: null, variant_id: null, product_name: "Custom Wedding Card", manual_description: "Gold foil", quantity: 10, unit_price: "5.00", line_total: "50.00" },
  ],
};

describe("manual order workspace", () => {
  it("keeps the manager-only manual-order navigation and route unavailable to a normal admin", async () => {
    authStorage.save("admin-token", admin);
    stubApi({ "/api/v1/auth/me": admin, "/api/v1/admin/dashboard": dashboard });

    renderApp("/admin/orders/manual");

    expect(await screen.findByRole("heading", { name: "لوحة التحكم" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "طلب يدوي جديد" })).not.toBeInTheDocument();
  });

  it("searches the paginated catalog before adding a product line", async () => {
    authStorage.save("manager-token", manager);
    const calls = stubApi({ "/api/v1/auth/me": manager, "/api/v1/admin/products": page([product]) });
    renderApp("/admin/orders/manual");

    await userEvent.type(await screen.findByLabelText("بحث في الكتالوج"), "راتنج");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => expect(calls.some((call) => new URL(`http://test${call.path}`).searchParams.get("q") === "راتنج")).toBe(true));
  });

  it("loads configured choices and applies their catalog price", async () => {
    authStorage.save("manager-token", manager);
    stubApi({
      "/api/v1/auth/me": manager,
      "/api/v1/admin/products": page([product]),
      "/api/v1/admin/products/7": {
        ...product, track_inventory: false, variants: [],
        options: [{ id: 10, name: "الحجم", affects_price: true, values: [{ id: 11, value: "كبير", price_override: "90.00" }] }],
      },
    });
    renderApp("/admin/orders/manual");

    await userEvent.selectOptions(await screen.findByLabelText("إضافة منتج من الكتالوج"), "7");
    await userEvent.selectOptions(await screen.findByLabelText("الحجم"), "11");
    await userEvent.click(screen.getByRole("button", { name: "إضافة المنتج" }));

    expect(screen.getByText("الحجم: كبير")).toBeInTheDocument();
    expect(screen.getByLabelText("سعر الصنف 1")).toHaveValue("90.00");
  });

  it("allows an optional standalone choice to remain empty at the base price", async () => {
    authStorage.save("manager-token", manager);
    stubApi({
      "/api/v1/auth/me": manager,
      "/api/v1/admin/products": page([product]),
      "/api/v1/admin/products/7": {
        ...product, price: "70.00", track_inventory: false, variants: [],
        options: [{ id: 10, name: "إضافات", affects_price: true, values: [{ id: 11, value: "30", price_override: "100.00" }] }],
      },
    });
    renderApp("/admin/orders/manual");

    await userEvent.selectOptions(await screen.findByLabelText("إضافة منتج من الكتالوج"), "7");
    expect(await screen.findByText("إضافات (اختياري)")).toBeInTheDocument();
    const add = screen.getByRole("button", { name: "إضافة المنتج" });
    expect(add).toBeEnabled();
    await userEvent.click(add);

    expect(screen.getByLabelText("سعر الصنف 1")).toHaveValue("70.00");
  });

  it("blocks a variant-backed required option until a valid variant is selected", async () => {
    authStorage.save("manager-token", manager);
    stubApi({
      "/api/v1/auth/me": manager,
      "/api/v1/admin/products": page([product]),
      "/api/v1/admin/products/7": {
        ...product, price: "70.00", track_inventory: true, stock_quantity: 5,
        options: [{ id: 10, name: "الحجم", values: [{ id: 11, value: "كبير" }] }],
        variants: [{ id: 20, title: "كبير", option_value_ids: [11], price_override: "90.00", stock_quantity: 5, is_active: true }],
      },
    });
    renderApp("/admin/orders/manual");

    await userEvent.selectOptions(await screen.findByLabelText("إضافة منتج من الكتالوج"), "7");
    expect(await screen.findByText("الحجم *")).toBeInTheDocument();
    const add = screen.getByRole("button", { name: "إضافة المنتج" });
    expect(add).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("الحجم"), "11");
    expect(add).toBeEnabled();
  });

  it("lets a manager save a mixed manual order with customer, source, totals, notes, and completion", async () => {
    authStorage.save("manager-token", manager);
    const calls = stubApi({
      "/api/v1/auth/me": manager,
      "/api/v1/admin/products": page([product]),
      "/api/v1/admin/products/7": { ...product, options: [], variants: [], track_inventory: false },
      "POST /api/v1/admin/orders/manual": { id: 18, order_number: "ORD-18" },
    });
    renderApp("/admin/orders/manual");

    expect(await screen.findByRole("heading", { name: "طلب يدوي جديد" })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("اسم العميل"), "سارة أحمد");
    await userEvent.type(screen.getByLabelText("الهاتف"), "0591234567");
    await userEvent.type(screen.getByLabelText("العنوان"), "رام الله، شارع الإرسال 10");
    await userEvent.selectOptions(screen.getByLabelText("إضافة منتج من الكتالوج"), "7");
    await userEvent.click(screen.getByRole("button", { name: "إضافة المنتج" }));
    await userEvent.click(screen.getByRole("button", { name: "إضافة صنف يدوي" }));
    await userEvent.type(screen.getByLabelText("اسم الصنف اليدوي 2"), "تغليف هدية");
    await userEvent.type(screen.getByLabelText("سعر الصنف اليدوي 2"), "2.50");
    await userEvent.clear(screen.getByLabelText("الخصم"));
    await userEvent.type(screen.getByLabelText("الخصم"), "1.00");
    await userEvent.type(screen.getByLabelText("ملاحظات العميل"), "اتصال قبل التوصيل");
    await userEvent.type(screen.getByLabelText("ملاحظات داخلية"), "دخلها المدير");
    await userEvent.click(screen.getByLabelText("إتمام الطلب وإصدار فاتورة"));
    await userEvent.clear(screen.getByLabelText("المبلغ المدفوع"));
    await userEvent.type(screen.getByLabelText("المبلغ المدفوع"), "5.00");
    await userEvent.type(screen.getByLabelText("تفاصيل الدفع"), "تحويل بنكي");
    await userEvent.click(screen.getByRole("button", { name: "حفظ الطلب اليدوي" }));

    const created = calls.find((call) => call.method === "POST" && call.path === "/api/v1/admin/orders/manual");
    expect(JSON.parse(created.body)).toMatchObject({
      source: "whatsapp", customer_name: "سارة أحمد", customer_phone: "0591234567", discount: "1.00",
      customer_notes: "اتصال قبل التوصيل", admin_notes: "دخلها المدير",
      items: [
        { kind: "catalog", product_id: 7, quantity: 1, unit_price: "12.50" },
        { kind: "manual", name: "تغليف هدية", quantity: 1, unit_price: "2.50" },
      ],
      completion: { paid_amount: "5.00", payment_details: "تحويل بنكي" },
    });
  }, 15000);

  it("lets only a manager structurally edit an eligible offline order while preserving its mixed item payload", async () => {
    authStorage.save("manager-token", manager);
    const calls = stubApi({
      "/api/v1/auth/me": manager,
      "/api/v1/admin/orders/18": mixedOfflineOrder,
      "/api/v1/admin/products": page([product]),
      "PATCH /api/v1/admin/orders/18": mixedOfflineOrder,
    });
    renderApp("/admin/orders/18");

    expect(await screen.findByRole("heading", { name: "تعديل الطلب" })).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("كمية راتنج شفاف"));
    await userEvent.type(screen.getByLabelText("كمية راتنج شفاف"), "2");
    await userEvent.clear(screen.getByLabelText("كمية Custom Wedding Card"));
    await userEvent.type(screen.getByLabelText("كمية Custom Wedding Card"), "15");
    await userEvent.clear(screen.getByLabelText("سعر Custom Wedding Card"));
    await userEvent.type(screen.getByLabelText("سعر Custom Wedding Card"), "6.00");
    await userEvent.type(screen.getByLabelText("سبب التعديل *"), "تصحيح الطلب");
    await userEvent.click(screen.getByRole("button", { name: "حفظ التعديلات" }));

    const request = calls.find((call) => call.method === "PATCH" && call.path === "/api/v1/admin/orders/18");
    expect(JSON.parse(request.body).items).toEqual([
      { kind: "catalog", product_id: 7, variant_id: null, selected_option_value_ids: [], quantity: 2, unit_price: "12.50" },
      { kind: "manual", order_item_id: 72, name: "Custom Wedding Card", description: "Gold foil", quantity: 15, unit_price: "6.00" },
    ]);
  }, 15000);

  it("does not show structural editing for a normal admin on the same offline order", async () => {
    authStorage.save("admin-token", admin);
    stubApi({ "/api/v1/auth/me": admin, "/api/v1/admin/orders/18": mixedOfflineOrder });
    renderApp("/admin/orders/18");

    await screen.findByLabelText("واتساب مع سارة أحمد");
    expect(screen.queryByRole("heading", { name: "تعديل الطلب" })).not.toBeInTheDocument();
  });

  it("requires a manager reason before reopening a completed order and shows the replaced-invoice warning", async () => {
    authStorage.save("manager-token", manager);
    const completed = { id: 8, order_number: "ORD-8", source: "website", status: "completed", is_locked: true, customer_name: "سارة أحمد", customer_phone: "0591234567", address: "رام الله", payment_method: "cash_on_delivery", payment_status: "paid", discount: "0.00", delivery_fee: "0.00", items: [], created_at: "2026-08-04T10:00:00Z", active_invoice: { id: 2, invoice_number: "INV-8", status: "active", issued_at: "2026-08-04T10:00:00Z" }, invoices: [{ id: 2, invoice_number: "INV-8", status: "active", issued_at: "2026-08-04T10:00:00Z" }], activities: [] };
    const reopened = { ...completed, status: "preparing", is_locked: false, active_invoice: null, invoices: [{ ...completed.invoices[0], status: "replaced" }] };
    const calls = stubApi({ "/api/v1/auth/me": manager, "/api/v1/admin/orders/8": completed, "POST /api/v1/admin/orders/8/reopen": reopened });
    renderApp("/admin/orders/8");

    expect(await screen.findByText(/سيتم استبدال الفاتورة النشطة INV-8/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "INV-8" })).toHaveAttribute("href", "/admin/invoices/INV-8");
    await userEvent.type(screen.getByLabelText("سبب إعادة الفتح"), "تصحيح عنوان التوصيل");
    await userEvent.click(screen.getByRole("button", { name: "إعادة فتح الطلب" }));
    expect(screen.getByRole("dialog", { name: "تأكيد إعادة فتح الطلب" })).toBeInTheDocument();
    expect(screen.getByLabelText("سبب إعادة الفتح")).toHaveValue("تصحيح عنوان التوصيل");
    expect(calls.find((call) => call.method === "POST" && call.path === "/api/v1/admin/orders/8/reopen")).toBeUndefined();
    await userEvent.click(screen.getByRole("button", { name: "تأكيد إعادة الفتح" }));

    const request = calls.find((call) => call.method === "POST" && call.path === "/api/v1/admin/orders/8/reopen");
    expect(JSON.parse(request.body)).toEqual({ reason: "تصحيح عنوان التوصيل" });
  });
});
