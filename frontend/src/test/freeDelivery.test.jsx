import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { cartStorage } from "../storage/cartStorage.js";
import { renderApp, storefrontRoutes, stubApi } from "./utils.jsx";

/**
 * The client's delivery table: two areas free from 220, one from 400. The
 * customer has to be able to see which of those they are close to, in the cart
 * and again at checkout, and the number they are shown has to be the one the
 * server charges.
 */
const AREAS = [
  { id: 1, name: "الضفة", delivery_fee: 25, free_delivery_threshold: 220, estimated_days: "3 أيام عمل", sort_order: 1 },
  { id: 2, name: "القدس", delivery_fee: 35, free_delivery_threshold: 220, estimated_days: "3 أيام عمل", sort_order: 2 },
  { id: 3, name: "الداخل", delivery_fee: 80, free_delivery_threshold: 400, estimated_days: "3 أيام عمل", sort_order: 3 },
];

const routes = { ...storefrontRoutes, "/api/v1/delivery-areas": AREAS };

const seedCart = (unit, qty = 1) =>
  cartStorage.save([
    {
      key: "1|",
      productId: 1,
      variantId: null,
      slug: "clear-resin",
      name: "ريزن شفاف",
      unit,
      bg: "",
      variation: "",
      qty,
    },
  ]);

const notice = async () => {
  const heading = await screen.findByText("التوصيل المجاني");
  return heading.parentElement;
};

describe("free delivery notice", () => {
  beforeEach(() => cartStorage.clear());

  it("groups the areas by threshold and says what is left to reach each one", async () => {
    seedCart(100);
    stubApi(routes);
    renderApp("/cart");

    const panel = within(await notice());
    // 220 − 100 for الضفة and القدس, which share a threshold and so share a line.
    expect(panel.getByText(/الضفة، القدس/)).toHaveTextContent("أضف 120 ₪");
    expect(panel.getByText(/الداخل/)).toHaveTextContent("أضف 300 ₪");
  });

  it("confirms eligibility once the subtotal reaches the threshold", async () => {
    seedCart(110, 2); // exactly 220
    stubApi(routes);
    renderApp("/cart");

    const panel = within(await notice());
    expect(panel.getByText(/طلبك مؤهل للتوصيل المجاني إلى الضفة، القدس/)).toBeInTheDocument();
    // The higher threshold is not reached and still says so.
    expect(panel.getByText(/الداخل/)).toHaveTextContent("أضف 180 ₪");
  });

  it("narrows to the chosen area at checkout", async () => {
    seedCart(100);
    stubApi({
      ...routes,
      "POST /api/v1/cart/price": {
        lines: [],
        subtotal: 100,
        discount: 0,
        delivery_fee: 80,
        total: 180,
        coupon_code: null,
        delivery_area_name: "الداخل",
      },
    });
    renderApp("/checkout");

    await userEvent.selectOptions(await screen.findByLabelText("منطقة التوصيل"), "3");

    const panel = within(await notice());
    expect(panel.getByText(/الداخل/)).toHaveTextContent("أضف 300 ₪");
    expect(panel.queryByText(/الضفة/)).not.toBeInTheDocument();
  });

  it("says nothing at all when no area offers free delivery", async () => {
    seedCart(100);
    stubApi({
      ...routes,
      "/api/v1/delivery-areas": [
        { id: 1, name: "الضفة", delivery_fee: 25, free_delivery_threshold: null, sort_order: 1 },
      ],
    });
    renderApp("/cart");

    await screen.findByText("ملخّص الطلب");
    expect(screen.queryByText("التوصيل المجاني")).not.toBeInTheDocument();
  });
});
