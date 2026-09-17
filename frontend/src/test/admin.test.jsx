import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { page, renderApp, respond, stubApi } from "./utils.jsx";
import { authStorage } from "../storage/authStorage.js";
import { api, setAuthToken, setUnauthorizedHandler } from "../api/client.js";
import { CategoriesPage, orderCategoriesForAdmin, reorderedSiblingIds } from "../admin/pages/CatalogScreens.jsx";
import { HeroSlidesPage } from "../admin/pages/ContentScreens.jsx";
import { orderAxisTicks, salesAxisTicks } from "../admin/pages/DashboardPage.jsx";

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
  coupons_active: 1,
  orders_total: 4,
  orders_pending: 1,
  orders_by_status: { pending: 1 },
  revenue_total: 500,
  low_stock_products: 0,
  monthly_sales: 500,
  previous_month_sales: 0,
  recent_orders_total: 4,
  recent_orders_by_status: { new: 4 },
  average_order_value: 125,
  best_sales_day: null,
  sales_by_day: [],
  orders_by_day: [],
  low_stock_items: [],
  recent_orders: [],
};

const signedIn = () => authStorage.save("valid-token", ADMIN);

describe("dashboard chart scales", () => {
  it("uses readable daily-sales ticks rather than the period total", () => {
    expect(salesAxisTicks([83])).toEqual([0, 50, 100]);
    expect(salesAxisTicks([83, 305])).toEqual([0, 100, 200, 300, 400]);
    expect(salesAxisTicks([0])).toEqual([0, 1]);
  });

  it("uses unique integer order ticks for empty, small, and larger series", () => {
    expect(orderAxisTicks([0])).toEqual([0, 1]);
    expect(orderAxisTicks([1])).toEqual([0, 1]);
    expect(orderAxisTicks([2])).toEqual([0, 1, 2]);
    expect(orderAxisTicks([3])).toEqual([0, 1, 2, 3]);
    expect(orderAxisTicks([7])).toEqual([0, 2, 4, 6, 8]);
    expect(orderAxisTicks([11])).toEqual([0, 5, 10, 15]);
  });
});

describe("admin category hierarchy", () => {
  const categories = [
    { id: 2, name: "شمعة المشروبات", slug: "drinks", parent_id: 1, product_count: 1 },
    { id: 3, name: "Crochet", slug: "crochet", parent_id: null, product_count: 0 },
    { id: 1, name: "Candles", slug: "candles", parent_id: null, product_count: 2 },
    { id: 4, name: "شمعة أخرى", slug: "other", parent_id: 1, product_count: 0 },
  ];

  it("renders the exact Admin categories route and creates a category", async () => {
    signedIn();
    const calls = stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/categories": page(categories),
      "POST /api/v1/admin/categories": { id: 5, name: "New category" },
    });
    renderApp("/admin/categories");
    expect(await screen.findByText("Candles")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "إضافة قسم" }));
    await userEvent.type(screen.getByLabelText("اسم القسم"), "New category");
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(calls.some((call) => call.method === "POST" && JSON.parse(call.body).name === "New category")).toBe(true));
  });

  it("groups each child directly under its parent without duplicates", () => {
    const ordered = orderCategoriesForAdmin(categories);
    expect(ordered.map((category) => category.id)).toEqual([1, 2, 4, 3]);
    expect(ordered.map((category) => category.__categoryDepth)).toEqual([0, 1, 1, 0]);
    expect(new Set(ordered.map((category) => category.id)).size).toBe(categories.length);
  });

  it("reorders only categories with the same parent", () => {
    expect(reorderedSiblingIds(categories, 4, 2)).toEqual({ parentId: 1, categoryIds: [4, 2] });
    expect(reorderedSiblingIds(categories, 2, 3)).toBeNull();
  });

  it("persists a sibling drag in the displayed order", async () => {
    const calls = stubApi({
      "/api/v1/admin/categories": page(categories),
      "PUT /api/v1/admin/categories/reorder": [categories[3], categories[0]],
    });
    render(<CategoriesPage />);
    const source = await screen.findByRole("button", { name: `اسحب لترتيب ${categories[3].name}` });
    const target = screen.getByRole("button", { name: `اسحب لترتيب ${categories[0].name}` });
    const values = new Map();
    const dataTransfer = {
      effectAllowed: "move",
      setData: (type, value) => values.set(type, value),
      getData: (type) => values.get(type) || "",
    };
    fireEvent.dragStart(source, { dataTransfer });
    fireEvent.dragOver(target, { dataTransfer });
    fireEvent.drop(target, { dataTransfer });

    await waitFor(() => expect(calls.some((call) =>
      call.method === "PUT" && JSON.parse(call.body).category_ids.join(",") === "4,2",
    )).toBe(true));
  });

  it("renders indented child labels while preserving row actions", async () => {
    const calls = stubApi({
      "/api/v1/admin/categories": page(categories),
      "PATCH /api/v1/admin/categories/1": { ...categories[2], show_on_home: true },
    });
    render(<CategoriesPage />);

    const child = await screen.findByText("شمعة المشروبات");
    expect(child.parentElement).toHaveStyle({ paddingInlineStart: "22px", fontWeight: "500" });
    expect(screen.getAllByRole("button", { name: "تعديل" })).toHaveLength(4);
    expect(screen.getAllByRole("button", { name: "حذف" })).toHaveLength(4);

    await userEvent.click(within(screen.getByText("Candles").closest("tr")).getByRole("button", { name: "تعديل" }));
    const homeToggle = within(screen.getByRole("dialog")).getByLabelText("عرض في الصفحة الرئيسية");
    await userEvent.click(homeToggle);
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(calls.some((call) =>
      call.method === "PATCH" && JSON.parse(call.body).show_on_home === true,
    )).toBe(true));
  });
});

describe("admin hero slides", () => {
  it("creates with the displayed root default, edits and reloads the saved target", async () => {
    let slides = [];
    const calls = stubApi({
      "/api/v1/admin/categories": page([
        { id: 2, name: "Child", slug: "child", parent_id: 1 },
        { id: 1, name: "Candles", slug: "candles", parent_id: null, is_active: true },
        { id: 3, name: "Crochet", slug: "crochet", parent_id: null, is_active: true },
      ]),
      "/api/v1/admin/hero-slides": () => slides,
      "POST /api/v1/admin/hero-slides": ({ init }) => {
        slides = [{ id: 1, ...JSON.parse(init.body) }];
        return slides[0];
      },
      "PATCH /api/v1/admin/hero-slides/1": ({ init }) => {
        slides = [{ ...slides[0], ...JSON.parse(init.body) }];
        return slides[0];
      },
    });
    const view = render(<HeroSlidesPage />);
    await userEvent.click(screen.getByRole("button", { name: "إضافة شريحة" }));
    await userEvent.click(screen.getByRole("button", { name: "إدخال رابط صورة يدويًا" }));
    await userEvent.type(screen.getByLabelText(/رابط يدوي/), "/media/hero.png");
    await userEvent.selectOptions(screen.getByLabelText("وجهة الإعلان"), "category");
    const selector = screen.getByLabelText("القسم");
    expect(within(selector).queryByRole("option", { name: "Child" })).not.toBeInTheDocument();
    expect(selector).toHaveValue("candles");
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "حفظ" }));
    await screen.findByRole("button", { name: "تعديل" });
    expect(JSON.parse(calls.find((call) => call.method === "POST").body).target_slug).toBe("candles");
    await userEvent.click(screen.getByRole("button", { name: "تعديل" }));
    await userEvent.selectOptions(screen.getByLabelText("القسم"), "crochet");
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    view.unmount();
    render(<HeroSlidesPage />);
    await userEvent.click(await screen.findByRole("button", { name: "تعديل" }));
    await waitFor(() => expect(screen.getByLabelText("القسم")).toHaveValue("crochet"));
  });
});

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
    expect(within(screen.getByRole("heading", { name: "أحدث الطلبات" }).closest("section")).getAllByText("4").length).toBeGreaterThan(0);
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
          status: "new",
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
    expect(within(screen.getByRole("table")).getByText("طلب جديد")).toBeInTheDocument();
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
