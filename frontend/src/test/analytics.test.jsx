import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AnalyticsPage from "../admin/pages/AnalyticsPage.jsx";
import { adminApi } from "../api/adminApi.js";
import { productFixture, renderApp, settingsFixture, storefrontRoutes, stubApi } from "./utils.jsx";
import { StoreProvider, useStore } from "../app/StoreProvider.jsx";
import CheckoutRoutePage from "../pages/CheckoutRoutePage.jsx";
import { publicApi } from "../api/publicApi.js";
import * as analytics from "../services/analytics.js";
import { cartStorage } from "../storage/cartStorage.js";

vi.mock("../api/adminApi.js", async () => {
  const actual = await vi.importActual("../api/adminApi.js");
  return { adminApi: { ...actual.adminApi, analytics: vi.fn() } };
});

const summary = {
  period: "today",
  range_start: "2026-09-18T21:00:00",
  range_end: "2026-09-19T21:00:00",
  location_tracking_configured: true,
  sessions: 14,
  unique_visitors: 9,
  average_session_duration_seconds: 125,
  completed_orders: 3,
  funnel: { product_views: 21, add_to_cart: 28, checkout_reached: 6, order_completed: 3 },
  abandoned_carts: 4,
  top_locations: [{ name: "القدس", sessions: 5 }, { name: "الداخل", sessions: 4 }],
  top_products: [{ product_id: 1, name: "ريزن شفاف", slug: "clear-resin", views: 7, product_exists: true }],
};

beforeEach(() => {
  adminApi.analytics.mockResolvedValue(summary);
});

describe("storefront analytics tracking", () => {
  function CartActions({ tick = 0 }) {
    const store = useStore();
    return <>
      <output aria-label="cart quantity">{store.cart.reduce((sum, line) => sum + line.qty, 0)}</output>
      <output aria-label="ready">{String(store.ready)}</output>
      <button onClick={() => store.addToCart({ id: 1, name: "Test Product", slug: "clear-resin", price: 100 })}>Add</button>
      <button onClick={() => store.addToCart(null)}>Reject</button>
      <span>{tick}</span>
    </>;
  }

  const eventCalls = (calls) => calls.filter((call) => call.path.split("?")[0] === "/api/v1/analytics/event");
  const cartTree = (tick = 0) => <StrictMode><MemoryRouter><StoreProvider><CartActions tick={tick} /></StoreProvider></MemoryRouter></StrictMode>;
  const checkoutTree = (tick = 0) => <StrictMode><MemoryRouter initialEntries={["/ar/checkout"]}>
    <StoreProvider><span>{tick}</span><CheckoutRoutePage /></StoreProvider>
  </MemoryRouter></StrictMode>;

  it("records exactly one type-only event per actual cart add, never for renders or rejected adds", async () => {
    const calls = stubApi({ ...storefrontRoutes, "POST /api/v1/analytics/event": {} });
    const view = render(cartTree());
    await waitFor(() => expect(screen.getByLabelText("ready")).toHaveTextContent("true"));
    expect(eventCalls(calls)).toHaveLength(0);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Reject" }));
    expect(screen.getByLabelText("cart quantity")).toHaveTextContent("0");
    expect(eventCalls(calls)).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByLabelText("cart quantity")).toHaveTextContent("1");
    expect(eventCalls(calls).map((call) => JSON.parse(call.body))).toEqual([{ event_type: "add_to_cart" }]);
    view.rerender(cartTree(1));
    expect(eventCalls(calls)).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByLabelText("cart quantity")).toHaveTextContent("2");
    expect(eventCalls(calls).map((call) => JSON.parse(call.body))).toEqual([
      { event_type: "add_to_cart" }, { event_type: "add_to_cart" },
    ]);
    expect(cartStorage.load()[0].qty).toBe(2);
    for (const call of eventCalls(calls)) expect(call.headers).not.toHaveProperty("Authorization");
  });

  it.each(["async", "sync"])("keeps cart updates and checkout navigation working after %s analytics failure", async (failure) => {
    const calls = stubApi({ ...storefrontRoutes, "POST /api/v1/analytics/event": {} });
    expect(publicApi.analyticsEvent).toBeTypeOf("function");
    const spy = vi.spyOn(publicApi, "analyticsEvent").mockImplementation(() => {
      if (failure === "sync") throw new Error("analytics unavailable");
      return Promise.reject(new Error("analytics unavailable"));
    });
    const view = render(cartTree());
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByLabelText("cart quantity")).toHaveTextContent("1");
    expect(cartStorage.load()[0].qty).toBe(1);
    view.unmount();
    cartStorage.clear();
    renderApp("/ar/checkout");
    expect(await screen.findByRole("heading", { name: "لا توجد منتجات لإتمام الطلب" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: /تصفّح المتجر/ }));
    expect(await screen.findByRole("heading", { name: "كل المنتجات", level: 1 })).toBeInTheDocument();
    expect(spy).toHaveBeenCalledWith({ event_type: "add_to_cart" });
    expect(spy).toHaveBeenCalledWith({ event_type: "checkout_reached" });
    expect(calls.some((call) => call.path.includes("/products"))).toBe(true);
  });

  it("attempts checkout arrival once per mount including StrictMode, allows later mounts for server session dedupe", async () => {
    const calls = stubApi({ ...storefrontRoutes, "POST /api/v1/analytics/event": {} });
    const view = render(checkoutTree());
    await screen.findByRole("heading", { name: "لا توجد منتجات لإتمام الطلب" });
    expect(eventCalls(calls).map((call) => JSON.parse(call.body))).toEqual([{ event_type: "checkout_reached" }]);
    view.rerender(checkoutTree(1));
    expect(eventCalls(calls)).toHaveLength(1);
    view.unmount();
    render(checkoutTree(2));
    await screen.findByRole("heading", { name: "لا توجد منتجات لإتمام الطلب" });
    expect(eventCalls(calls).map((call) => JSON.parse(call.body))).toEqual([
      { event_type: "checkout_reached" }, { event_type: "checkout_reached" },
    ]);
  });

  it.each(["trackAddToCart", "trackCheckoutReached"])("%s returns a settled promise even for an unexpected synchronous transport failure", async (helper) => {
    expect(analytics[helper]).toBeTypeOf("function");
    vi.spyOn(publicApi, "analyticsEvent").mockImplementation(() => { throw new Error("sync transport failure"); });
    await expect(analytics[helper]()).resolves.toBeNull();
  });

  it("does not report sold-out product add attempts", async () => {
    const calls = stubApi({
      ...storefrontRoutes,
      "GET /api/v1/products/clear-resin/related": [],
      "GET /api/v1/products/clear-resin": { ...productFixture, in_stock: false, stock_quantity: 0 },
      "POST /api/v1/analytics/event": {},
    });
    renderApp("/ar/product/clear-resin");
    await screen.findByRole("heading", { name: productFixture.name, level: 1 });
    const button = screen.getByRole("button", { name: "غير متوفر حالياً" });
    expect(button).toBeDisabled();
    await userEvent.click(button);
    expect(cartStorage.load()).toHaveLength(0);
    expect(eventCalls(calls)).toHaveLength(0);
  });

  it("tracks a public route but never requires a client visitor identifier", async () => {
    const calls = stubApi({ ...storefrontRoutes, "POST /api/v1/analytics/visit": {} });
    renderApp("/ar/");
    await screen.findAllByRole("link", { name: `${settingsFixture.store_name} — الصفحة الرئيسية` });
    await waitFor(() => expect(calls.some((call) => call.path.startsWith("/api/v1/analytics/visit"))).toBe(true));
    const call = calls.find((item) => item.path.startsWith("/api/v1/analytics/visit"));
    const body = JSON.parse(call.body);
    expect(body.path).toBe("/ar/");
    expect(body).not.toHaveProperty("visitor_id");
  });

  it("records product view only after a valid PDP loads", async () => {
    const calls = stubApi({
      ...storefrontRoutes,
      "GET /api/v1/products/clear-resin/related": [],
      "GET /api/v1/products/clear-resin": productFixture,
      "POST /api/v1/analytics/visit": {},
      "POST /api/v1/analytics/product-view": {},
    });
    renderApp("/ar/product/clear-resin");
    await screen.findByRole("heading", { name: productFixture.name, level: 1 });
    await waitFor(() => expect(calls.some((call) => call.path.startsWith("/api/v1/analytics/product-view"))).toBe(true));
    const call = calls.find((item) => item.path.startsWith("/api/v1/analytics/product-view"));
    expect(JSON.parse(call.body)).toEqual({ product_id: productFixture.id });
  });
});

describe("Admin analytics page", () => {
  it("shows four summary cards with duration and website completion semantics", async () => {
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    const cards = await screen.findByTestId("analytics-summary");
    expect(cards.children).toHaveLength(4);
    expect(Array.from(cards.children).map((card) => card.querySelector("strong").textContent)).toEqual(["14", "9", "2 دقيقة و5 ثانية", "3"]);
    expect(within(cards).getByText("متوسط مدة الزيارة")).toBeInTheDocument();
    expect(within(cards).getByText("الطلبات المكتملة عبر الموقع")).toBeInTheDocument();
    expect(within(cards).getByText("طلبات أُنشئت بنجاح عبر الموقع، بغض النظر عن حالة تجهيزها لاحقاً.")).toBeInTheDocument();
    expect(within(cards).queryByText("السلات المتروكة")).not.toBeInTheDocument();
  });

  it.each([
    [undefined, "0 ثانية"], [null, "0 ثانية"], ["", "0 ثانية"], [0, "0 ثانية"],
    [-4, "0 ثانية"], ["invalid", "0 ثانية"], [Infinity, "0 ثانية"], [NaN, "0 ثانية"],
    [0.4, "0 ثانية"], [45.4, "45 ثانية"], [59.6, "1 دقيقة"], [60, "1 دقيقة"],
    [3599.6, "1 ساعة"], [3600, "1 ساعة"], [3661, "1 ساعة و1 دقيقة و1 ثانية"],
  ])("formats average duration %s as %s", async (seconds, expected) => {
    adminApi.analytics.mockResolvedValueOnce({ ...summary, average_session_duration_seconds: seconds });
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    const cards = await screen.findByTestId("analytics-summary");
    expect(within(cards).getByText(expected)).toBeInTheDocument();
  });

  it("charts products once with relative bars, linked existing products and deleted-name fallback", async () => {
    const longName = "منتج طويل ".repeat(20).trim();
    adminApi.analytics.mockResolvedValueOnce({ ...summary, top_products: [{ product_id: 2, name: longName, slug: "deleted", views: 14, product_exists: false }, summary.top_products[0], { product_id: 3, name: "بلا مشاهدات", slug: "zero", views: 0, product_exists: false }] });
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    const chart = await screen.findByRole("figure", { name: "مقارنة مشاهدات المنتجات" });
    expect(within(chart).getByText("7 مشاهدة")).toBeInTheDocument();
    expect(Array.from(chart.querySelectorAll("[data-view-bar]")).map((bar) => bar.style.width)).toEqual(["100%", "50%", "0%"]);
    expect(within(chart).getByRole("link", { name: "ريزن شفاف" })).toHaveAttribute("href", "/admin/products/1");
    for (const name of [longName, "ريزن شفاف", "بلا مشاهدات"]) expect(screen.getAllByText(name)).toHaveLength(1);
    expect(within(chart).queryByRole("link", { name: longName })).not.toBeInTheDocument();
    expect(within(chart).getAllByRole("listitem")).toHaveLength(3);
    expect(within(chart).getByText(longName)).toHaveStyle({ overflowWrap: "anywhere" });
    expect(screen.getAllByRole("figure", { name: "مقارنة مشاهدات المنتجات" })).toHaveLength(1);
  });

  it("shows locations once as a ranked chart with readable counts and decorative bars", async () => {
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    const chart = await screen.findByRole("figure", { name: "مقارنة زيارات الأماكن" });
    expect(within(chart).getAllByRole("listitem").map((item) => item.textContent)).toEqual(["1القدس5 زيارة", "2الداخل4 زيارة"]);
    expect(Array.from(chart.querySelectorAll("[data-view-bar]")).map((bar) => bar.style.width)).toEqual(["100%", "80%"]);
    for (const bar of chart.querySelectorAll("[data-view-bar]")) expect(bar.parentElement).toHaveAttribute("aria-hidden", "true");
    expect(screen.getAllByRole("figure")).toHaveLength(2);
    expect(screen.getAllByText("القدس")).toHaveLength(1);
    expect(screen.getAllByText("الداخل")).toHaveLength(1);
  });

  it("keeps zero-count locations visible without suggesting any visits", async () => {
    adminApi.analytics.mockResolvedValueOnce({ ...summary, top_locations: [{ name: "غير معروف", sessions: 0 }] });
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    const chart = await screen.findByRole("figure", { name: "مقارنة زيارات الأماكن" });
    expect(within(chart).getByText("غير معروف")).toBeInTheDocument();
    expect(within(chart).getByText("0 زيارة")).toBeInTheDocument();
    expect(chart.querySelector("[data-view-bar]")).toHaveStyle({ width: "0%" });
  });

  it("never displays negative or nonfinite aggregate counts or bar widths", async () => {
    adminApi.analytics.mockResolvedValueOnce({ ...summary, sessions: -1, unique_visitors: Infinity, completed_orders: NaN, abandoned_carts: undefined, funnel: { product_views: -1, add_to_cart: Infinity, checkout_reached: NaN }, top_locations: [{ name: "غير معروف", sessions: -3 }], top_products: [{ ...summary.top_products[0], views: Infinity }] });
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    const cards = await screen.findByTestId("analytics-summary");
    expect(Array.from(cards.children).map((card) => card.querySelector("strong").textContent)).toEqual(["0", "0", "2 دقيقة و5 ثانية", "0"]);
    expect(within(screen.getByRole("region", { name: "مسار الشراء" })).getAllByRole("listitem").map((item) => item.querySelector("strong").textContent)).toEqual(["0", "0", "0", "0"]);
    expect(within(screen.getByRole("region", { name: "السلات المتروكة" })).getByText("0")).toBeInTheDocument();
    for (const bar of document.querySelectorAll("[data-view-bar]")) expect(bar).toHaveStyle({ width: "0%" });
    expect(document.body.textContent).not.toMatch(/NaN|Infinity|∞/);
  });

  it("renders the four event counts in order without treating them as a visitor cohort", async () => {
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    const funnel = await screen.findByRole("region", { name: "مسار الشراء" });
    expect(within(funnel).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "مشاهدة المنتجات21", "الإضافة إلى السلة28", "الوصول إلى إتمام الطلب6", "إنشاء الطلب بنجاح3",
    ]);
    expect(funnel).toHaveTextContent("عدد مرات حدوث كل خطوة خلال الفترة المحددة؛ قد تتكرر الخطوة في الزيارة الواحدة.");
    expect(funnel.textContent).not.toContain("%");
  });

  it("shows one separate abandoned-cart aggregate with the inactive, added and uncompleted definition", async () => {
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    const abandoned = await screen.findByRole("region", { name: "السلات المتروكة" });
    expect(within(abandoned).getByText("4")).toBeInTheDocument();
    expect(abandoned).toHaveTextContent("زيارات أُضيفت فيها منتجات إلى السلة خلال الفترة المحددة، ولم يُنشأ فيها طلب ناجح، وتجاوز آخر نشاط فيها مهلة الخمول المعتمدة.");
    expect(screen.getAllByText("السلات المتروكة")).toHaveLength(1);
  });

  it("keeps empty aggregates safe and shows zero duration, funnel and abandoned counts", async () => {
    adminApi.analytics.mockResolvedValueOnce({ ...summary, sessions: 0, unique_visitors: 0, average_session_duration_seconds: 0, completed_orders: 0, funnel: {}, abandoned_carts: 0, top_locations: [], top_products: [] });
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    const cards = await screen.findByTestId("analytics-summary");
    expect(Array.from(cards.children).map((card) => card.querySelector("strong").textContent)).toEqual(["0", "0", "0 ثانية", "0"]);
    expect(screen.getByText("لا توجد زيارات ضمن هذه الفترة بعد.")).toBeInTheDocument();
    expect(screen.getByText("لا توجد مشاهدات منتجات ضمن هذه الفترة بعد.")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "مسار الشراء" })).getAllByRole("listitem").map((item) => item.querySelector("strong").textContent)).toEqual(["0", "0", "0", "0"]);
    expect(within(screen.getByRole("region", { name: "السلات المتروكة" })).getByText("0")).toBeInTheDocument();
  });

  it("shows only aggregate data and product links even if an unexpected payload includes visitor details", async () => {
    adminApi.analytics.mockResolvedValueOnce({ ...summary, visitors: [{ name: "PRIVATE-VISITOR", email: "private@example.test", ip: "192.0.2.1" }], session_details: [{ id: "PRIVATE-SESSION", path: "/private-path" }] });
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    await screen.findByTestId("analytics-summary");
    for (const detail of ["PRIVATE-VISITOR", "private@example.test", "192.0.2.1", "PRIVATE-SESSION", "/private-path"]) expect(document.body.textContent).not.toContain(detail);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link").map((link) => link.getAttribute("href"))).toEqual(["/admin/products/1"]);
  });

  it.each([{ rows: [] }, { rows: [{ product_id: 1, name: "صفر", views: 0 }] }])("handles empty and zero views: %j", async ({ rows }) => {
    adminApi.analytics.mockResolvedValueOnce({ ...summary, top_products: rows });
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    await screen.findByText("الزيارات");
    if (!rows.length) expect(screen.getByText("لا توجد مشاهدات منتجات ضمن هذه الفترة بعد.")).toBeInTheDocument();
    else expect(screen.getByRole("figure", { name: "مقارنة مشاهدات المنتجات" }).querySelector("[data-view-bar]")).toHaveStyle({ width: "0%" });
  });
  it("shows merchant-facing analytics copy without technical implementation details", async () => {
    adminApi.analytics.mockResolvedValueOnce({ ...summary, location_tracking_configured: false });
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    expect(await screen.findByText("الزيارات")).toBeInTheDocument();
    expect(screen.getByText("الزوار الفريدون")).toBeInTheDocument();
    expect(screen.getByText("أماكن الزوار")).toBeInTheDocument();
    expect(screen.getByText("المنتجات الأكثر مشاهدة")).toBeInTheDocument();
    expect(screen.getByText("ملخص لحركة الزوار والمنتجات الأكثر مشاهدة خلال الفترة المحددة.")).toBeInTheDocument();
    expect(screen.getByText("قد لا تتوفر بيانات الموقع الجغرافي لبعض الزيارات.")).toBeInTheDocument();
    expect(screen.getByText("إجمالي الزيارات خلال الفترة المحددة.")).toBeInTheDocument();
    expect(screen.getByText("عدد الزوار المختلفين خلال الفترة المحددة.")).toBeInTheDocument();
    expect(screen.getByText("أكثر الأماكن التي جاءت منها الزيارات.")).toBeInTheDocument();
    expect(screen.getByText("المنتجات التي حازت على أكبر عدد من المشاهدات.")).toBeInTheDocument();
    expect(screen.getByText("القدس")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ريزن شفاف" })).toBeInTheDocument();
    expect(screen.getByText("5 زيارة")).toBeInTheDocument();
    expect(screen.getByText("7 مشاهدة")).toBeInTheDocument();

    const pageText = document.body.textContent;
    for (const technicalCopy of ["Cloudflare", "AOP", "fingerprinting", "first-party", "30 دقيقة"]) {
      expect(pageText).not.toContain(technicalCopy);
    }
  });

  it("reloads the common report when the period changes", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    await screen.findByText("الزيارات");
    await user.click(screen.getByRole("button", { name: "آخر 7 أيام" }));
    await waitFor(() => expect(adminApi.analytics).toHaveBeenLastCalledWith("7d"));
    await user.click(screen.getByRole("button", { name: "آخر 30 يوم" }));
    await waitFor(() => expect(adminApi.analytics).toHaveBeenLastCalledWith("30d"));
    await user.click(screen.getByRole("button", { name: "اليوم" }));
    await waitFor(() => expect(adminApi.analytics).toHaveBeenLastCalledWith("today"));
    expect(screen.getByRole("button", { name: "اليوم" })).toHaveAttribute("aria-pressed", "true");
  });

  it("retains initial loading, error copy and recovery on period change", async () => {
    let reject;
    adminApi.analytics.mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    expect(screen.getByText("جارٍ تحميل الإحصائيات…")).toBeInTheDocument();
    await act(async () => reject(new Error("unavailable")));
    expect(screen.getByText("تعذّر تحميل الإحصائيات حالياً. حاول مرة أخرى.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "آخر 7 أيام" }));
    await screen.findByTestId("analytics-summary");
    expect(screen.queryByText("تعذّر تحميل الإحصائيات حالياً. حاول مرة أخرى.")).not.toBeInTheDocument();
  });

  it.each(["resolve", "reject"])("ignores a stale period request that later %s", async (settlement) => {
    let resolve, reject;
    adminApi.analytics.mockReturnValueOnce(new Promise((done, fail) => { resolve = done; reject = fail; }));
    adminApi.analytics.mockResolvedValueOnce({ ...summary, period: "7d", sessions: 77 });
    render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: "آخر 7 أيام" }));
    const cards = await screen.findByTestId("analytics-summary");
    expect(within(cards).getByText("77")).toBeInTheDocument();
    await act(async () => settlement === "resolve" ? resolve(summary) : reject(new Error("stale")));
    expect(within(cards).getByText("77")).toBeInTheDocument();
    expect(within(cards).queryByText("14")).not.toBeInTheDocument();
    expect(screen.queryByText("تعذّر تحميل الإحصائيات حالياً. حاول مرة أخرى.")).not.toBeInTheDocument();
  });
});
