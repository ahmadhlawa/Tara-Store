import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cartStorage } from "../storage/cartStorage.js";
import { renderApp, respond, storefrontRoutes, stubApi } from "./utils.jsx";

const quote = (type = "normal") => ({
  lines: [],
  subtotal: 130,
  discount: 0,
  delivery_fee: 0,
  packaging_type: type,
  packaging_fee: type === "gift" ? 5 : 0,
  total: type === "gift" ? 135 : 130,
});

const routes = {
  ...storefrontRoutes,
  "POST /api/v1/cart/price": ({ init }) => quote(JSON.parse(init.body).packaging_type),
};

const priceCalls = (calls) =>
  calls.filter((call) => call.path.startsWith("/api/v1/cart/price"));

const orderCalls = (calls) =>
  calls.filter((call) => call.method === "POST" && call.path.startsWith("/api/v1/orders"));

async function fillCheckout() {
  await userEvent.type(screen.getByLabelText(/الاسم الكامل/), "سارة أحمد");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "رمز الدولة" }), "+970");
  await userEvent.type(screen.getByLabelText(/رقم الهاتف/), "0591234567");
  await userEvent.type(screen.getByLabelText(/العنوان بالتفصيل/), "رام الله، شارع الإرسال");
  await userEvent.selectOptions(screen.getByLabelText(/منطقة التوصيل/), "1");
  await userEvent.click(screen.getByRole("checkbox", { name: /قرأت/ }));
}

describe("storefront packaging", () => {
  beforeEach(() => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    cartStorage.save([
      {
        key: "1|",
        productId: 1,
        slug: "clear-resin",
        name: "ريزن شفاف",
        unit: 130,
        qty: 1,
      },
    ]);
  });

  it("keeps packaging out of the cart drawer and prices it as normal", async () => {
    const calls = stubApi(routes);
    renderApp("/ar/shop");

    await userEvent.click(await screen.findByRole("button", { name: "عربة التسوّق" }));
    const drawer = screen.getByRole("dialog", { name: "عربة التسوّق" });

    expect(within(drawer).queryByText("التغليف")).not.toBeInTheDocument();
    expect(within(drawer).queryByText(/رسوم التغليف/)).not.toBeInTheDocument();
    expect(within(drawer).queryByRole("radio")).not.toBeInTheDocument();

    await waitFor(() => expect(priceCalls(calls).length).toBeGreaterThan(0));
    expect(JSON.parse(priceCalls(calls).at(-1).body).packaging_type).toBe("normal");
  });

  it("offers one optional gift checkbox at checkout and hides normal packaging", async () => {
    const calls = stubApi(routes);
    renderApp("/ar/checkout");

    const gift = await screen.findByRole("checkbox", { name: /تغليف كهدية/ });
    expect(gift).not.toBeChecked();

    const summary = await screen.findByRole("complementary", { name: "ملخّص الطلب" });
    expect(within(summary).queryByText("تغليف كهدية")).not.toBeInTheDocument();
    expect(within(summary).queryByText(/رسوم التغليف/)).not.toBeInTheDocument();

    await userEvent.click(gift);

    await waitFor(() =>
      expect(JSON.parse(priceCalls(calls).at(-1).body).packaging_type).toBe("gift"),
    );
    await waitFor(() => expect(within(summary).getByText("تغليف كهدية")).toBeInTheDocument());
    expect(within(summary).getByText("5 ₪")).toBeInTheDocument();

    await userEvent.click(gift);
    await waitFor(() =>
      expect(JSON.parse(priceCalls(calls).at(-1).body).packaging_type).toBe("normal"),
    );
    expect(within(summary).queryByText("تغليف كهدية")).not.toBeInTheDocument();
  });

  it("submits gift packaging only when the checkbox is selected", async () => {
    const order = {
      order_number: "ORD-GIFT",
      public_token: "token-gift",
      status: "new",
      items: [],
      customer_name: "سارة أحمد",
      customer_phone: "+970591234567",
      address: "رام الله، شارع الإرسال",
      subtotal: 130,
      discount: 0,
      delivery_fee: 0,
      total: 135,
      packaging_type: "gift",
      packaging_fee: 5,
    };

    const calls = stubApi({
      ...routes,
      "POST /api/v1/orders": respond(201, order),
      "/api/v1/orders/ORD-GIFT": order,
    });
    vi.spyOn(window, "open").mockImplementation(() => null);

    renderApp("/ar/checkout");
    await userEvent.click(await screen.findByRole("checkbox", { name: /تغليف كهدية/ }));
    await fillCheckout();

    const submit = screen.getByRole("button", { name: /تأكيد وإرسال الطلب/ });
    await waitFor(() => expect(submit).toBeEnabled());
    await userEvent.click(submit);

    await screen.findByRole("heading", { name: "تم استلام طلبك بنجاح" });
    const payload = JSON.parse(orderCalls(calls)[0].body);
    expect(payload.packaging_type).toBe("gift");
    expect(payload).not.toHaveProperty("packaging_fee");

    const success = document.querySelector(".vs-done__summary");
    expect(within(success).getByText("تغليف كهدية")).toBeInTheDocument();
    expect(within(success).getByText("5 ₪")).toBeInTheDocument();
  });
});
