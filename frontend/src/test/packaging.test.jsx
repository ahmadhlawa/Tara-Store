import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cartStorage } from "../storage/cartStorage.js";
import { renderApp, respond, storefrontRoutes, stubApi } from "./utils.jsx";

const quote = (type = "normal") => ({
  lines: [], subtotal: 130, discount: 0, delivery_fee: 0,
  packaging_type: type, packaging_fee: type === "gift" ? 7 : 0,
  total: type === "gift" ? 137 : 130,
});
const routes = {
  ...storefrontRoutes,
  "POST /api/v1/cart/price": ({ init }) => quote(JSON.parse(init.body).packaging_type),
};
const priceCalls = (calls) => calls.filter((call) => call.path.startsWith("/api/v1/cart/price"));
const packagingRow = (root) => within(root).getByText(/رسوم التغليف|Packaging fee/).parentElement;
const totalRow = (root) => within(root).getByText(/^(الإجمالي|Total)$/).parentElement;
const orderCalls = (calls) => calls.filter((call) => call.method === "POST" && call.path.startsWith("/api/v1/orders"));

async function fillCheckout() {
  const form = document.querySelector(".vs-checkout__form");
  const fields = form.querySelectorAll("input[type=text], input[type=tel], textarea");
  await userEvent.type(fields[0], "سارة أحمد");
  await userEvent.selectOptions(within(form).getByRole("combobox", { name: /رمز الدولة|Country code/ }), "+970");
  await userEvent.type(fields[1], "0591234567");
  await userEvent.type(fields[2], "رام الله، شارع الإرسال");
  await userEvent.selectOptions(within(form).getByRole("combobox", { name: /منطقة التوصيل|Delivery area/ }), "1");
  await userEvent.click(within(form).getByRole("checkbox"));
  await waitFor(() => expect(form.querySelector("button[type=submit]")).toHaveTextContent("130 ₪"));
  return form;
}

async function changeToUnquotedGift(mode, calls) {
  const originalFetch = globalThis.fetch;
  let resolveQuote;
  globalThis.fetch = vi.fn((url, init) => String(url).includes("/cart/price")
    ? new Promise((resolve) => { resolveQuote = resolve; })
    : originalFetch(url, init));
  await userEvent.click(screen.getByRole("radio", { name: /تغليف كهدية|Gift packaging/ }));
  await waitFor(() => expect(resolveQuote).toBeTypeOf("function"));
  if (mode === "failed") {
    await act(async () => resolveQuote(new Response(JSON.stringify({ error: { code: "unavailable", message: "Quote unavailable" } }), { status: 400 })));
    expect(await screen.findByRole("alert")).toHaveTextContent(document.documentElement.lang === "en"
      ? "Something went wrong. Please try again." : "Quote unavailable");
  }
  expect(orderCalls(calls)).toHaveLength(0);
  return resolveQuote;
}

describe("storefront packaging", () => {
  beforeEach(() => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    cartStorage.save([{ key: "1|", productId: 1, slug: "clear-resin", name: "ريزن شفاف", unit: 100, qty: 1 }]);
  });

  it("ends the cart with a single-choice packaging section defaulting to normal", async () => {
    const calls = stubApi(routes);
    renderApp("/ar/shop");
    await userEvent.click(await screen.findByRole("button", { name: "عربة التسوّق" }));
    const drawer = screen.getByRole("dialog");
    const group = within(drawer).getByRole("group", { name: "التغليف" });
    expect(drawer.querySelector(".vs-drawer__body").lastElementChild).toBe(group);
    expect(within(group).getAllByRole("radio")).toHaveLength(2);
    expect(within(group).getByRole("radio", { name: /تغليف عادي/ })).toBeChecked();
    expect(within(group).getByText("0 ₪")).toBeInTheDocument();
    expect(within(group).getByRole("radio", { name: /تغليف كهدية/ })).not.toBeChecked();
    expect(within(group).getByText("+5 ₪")).toBeInTheDocument();
    await waitFor(() => expect(priceCalls(calls).length).toBeGreaterThan(0));
    expect(JSON.parse(priceCalls(calls).at(-1).body).packaging_type).toBe("normal");
  });

  it("uses server gift fee and total in the drawer and reprices normal and quantity changes", async () => {
    const calls = stubApi(routes);
    renderApp("/ar/shop");
    await userEvent.click(await screen.findByRole("button", { name: "عربة التسوّق" }));
    const drawer = screen.getByRole("dialog");
    await userEvent.click(within(drawer).getByRole("radio", { name: /تغليف كهدية/ }));
    await waitFor(() => expect(packagingRow(drawer)).toHaveTextContent("7 ₪"));
    expect(packagingRow(drawer)).toHaveTextContent("تغليف كهدية");
    expect(totalRow(drawer)).toHaveTextContent("137 ₪");
    expect(totalRow(drawer)).not.toHaveTextContent("105 ₪");
    const gift = JSON.parse(priceCalls(calls).at(-1).body);
    expect(gift.packaging_type).toBe("gift");
    expect(gift).not.toHaveProperty("packaging_fee");
    await userEvent.click(within(drawer).getByRole("radio", { name: /تغليف عادي/ }));
    await waitFor(() => expect(packagingRow(drawer)).toHaveTextContent("0 ₪"));
    expect(totalRow(drawer)).toHaveTextContent("130 ₪");
    await userEvent.click(within(drawer).getByRole("button", { name: "زيادة الكمية" }));
    await waitFor(() => expect(JSON.parse(priceCalls(calls).at(-1).body).items[0].quantity).toBe(2));
  });

  it("keeps gift selected through drawer navigation and both locale switches", async () => {
    const calls = stubApi(routes);
    renderApp("/ar/shop");
    await userEvent.click(await screen.findByRole("button", { name: "عربة التسوّق" }));
    const drawer = screen.getByRole("dialog");
    await userEvent.click(within(drawer).getByRole("radio", { name: /تغليف كهدية/ }));
    await userEvent.click(within(drawer).getByRole("link", { name: "إتمام الطلب" }));
    expect(await screen.findByRole("radio", { name: /تغليف كهدية/ })).toBeChecked();
    await waitFor(() => expect(packagingRow(screen.getByRole("complementary", { name: "ملخّص الطلب" }))).toHaveTextContent("7 ₪"));
    await userEvent.click(screen.getByRole("link", { name: "Switch to English" }));
    expect(await screen.findByRole("group", { name: "Packaging" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Gift packaging/ })).toBeChecked();
    const summary = screen.getByRole("complementary", { name: "Order summary" });
    await waitFor(() => expect(packagingRow(summary)).toHaveTextContent("7 ₪"));
    expect(packagingRow(summary)).toHaveTextContent("Gift packaging");
    expect(totalRow(summary)).toHaveTextContent("137 ₪");
    expect(priceCalls(calls).filter((call) => call.path.includes("locale=en")).every((call) => JSON.parse(call.body).packaging_type === "gift")).toBe(true);
    await userEvent.click(screen.getByRole("link", { name: "التبديل إلى العربية" }));
    expect(await screen.findByRole("radio", { name: /تغليف كهدية/ })).toBeChecked();
    expect(cartStorage.load()[0]).toMatchObject({ productId: 1, qty: 1, unit: 100 });
  });

  it("places the selected gift order and shows response packaging in success and WhatsApp charges", async () => {
    const order = {
      order_number: "ORD-GIFT", public_token: "token-gift", status: "new", items: [],
      customer_name: "سارة أحمد", customer_phone: "0591234567", address: "عنوان من الخادم",
      subtotal: 130, discount: 0, delivery_fee: 0, total: 137,
      packaging_type: "gift", packaging_fee: 7,
    };
    const calls = stubApi({ ...routes, "POST /api/v1/orders": respond(201, order), "/api/v1/orders/ORD-GIFT": order });
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    renderApp("/ar/checkout");
    expect(await screen.findByRole("radio", { name: /تغليف عادي/ })).toBeChecked();
    await userEvent.click(screen.getByRole("radio", { name: /تغليف كهدية/ }));
    await userEvent.type(screen.getByLabelText(/الاسم الكامل/), "سارة أحمد");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "رمز الدولة" }), "+970");
    await userEvent.type(screen.getByLabelText(/رقم الهاتف/), "0591234567");
    await userEvent.type(screen.getByLabelText(/العنوان بالتفصيل/), "رام الله، شارع الإرسال");
    await userEvent.selectOptions(screen.getByLabelText(/منطقة التوصيل/), "1");
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: /تأكيد وإرسال الطلب/ }));
    await screen.findByRole("heading", { name: "تم استلام طلبك بنجاح" });
    const payload = JSON.parse(calls.find((call) => call.method === "POST" && call.path.startsWith("/api/v1/orders")).body);
    expect(payload.packaging_type).toBe("gift");
    expect(payload).not.toHaveProperty("packaging_fee");
    const summary = document.querySelector(".vs-done__summary");
    expect(packagingRow(summary)).toHaveTextContent("تغليف كهدية");
    expect(packagingRow(summary)).toHaveTextContent("7 ₪");
    expect(totalRow(summary)).toHaveTextContent("137 ₪");
    const message = decodeURIComponent(open.mock.calls[0][0].split("?text=")[1]);
    expect(message).toContain("تغليف كهدية");
    expect(message).toContain("رسوم التغليف: 7");
    await userEvent.click(screen.getByRole("link", { name: "Switch to English" }));
    await screen.findByRole("heading", { name: "Your order has been received" });
    expect(packagingRow(document.querySelector(".vs-done__summary"))).toHaveTextContent("Gift packaging");
    expect(cartStorage.load()).toHaveLength(0);
  });

  it.each(["drawer", "checkout"])("clears stale %s charges and ignores old quotes after selection changes", async (surface) => {
    const calls = stubApi(routes);
    renderApp(surface === "drawer" ? "/ar/shop" : "/ar/checkout");
    if (surface === "drawer") await userEvent.click(await screen.findByRole("button", { name: "عربة التسوّق" }));
    const root = surface === "drawer" ? screen.getByRole("dialog") : await screen.findByRole("complementary", { name: "ملخّص الطلب" });
    await waitFor(() => expect(totalRow(root)).toHaveTextContent("130 ₪"));
    const originalFetch = globalThis.fetch;
    const pending = [];
    globalThis.fetch = vi.fn((url, init) => String(url).includes("/cart/price")
      ? new Promise((resolve) => pending.push({ resolve, type: JSON.parse(init.body).packaging_type }))
      : originalFetch(url, init));
    await userEvent.click(screen.getByRole("radio", { name: /تغليف كهدية/ }));
    expect(totalRow(root)).not.toHaveTextContent("130 ₪");
    await userEvent.click(screen.getByRole("radio", { name: /تغليف عادي/ }));
    await waitFor(() => expect(pending).toHaveLength(2));
    await act(async () => pending[1].resolve(new Response(JSON.stringify(quote("normal")))));
    await waitFor(() => expect(totalRow(root)).toHaveTextContent("130 ₪"));
    await act(async () => pending[0].resolve(new Response(JSON.stringify(quote("gift")))));
    expect(totalRow(root)).toHaveTextContent("130 ₪");
    expect(packagingRow(root)).not.toHaveTextContent("7 ₪");
    expect(priceCalls(calls).length).toBeGreaterThan(0);
  });

  it("reports failed drawer quotes without showing a locally calculated gift total", async () => {
    stubApi({ ...routes, "POST /api/v1/cart/price": respond(400, { error: { code: "unavailable", message: "Quote unavailable" } }) });
    renderApp("/ar/shop");
    await userEvent.click(await screen.findByRole("button", { name: "عربة التسوّق" }));
    await userEvent.click(screen.getByRole("radio", { name: /تغليف كهدية/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Quote unavailable");
    expect(totalRow(screen.getByRole("dialog"))).not.toHaveTextContent("105 ₪");
  });

  it.each([
    ["ar", "pending", "جارٍ حساب الإجمالي…"],
    ["en", "pending", "Calculating total…"],
    ["ar", "failed", "تعذّر حساب الإجمالي"],
    ["en", "failed", "Could not calculate total"],
  ])("blocks %s confirmation when the current gift quote is %s", async (locale, mode, label) => {
    const calls = stubApi(routes);
    renderApp(`/${locale}/checkout`);
    await screen.findByRole("radio", { name: /تغليف عادي|Normal packaging/ });
    const form = await fillCheckout();
    const resolveQuote = await changeToUnquotedGift(mode, calls);
    const submit = form.querySelector("button[type=submit]");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(label);
    expect(submit).not.toHaveTextContent("0 ₪");
    await userEvent.click(submit);
    expect(orderCalls(calls)).toHaveLength(0);
    if (mode === "pending") {
      await act(async () => resolveQuote(new Response(JSON.stringify(quote("gift")))));
      await waitFor(() => expect(submit).toBeEnabled());
      expect(submit).toHaveTextContent("137 ₪");
    } else {
      stubApi(routes);
      await userEvent.click(screen.getByRole("radio", { name: /تغليف عادي|Normal packaging/ }));
      await waitFor(() => expect(submit).toBeEnabled());
      expect(submit).toHaveTextContent("130 ₪");
    }
  });

  it.each(["pending", "failed"])("guards direct form submission when the gift quote is %s", async (mode) => {
    const calls = stubApi(routes);
    renderApp("/ar/checkout");
    await screen.findByRole("radio", { name: /تغليف عادي/ });
    const form = await fillCheckout();
    await changeToUnquotedGift(mode, calls);
    fireEvent.submit(form);
    await act(async () => {});
    expect(orderCalls(calls)).toHaveLength(0);
  });
});
