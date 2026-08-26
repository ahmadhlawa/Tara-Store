import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { page, renderApp, respond, storefrontRoutes, stubApi } from "./utils.jsx";
import { authStorage } from "../storage/authStorage.js";
import { cartStorage } from "../storage/cartStorage.js";

const ADMIN = {
  id: 1,
  email: "owner@example.com",
  full_name: "مالك المتجر",
  role: "super_admin",
  is_active: true,
  created_at: "2026-08-01T00:00:00Z",
  last_login_at: null,
};

const signedIn = () => authStorage.save("valid-token", ADMIN);

const INVOICE_ROW = {
  id: 5,
  invoice_number: "INV-000001",
  order_id: 3,
  order_number: "ORD-260801-1234",
  customer_name: "سارة أحمد",
  customer_phone: "0591234567",
  issued_at: "2026-08-01T10:00:00Z",
  grand_total: 220,
  currency_symbol: "₪",
  payment_method: "cash_on_delivery",
  status: "active",
  payment_status: "unpaid",
  paid_amount: 0,
  remaining_amount: 220,
};

const INVOICE = {
  ...INVOICE_ROW,
  customer_email: "sara@example.com",
  customer_notes: "اتصلوا قبل التوصيل",
  store_name: "متجر فيستا",
  store_phone: "0590000000",
  store_whatsapp: null,
  store_email: null,
  store_address: "رام الله",
  store_logo_url: null,
  legal_business_name: null,
  registration_number: null,
  tax_number: null,
  delivery_address: "رام الله، شارع الإرسال، بناية ٥",
  delivery_area_name: "رام الله",
  currency_code: "ILS",
  subtotal: 200,
  discount: 0,
  coupon_code: null,
  delivery_fee: 20,
  tax_enabled: false,
  tax_rate: 0,
  prices_include_tax: false,
  tax_amount: 0,
  payment_status: "unpaid",
  paid_amount: 0,
  refunded_amount: 0,
  remaining_amount: 220,
  payment_details: null,
  activities: [{ id: 1, event_type: "invoice_issued", reason: null, created_at: "2026-08-01T10:00:00Z" }],
  history: [],
  replacement_invoice: null,
  replaces_invoice: null,
  cancelled_at: null,
  cancellation_reason: null,
  cancelled_by_admin_id: null,
  items: [
    {
      id: 1,
      product_name: "ريزن شفاف",
      sku: "RES-1000",
      variant_description: "١ كغم",
      unit_price: 100,
      quantity: 2,
      line_total: 200,
    },
  ],
};

const CANCELLED = {
  ...INVOICE,
  status: "cancelled",
  cancelled_at: "2026-08-02T09:00:00Z",
  cancellation_reason: "نفدت الكمية",
  cancelled_by_admin_id: 1,
};

const ORDER = {
  id: 3,
  order_number: "ORD-260801-1234",
  status: "confirmed",
  customer_name: "سارة أحمد",
  customer_phone: "0591234567",
  customer_email: null,
  address: "رام الله، شارع الإرسال، بناية ٥",
  delivery_area_id: 1,
  delivery_area_name: "رام الله",
  delivery_fee: 20,
  subtotal: 200,
  discount: 0,
  total: 220,
  coupon_code: null,
  payment_method: "cash_on_delivery",
  customer_notes: null,
  admin_notes: null,
  created_at: "2026-08-01T09:00:00Z",
  updated_at: "2026-08-01T10:00:00Z",
  items: [],
  status_history: [],
  invoice: {
    id: 5,
    invoice_number: "INV-000001",
    status: "issued",
    issued_at: "2026-08-01T10:00:00Z",
    grand_total: 220,
  },
};

describe("admin invoice list", () => {
  it("lists invoices with every column the screen promises", async () => {
    signedIn();
    stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/invoices": page([INVOICE_ROW]),
    });
    renderApp("/admin/invoices");

    expect(await screen.findByRole("heading", { name: "أرشيف الفواتير" })).toBeInTheDocument();
    const table = await screen.findByRole("table");
    const row = within(table);

    expect(row.getByRole("link", { name: "INV-000001" })).toBeInTheDocument();
    expect(row.getByRole("link", { name: "ORD-260801-1234" })).toBeInTheDocument();
    expect(row.getByText("سارة أحمد")).toBeInTheDocument();
    expect(row.getByText("220.00 ₪")).toBeInTheDocument();
    expect(row.getByText("غير مدفوع")).toBeInTheDocument();
    expect(row.getByText("نشطة")).toBeInTheDocument();
    expect(row.getByRole("button", { name: "عرض" })).toBeInTheDocument();
  });

  it("passes the search term and filters through to the API", async () => {
    signedIn();
    const calls = stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/invoices": page([INVOICE_ROW]),
    });
    renderApp("/admin/invoices");

    await screen.findByRole("table");
    await userEvent.type(screen.getByLabelText("بحث في الفواتير"), "INV-1");
    await userEvent.selectOptions(screen.getByLabelText("حالة الفاتورة"), "cancelled");

    await waitFor(() => {
      const last = calls.filter((call) => call.path.includes("/admin/invoices")).at(-1);
      expect(last.path).toContain("q=INV-1");
      expect(last.path).toContain("status=cancelled");
    });
  });

  it("explains the empty state instead of showing a bare table", async () => {
    signedIn();
    stubApi({ "/api/v1/auth/me": ADMIN, "/api/v1/admin/invoices": page([]) });
    renderApp("/admin/invoices");

    expect(await screen.findByText("لا توجد فواتير مطابقة للبحث.")).toBeInTheDocument();
  });

  it("keeps the invoice screens behind authentication", async () => {
    stubApi({});
    renderApp("/admin/invoices");

    expect(await screen.findByRole("heading", { name: "تسجيل دخول الإدارة" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "أرشيف الفواتير" })).not.toBeInTheDocument();
  });
});

describe("admin invoice detail", () => {
  it("renders an internal archive detail with final prices, activity and replacement links", async () => {
    signedIn();
    stubApi({ "/api/v1/auth/me": ADMIN, "/api/v1/admin/invoices/INV-000001": { ...INVOICE, replacement_invoice: { id: 6, invoice_number: "INV-000002", status: "active", issued_at: "2026-08-02T10:00:00Z" } } });
    renderApp("/admin/invoices/INV-000001");

    expect(await screen.findByRole("heading", { name: /INV-000001/ })).toBeInTheDocument();
    expect(screen.getByLabelText("ملخص الأسعار النهائية")).toHaveTextContent("220.00");
    expect(screen.getByText("سجل النشاط")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /INV-000002/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /طباعة|PDF|مشاركة/ })).not.toBeInTheDocument();
  });

  it("reports a missing invoice instead of rendering an empty sheet", async () => {
    signedIn();
    stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/invoices/INV-000999": respond(404, {
        error: { code: "invoice_not_found", message: "الفاتورة غير موجودة." },
      }),
    });
    renderApp("/admin/invoices/INV-000999");

    expect(await screen.findByRole("heading", { name: "الفاتورة غير موجودة" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /طباعة|PDF|مشاركة/ })).not.toBeInTheDocument();
  });
});

describe("order detail invoice panel", () => {
  it("links to the invoice without offering a print action", async () => {
    signedIn();
    stubApi({ "/api/v1/auth/me": ADMIN, "/api/v1/admin/orders/3": ORDER });
    renderApp("/admin/orders/3");

    await screen.findByRole("heading", { name: /ORD-260801-1234/ });
    expect(screen.getByRole("heading", { name: "الفاتورة" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "INV-000001" })).toBeInTheDocument();
    expect(screen.getByText("صادرة")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "عرض الفاتورة" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /طباعة الفاتورة/ })).not.toBeInTheDocument();
    expect(screen.getByText("الدفع عند الاستلام")).toBeInTheDocument();
  });

  it("says a pending order has no invoice yet", async () => {
    signedIn();
    stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/orders/3": { ...ORDER, status: "pending", invoice: null },
    });
    renderApp("/admin/orders/3");

    await screen.findByRole("heading", { name: /ORD-260801-1234/ });
    expect(screen.getByText(/تصدر الفاتورة تلقائياً عند تغيير الحالة/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "INV-000001" })).not.toBeInTheDocument();
  });

  it("shows item and total read-only details when the order is not editable", async () => {
    signedIn();
    stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/orders/3": {
        ...ORDER,
        source: "website",
        payment_status: "unpaid",
        is_locked: false,
        completed_at: null,
        activities: [],
        items: [{ id: 1, product_id: 7, product_name: "ريزن شفاف", sku: "RES-1000", quantity: 2, unit_price: "100.00", line_total: "200.00" }],
      },
    });
    renderApp("/admin/orders/3");

    await screen.findByRole("heading", { name: /ORD-260801-1234/ });
    expect(screen.getByRole("heading", { name: "أصناف الطلب" })).toBeInTheDocument();
    expect(screen.getByText("ريزن شفاف")).toBeInTheDocument();
    expect(screen.getByLabelText("ملخص إجمالي الطلب")).toHaveTextContent("220.00");
  });

  it("hides workflow controls from a normal admin on a manager-reopened order", async () => {
    authStorage.save("valid-token", { ...ADMIN, role: "admin" });
    const normalAdmin = { ...ADMIN, role: "admin" };
    stubApi({
      "/api/v1/auth/me": normalAdmin,
      "/api/v1/admin/orders/3": { ...ORDER, source: "website", payment_status: "unpaid", is_locked: false, completed_at: "2026-08-04T10:00:00Z", status: "preparing", activities: [] },
    });
    renderApp("/admin/orders/3");

    await screen.findByRole("heading", { name: /ORD-260801-1234/ });
    expect(screen.queryByLabelText("تغيير الحالة")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("ملاحظة الحالة")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "تحديث الحالة" })).not.toBeInTheDocument();
  });
});

describe("invoice archive workflow", () => {
  it("hides linked invoices when history contains only the current invoice", async () => {
    signedIn();
    stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/invoices/INV-000001": {
        ...INVOICE,
        history: [{ id: 5, invoice_number: "INV-000001", status: "active", issued_at: "2026-08-01T10:00:00Z" }],
      },
    });
    renderApp("/admin/invoices/INV-000001");

    await screen.findByRole("heading", { name: /INV-000001/ });
    expect(screen.queryByRole("heading", { name: "الفواتير المرتبطة" })).not.toBeInTheDocument();
  });

  it("sends archive filters for payment, source and employee", async () => {
    signedIn();
    const calls = stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/invoices": page([{ ...INVOICE_ROW, status: "active", payment_status: "unpaid", paid_amount: 0, remaining_amount: 220 }]),
    });
    renderApp("/admin/invoices");

    await screen.findByRole("table");
    await userEvent.selectOptions(screen.getByLabelText("حالة الدفع"), "paid");
    await userEvent.selectOptions(screen.getByLabelText("مصدر الطلب"), "whatsapp");
    await userEvent.type(screen.getByLabelText("رقم الموظف المصدر"), "7");

    await waitFor(() => {
      const path = calls.filter((call) => call.path.includes("/admin/invoices")).at(-1).path;
      expect(path).toContain("payment_status=paid");
      expect(path).toContain("source=whatsapp");
      expect(path).toContain("employee_id=7");
    });
  });

  // Browser reproduction B1: "مستبدلة" + "مدفوع جزئيًا" answered 422 because the
  // payment option carried the non-canonical value "partial".
  it("sends canonical values for the replaced and partially-paid Arabic filter labels", async () => {
    signedIn();
    const calls = stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/invoices": page([INVOICE_ROW]),
    });
    renderApp("/admin/invoices");

    await screen.findByRole("table");
    await userEvent.selectOptions(screen.getByLabelText("حالة الفاتورة"), "replaced");
    await userEvent.selectOptions(screen.getByLabelText("حالة الدفع"), "partially_paid");

    await waitFor(() => {
      const path = calls.filter((call) => call.path.includes("/admin/invoices")).at(-1).path;
      expect(path).toContain("status=replaced");
      expect(path).toContain("payment_status=partially_paid");
      expect(path).not.toContain("payment_status=partial&");
    });
  });

  it("shows the Arabic label for a partially paid invoice instead of the raw API value", async () => {
    signedIn();
    stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/invoices": page([{ ...INVOICE_ROW, payment_status: "partially_paid" }]),
    });
    renderApp("/admin/invoices");

    const table = await screen.findByRole("table");
    expect(within(table).getByText("مدفوع جزئياً")).toBeInTheDocument();
    expect(within(table).queryByText("partially_paid")).not.toBeInTheDocument();
  });

  it("limits a normal admin to increasing payment information", async () => {
    const normalAdmin = { ...ADMIN, role: "admin" };
    authStorage.save("valid-token", normalAdmin);
    const calls = stubApi({
      "/api/v1/auth/me": normalAdmin,
      "PATCH /api/v1/admin/invoices/INV-000001/payment": { ...INVOICE, paid_amount: 100, remaining_amount: 120 },
      "/api/v1/admin/invoices/INV-000001": INVOICE,
    });
    renderApp("/admin/invoices/INV-000001");

    await screen.findByLabelText("المبلغ المدفوع");
    expect(screen.queryByLabelText("المبلغ المسترد")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("سبب التصحيح أو الاسترداد")).not.toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("المبلغ المدفوع"));
    await userEvent.type(screen.getByLabelText("المبلغ المدفوع"), "100");
    await userEvent.click(screen.getByRole("button", { name: "حفظ تحديث الدفع" }));
    await waitFor(() => expect(calls.some((call) => call.method === "PATCH")).toBe(true));
    expect(JSON.parse(calls.find((call) => call.method === "PATCH").body)).not.toHaveProperty("refunded_amount");
  });

  it("requires a manager reason for corrections and refunds", async () => {
    signedIn();
    stubApi({ "/api/v1/auth/me": ADMIN, "/api/v1/admin/invoices/INV-000001": { ...INVOICE, paid_amount: 100, remaining_amount: 120 } });
    renderApp("/admin/invoices/INV-000001");

    await screen.findByLabelText("المبلغ المسترد");
    await userEvent.clear(screen.getByLabelText("المبلغ المسترد"));
    await userEvent.type(screen.getByLabelText("المبلغ المسترد"), "20");
    await userEvent.click(screen.getByRole("button", { name: "حفظ تحديث الدفع" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("سبب التصحيح أو الاسترداد مطلوب");
  });
});

describe("storefront payment surface", () => {
  // The checkout form only renders with something in the cart.
  const withCart = () =>
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

  const cartRoutes = {
    ...storefrontRoutes,
    "POST /api/v1/cart/price": {
      lines: [
        {
          product_id: 1,
          variant_id: null,
          product_name: "ريزن شفاف",
          slug: "clear-resin",
          variant_description: null,
          unit_price: 100,
          quantity: 1,
          line_total: 100,
          primary_image_url: null,
        },
      ],
      subtotal: 100,
      discount: 0,
      delivery_fee: 20,
      total: 120,
      coupon_code: null,
      delivery_area_name: "رام الله",
    },
  };

  const withTransferInstructions = () => ({
    ...cartRoutes,
    "/api/v1/store/settings": {
      ...storefrontRoutes["/api/v1/store/settings"],
      manual_payment_instructions: "بنك فلسطين — حساب رقم 12345",
    },
  });

  it("offers only cash on delivery while the owner has published no transfer details", async () => {
    withCart();
    stubApi(cartRoutes);
    renderApp("/checkout");

    const heading = await screen.findByText("طريقة الدفع");
    const panel = within(heading.parentElement);
    expect(panel.getByText("الدفع عند الاستلام")).toBeInTheDocument();
    expect(panel.queryByText("تحويل بنكي / يدوي")).not.toBeInTheDocument();
    expect(document.querySelectorAll('input[name="pay"]').length).toBe(1);
  });

  it("keeps checkout cash-on-delivery only when legacy transfer details exist", async () => {
    withCart();
    stubApi(withTransferInstructions());
    renderApp("/checkout");

    const heading = await screen.findByText("طريقة الدفع");
    const panel = within(heading.parentElement);
    expect(panel.getByText("الدفع عند الاستلام")).toBeInTheDocument();
    expect(panel.queryByText("تحويل بنكي / يدوي")).not.toBeInTheDocument();

    // Exactly one payment option, and it is never a card or transfer flow.
    expect(document.querySelectorAll('input[name="pay"]').length).toBe(1);
    expect(screen.queryByLabelText(/رقم البطاقة/)).not.toBeInTheDocument();
    expect(screen.queryByText(/CVV/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/تاريخ الانتهاء/)).not.toBeInTheDocument();
    expect(screen.queryByText(/بطاقة ائتمان/)).not.toBeInTheDocument();
    expect(document.querySelector('input[autocomplete="cc-number"]')).toBeNull();
  });

  it("never claims a payment was taken", async () => {
    withCart();
    stubApi(cartRoutes);
    renderApp("/checkout");

    expect(
      await screen.findByText(/لا يتم تحصيل أي مبلغ الآن؛ يُدفع نقداً للمندوب عند التسليم/),
    ).toBeInTheDocument();
  });

  it("never promises transfer details the owner has not published", async () => {
    withCart();
    stubApi(cartRoutes);
    renderApp("/checkout");

    await screen.findByText("طريقة الدفع");
    expect(screen.queryByText(/حساب رقم/)).not.toBeInTheDocument();
  });

  it("does not expose legacy transfer instructions", async () => {
    withCart();
    stubApi(withTransferInstructions());
    renderApp("/checkout");

    await screen.findByText("طريقة الدفع");
    expect(screen.queryByText("بنك فلسطين — حساب رقم 12345")).not.toBeInTheDocument();
  });

  it("prefers the Arabic store name when the owner has set one", async () => {
    stubApi({
      ...storefrontRoutes,
      "/api/v1/store/settings": {
        ...storefrontRoutes["/api/v1/store/settings"],
        store_name: "Tara Store",
        store_name_ar: "متجر فيستا",
      },
    });
    renderApp("/");

    expect((await screen.findAllByText("متجر فيستا")).length).toBeGreaterThan(0);
  });
});
