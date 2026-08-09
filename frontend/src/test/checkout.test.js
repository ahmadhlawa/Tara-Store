import { beforeEach, describe, expect, it, vi } from "vitest";

const { createOrder } = vi.hoisted(() => ({ createOrder: vi.fn() }));

vi.mock("../api/publicApi.js", () => ({
  publicApi: {
    createOrder,
    priceCart: vi.fn(),
    validateCoupon: vi.fn(),
    order: vi.fn(),
  },
}));

import { buildOrderWhatsAppMessage, checkoutService } from "../services/checkout.js";
import { paymentMethodLabels, paymentMethods } from "../store.js";

describe("checkout confirmation", () => {
  beforeEach(() => {
    createOrder.mockReset();
  });

  it("submits the caller's stable reference with identifier-only cart lines", async () => {
    createOrder.mockResolvedValue({ order_number: "ORD-1" });

    await checkoutService.placeOrder(
      [{ productId: 4, variantId: null, qty: 2, name: "Untrusted", unit: 1 }],
      { name: "Customer", phone: "0591234567", address: "A valid address", paymentMethod: "cash_on_delivery" },
      "checkout-ref-0001",
    );

    expect(createOrder).toHaveBeenCalledWith({
      client_reference: "checkout-ref-0001",
      customer_name: "Customer",
      customer_phone: "0591234567",
      customer_email: null,
      address: "A valid address",
      delivery_area_id: null,
      coupon_code: null,
      payment_method: "cash_on_delivery",
      customer_notes: null,
      items: [{ product_id: 4, variant_id: null, quantity: 2 }],
    });
  });

  it("builds the Arabic WhatsApp text entirely from the canonical order response", () => {
    const message = buildOrderWhatsAppMessage({
      order_number: "ORD-20260803-0042",
      customer_name: "سارة أحمد",
      customer_phone: "0591234567",
      address: "رام الله، شارع الإرسال",
      customer_notes: "اتصل قبل الوصول",
      delivery_area_name: "Delivery area API",
      items: [{ product_name: "اسم من الخادم", sku: "SKU-1", quantity: 2, unit_price: 25, line_total: 50 }],
      subtotal: 50,
      discount: 0,
      delivery_fee: 20,
      total: 70,
    });

    expect(message).toContain("ORD-20260803-0042");
    expect(message).toContain("سارة أحمد");
    expect(message).toContain("اسم من الخادم");
    expect(message).toContain("50");
    expect(message).toContain("20");
    expect(message).toContain("70");
    expect(message).toContain("Delivery area API");
    expect(message).toContain("اتصل قبل الوصول");
    expect(message).not.toContain("Untrusted");
  });
});

/**
 * The API's PaymentMethod enum is the contract. The storefront may only ever offer
 * values it accepts: anything else is rejected with a 422 the customer cannot act on,
 * after they have already filled the whole form.
 */
describe("checkout payment methods", () => {
  const CANONICAL = ["cash_on_delivery", "card", "bank_transfer"];

  it("offers only payment values the orders API accepts", () => {
    for (const method of paymentMethods) {
      expect(CANONICAL, `unsupported payment key "${method.key}"`).toContain(method.key);
    }
  });

  it("labels every offered payment method", () => {
    for (const method of paymentMethods) {
      expect(paymentMethodLabels[method.key], `no label for "${method.key}"`).toBeTruthy();
    }
  });
});
