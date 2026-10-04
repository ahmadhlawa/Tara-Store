import { beforeEach, describe, expect, it, vi } from "vitest";

const { createOrder, priceCart } = vi.hoisted(() => ({ createOrder: vi.fn(), priceCart: vi.fn() }));

vi.mock("../api/publicApi.js", () => ({
  publicApi: {
    createOrder,
    priceCart,
    validateCoupon: vi.fn(),
    order: vi.fn(),
  },
}));

import { buildOrderWhatsAppMessage, checkoutService } from "../services/checkout.js";
import { paymentMethodLabels, paymentMethods } from "../store.js";

describe("checkout confirmation", () => {
  beforeEach(() => {
    createOrder.mockReset();
    priceCart.mockReset();
  });

  it("submits the caller's stable reference with identifier-only cart lines", async () => {
    createOrder.mockResolvedValue({ order_number: "ORD-1" });

    await checkoutService.placeOrder(
      [{ productId: 4, variantId: null, qty: 2, name: "Untrusted", unit: 1 }],
      { name: "Customer", countryCode: "+970", phone: "0591234567", address: "A valid address", paymentMethod: "cash_on_delivery" },
      "checkout-ref-0001",
    );

    expect(createOrder).toHaveBeenCalledWith({
      client_reference: "checkout-ref-0001",
      customer_name: "Customer",
      customer_phone: "970591234567",
      address: "A valid address",
      delivery_area_id: null,
      coupon_code: null,
      payment_method: "cash_on_delivery",
      customer_notes: null,
      packaging_type: "normal",
      items: [{ product_id: 4, variant_id: null, selected_option_value_ids: [], quantity: 2 }],
    });
  });

  it.each([
    ["+970", "0591234567", "970591234567"],
    ["+970", "591234567", "970591234567"],
    ["+972", "0521234567", "972521234567"],
    ["+972", "521234567", "972521234567"],
  ])("normalizes %s and %s before submitting the order", async (countryCode, phone, expected) => {
    createOrder.mockResolvedValue({ order_number: "ORD-1" });

    await checkoutService.placeOrder(
      [{ productId: 4, variantId: null, qty: 1 }],
      { name: "Customer", countryCode, phone, address: "A valid address", paymentMethod: "cash_on_delivery" },
      `checkout-${expected}`,
    );

    expect(createOrder.mock.calls[0][0].customer_phone).toBe(expected);
  });

  it("refuses to submit an invalid customer phone", async () => {
    await expect(checkoutService.placeOrder(
      [{ productId: 4, variantId: null, qty: 1 }],
      { name: "Customer", countryCode: "", phone: "0591234567", address: "A valid address" },
      "checkout-invalid-phone",
    )).rejects.toThrow("Invalid customer phone");
    expect(createOrder).not.toHaveBeenCalled();
  });

  it("defaults quotes to normal packaging", async () => {
    priceCart.mockResolvedValue({ packaging_type: "normal", packaging_fee: 0, total: 100 });
    await checkoutService.price([{ productId: 4, qty: 1 }]);
    expect(priceCart.mock.calls[0][0]).toHaveProperty("packaging_type", "normal");
  });

  it("sends only the gift identifier and preserves server quote amounts", async () => {
    priceCart.mockResolvedValue({ packaging_type: "gift", packaging_fee: 7, total: 137 });
    const quote = await checkoutService.price([{ productId: 4, qty: 1, unit: 1 }], {
      packagingType: "gift", packagingFee: 999, packaging_fee: 999,
    });
    expect(priceCart).toHaveBeenCalledWith({
      items: [{ product_id: 4, variant_id: null, selected_option_value_ids: [], quantity: 1 }],
      coupon_code: null, delivery_area_id: null, packaging_type: "gift",
    });
    expect(quote).toMatchObject({ packagingType: "gift", packagingFee: 7, total: 137 });
  });

  it("places gift orders without accepting an arbitrary packaging fee", async () => {
    const order = { packaging_type: "gift", packaging_fee: 7, total: 137 };
    createOrder.mockResolvedValue(order);
    const result = await checkoutService.placeOrder([{ productId: 4, qty: 1 }], {
      name: "Customer", countryCode: "+970", phone: "0591234567",
      packagingType: "gift", packagingFee: 999, packaging_fee: 999,
    }, "reference");
    expect(createOrder.mock.calls[0][0]).toHaveProperty("packaging_type", "gift");
    expect(createOrder.mock.calls[0][0]).not.toHaveProperty("packaging_fee");
    expect(result).toBe(order);
  });

  it.each(["ar", "en"])("translates WhatsApp packaging labels in %s using canonical amounts", (locale) => {
    const message = buildOrderWhatsAppMessage({
      packaging_type: "gift", packaging_fee: 7, total: 137, items: [],
    }, locale);
    expect(message).toContain(locale === "en" ? "Gift packaging" : "تغليف كهدية");
    expect(message).toContain(locale === "en" ? "Packaging fee: 7" : "رسوم التغليف: 7");
    expect(message).toContain("137");
    expect(message).not.toContain("999");
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
