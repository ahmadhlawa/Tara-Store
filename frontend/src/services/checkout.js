// Checkout talks to the server for every number it shows. The browser cart is a
// convenience; the API is the source of truth for prices, discounts and totals.
import { publicApi } from "../api/publicApi.js";

const toItems = (cart) =>
  cart.map((line) => ({
    product_id: line.productId,
    variant_id: line.variantId ?? null,
    selected_option_value_ids: line.selectedOptionValueIds || [],
    quantity: line.qty,
  }));

const displayMoney = (value) => String(value ?? 0);

/** The server response is the only source for this operator-facing message. */
export function buildOrderWhatsAppMessage(order) {
  const lines = (order.items || []).map(
    (item) =>
      `- ${item.product_name}${item.sku ? ` (${item.sku})` : ""} × ${item.quantity}: ${displayMoney(item.line_total)}`,
  );
  return [
    "طلب جديد من الموقع",
    `رقم الطلب: ${order.order_number}`,
    "",
    "بيانات العميل:",
    `الاسم: ${order.customer_name}`,
    `الهاتف: ${order.customer_phone}`,
    `العنوان: ${order.address}`,
    "",
    "المنتجات:",
    ...lines,
    "",
    `المجموع الفرعي: ${displayMoney(order.subtotal)}`,
    `الخصم: ${displayMoney(order.discount)}`,
    `التوصيل${order.delivery_area_name ? ` (${order.delivery_area_name})` : ""}: ${displayMoney(order.delivery_fee)}`,
    `الإجمالي: ${displayMoney(order.total)}`,
    ...(order.customer_notes ? ["", `ملاحظات: ${order.customer_notes}`] : []),
  ].join("\n");
}

export const checkoutService = {
  /** Re-price the cart server-side. Returns null for an empty cart. */
  async price(cart, { couponCode = null, deliveryAreaId = null } = {}) {
    if (!cart.length) return null;
    const response = await publicApi.priceCart({
      items: toItems(cart),
      coupon_code: couponCode || null,
      delivery_area_id: deliveryAreaId ?? null,
    });
    return {
      lines: response.lines,
      subtotal: response.subtotal,
      discount: response.discount,
      shipping: response.delivery_fee,
      total: response.total,
      couponCode: response.coupon_code,
      areaName: response.delivery_area_name,
    };
  },

  validateCoupon: (code, subtotal) => publicApi.validateCoupon(code, subtotal),

  async placeOrder(cart, customer, clientReference) {
    return publicApi.createOrder({
      client_reference: clientReference,
      customer_name: customer.name,
      customer_phone: customer.phone,
      address: customer.address,
      delivery_area_id: customer.deliveryAreaId ?? null,
      coupon_code: customer.couponCode || null,
      payment_method: customer.paymentMethod,
      customer_notes: customer.notes || null,
      items: toItems(cart),
    });
  },

  order: (orderNumber, token) => publicApi.order(orderNumber, token),
};

/**
 * Local, optimistic totals for the cart drawer and the cart page.
 * Anything that becomes an order is re-priced by the server first.
 */
export function localTotals(cart, { discount = 0, shipping = 0 } = {}) {
  const subtotal = cart.reduce((sum, line) => sum + line.unit * line.qty, 0);
  return {
    subtotal,
    discount,
    shipping,
    total: Math.max(0, subtotal - discount + shipping),
  };
}
