import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { page, renderApp, respond, stubApi } from "./utils.jsx";
import { authStorage } from "../storage/authStorage.js";
import { api, setAuthToken, setUnauthorizedHandler } from "../api/client.js";

const ADMIN = {
  id: 1,
  email: "owner@example.com",
  full_name: "مالك المتجر",
  role: "super_admin",
  is_active: true,
  created_at: "2026-07-01T00:00:00Z",
  last_login_at: null,
};

const DASHBOARD = {
  products_total: 3,
  products_active: 2,
  categories_total: 1,
  articles_published: 0,
  coupons_active: 1,
  orders_total: 4,
  orders_pending: 1,
  orders_by_status: { pending: 1 },
  revenue_total: 500,
  low_stock_products: 0,
  recent_orders: [],
};

const signedIn = () => authStorage.save("valid-token", ADMIN);

describe("admin workspace", () => {
  it("shows the login form with no storefront chrome", async () => {
    stubApi({});
    renderApp("/admin/login");

    expect(await screen.findByRole("heading", { name: "تسجيل دخول الإدارة" })).toBeInTheDocument();
    expect(screen.getByLabelText(/البريد الإلكتروني/)).toBeInTheDocument();
    expect(screen.getByLabelText(/كلمة المرور/)).toBeInTheDocument();
    expect(screen.queryByRole("search")).not.toBeInTheDocument();
    expect(screen.queryByText("عربة التسوّق")).not.toBeInTheDocument();
  });

  it("redirects an unauthenticated visitor away from protected admin routes", async () => {
    stubApi({});
    renderApp("/admin/products");

    expect(await screen.findByRole("heading", { name: "تسجيل دخول الإدارة" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "المنتجات" })).not.toBeInTheDocument();
  });

  it("signs in, stores the session and lands on the dashboard", async () => {
    const calls = stubApi({
      "POST /api/v1/auth/login": { access_token: "fresh-token", token_type: "bearer", expires_in_minutes: 720 },
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/dashboard": DASHBOARD,
    });
    renderApp("/admin/login");

    await userEvent.type(await screen.findByLabelText(/البريد الإلكتروني/), "owner@example.com");
    await userEvent.type(screen.getByLabelText(/كلمة المرور/), "SuperSecret!99");
    await userEvent.click(screen.getByRole("button", { name: "دخول" }));

    expect(await screen.findByRole("heading", { name: "لوحة التحكم" })).toBeInTheDocument();
    expect(authStorage.load()?.token).toBe("fresh-token");

    const meCall = calls.find((call) => call.path === "/api/v1/auth/me");
    expect(meCall.headers.Authorization).toBe("Bearer fresh-token");
  });

  it("surfaces a failed login without creating a session", async () => {
    stubApi({
      "POST /api/v1/auth/login": respond(401, {
        error: { code: "invalid_credentials", message: "البريد الإلكتروني أو كلمة المرور غير صحيحة." },
      }),
    });
    renderApp("/admin/login");

    await userEvent.type(await screen.findByLabelText(/البريد الإلكتروني/), "owner@example.com");
    await userEvent.type(screen.getByLabelText(/كلمة المرور/), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "دخول" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("غير صحيحة");
    expect(authStorage.load()).toBeNull();
  });

  it("clears an invalid stored session and returns to the login page", async () => {
    authStorage.save("stale-token", ADMIN);
    stubApi({
      "/api/v1/auth/me": respond(401, { error: { code: "not_authenticated", message: "الرجاء تسجيل الدخول." } }),
    });
    renderApp("/admin");

    expect(await screen.findByRole("heading", { name: "تسجيل دخول الإدارة" })).toBeInTheDocument();
    await waitFor(() => expect(authStorage.load()).toBeNull());
  });

  it("restores a valid session without asking to sign in again", async () => {
    signedIn();
    stubApi({ "/api/v1/auth/me": ADMIN, "/api/v1/admin/dashboard": DASHBOARD });
    renderApp("/admin");

    expect(await screen.findByRole("heading", { name: "لوحة التحكم" })).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("renders the product management route with its data", async () => {
    signedIn();
    stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/products": page([
        {
          id: 7,
          name: "ريزن شفاف",
          slug: "clear-resin",
          sku: "RES-1000",
          product_type: "standard",
          category_id: 1,
          category_name: "ريزن",
          price: 100,
          compare_at_price: null,
          cost_price: 60,
          stock_quantity: 2,
          track_inventory: true,
          low_stock_threshold: 5,
          is_active: true,
          is_featured: false,
          is_new: false,
          is_bestseller: false,
          sort_order: 0,
          primary_image_url: null,
          updated_at: "2026-07-30T09:00:00Z",
        },
      ]),
    });
    renderApp("/admin/products");

    expect(await screen.findByRole("heading", { name: "المنتجات" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "ريزن شفاف" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "منتج جديد" })).toBeInTheDocument();
  });

  it("renders the order management route with its data", async () => {
    signedIn();
    stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/orders": page([
        {
          id: 3,
          order_number: "ORD-260731-1234",
          status: "pending",
          customer_name: "سارة أحمد",
          customer_phone: "0591234567",
          delivery_area_name: "رام الله",
          total: 120,
          payment_method: "cash_on_delivery",
          items_count: 2,
          created_at: "2026-07-31T10:00:00Z",
        },
      ]),
    });
    renderApp("/admin/orders");

    expect(await screen.findByRole("heading", { name: "الطلبات" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "ORD-260731-1234" })).toBeInTheDocument();

    // The label also exists as an <option> in the status filter, so scope the assertion
    // to the order row's status badge inside the table.
    expect(within(screen.getByRole("table")).getByText("بانتظار المراجعة")).toBeInTheDocument();
  });

  it("offers searchable order filters and a WhatsApp customer action", async () => {
    signedIn();
    stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/orders": page([{
        id: 9,
        order_number: "ORD-260804-009",
        status: "preparing",
        source: "website",
        customer_name: "سارة أحمد",
        customer_phone: "059-123 4567",
        delivery_area_name: "رام الله",
        total: 120,
        payment_method: "cash_on_delivery",
        payment_status: "unpaid",
        items_count: 2,
        created_at: "2026-08-04T10:00:00Z",
      }]),
    });
    renderApp("/admin/orders");

    expect(await screen.findByLabelText("المصدر")).toBeInTheDocument();
    expect(screen.getByLabelText("حالة الدفع")).toBeInTheDocument();
    expect(screen.getByLabelText("من تاريخ")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "واتساب مع سارة أحمد" })).toHaveAttribute("href", "https://wa.me/0591234567");
  });

  it("hides super-admin-only navigation from a normal admin", async () => {
    authStorage.save("valid-token", { ...ADMIN, role: "admin" });
    stubApi({
      "/api/v1/auth/me": { ...ADMIN, role: "admin" },
      "/api/v1/admin/dashboard": DASHBOARD,
    });
    renderApp("/admin");

    expect(await screen.findByRole("heading", { name: "لوحة التحكم" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "المنتجات" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "حسابات الإدارة" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "سجل التغييرات" })).not.toBeInTheDocument();
  });
});

describe("api client", () => {
  it("only attaches the bearer token to authenticated calls", async () => {
    const calls = stubApi({ "/api/v1/store/settings": {}, "/api/v1/admin/dashboard": {} });
    setAuthToken("secret-token");

    await api.get("/store/settings");
    await api.get("/admin/dashboard", { auth: true });

    expect(calls[0].headers.Authorization).toBeUndefined();
    expect(calls[1].headers.Authorization).toBe("Bearer secret-token");
    setAuthToken(null);
  });

  it("raises the API error shape and notifies the unauthorized handler", async () => {
    stubApi({
      "/api/v1/admin/dashboard": respond(401, {
        error: { code: "not_authenticated", message: "الرجاء تسجيل الدخول." },
      }),
    });
    setAuthToken("expired");
    let signedOut = false;
    setUnauthorizedHandler(() => {
      signedOut = true;
    });

    await expect(api.get("/admin/dashboard", { auth: true })).rejects.toMatchObject({
      status: 401,
      code: "not_authenticated",
      message: "الرجاء تسجيل الدخول.",
    });
    expect(signedOut).toBe(true);

    setUnauthorizedHandler(null);
    setAuthToken(null);
  });

  it("reports an unreachable server as a network error instead of throwing raw", async () => {
    globalThis.fetch = () => Promise.reject(new TypeError("failed to fetch"));
    await expect(api.get("/store/settings")).rejects.toMatchObject({ code: "network_error" });
  });
});
