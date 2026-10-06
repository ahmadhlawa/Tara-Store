import { t } from "../i18n/locale.jsx";
// Checkout talks to the server for every number it shows. The browser cart is a
// convenience; the API is the source of truth for prices, discounts and totals.
import { publicApi } from "../api/publicApi.js";
import { packagingTypeLabels } from "../store.js";
import { normalizeCustomerPhone } from "../utils/phone.js";

const toItems = (cart) =>
  cart.map((line) => ({
    product_id: line.productId,
    variant_id: line.variantId ?? null,
    selected_option_value_ids: line.selectedOptionValueIds || [],
    quantity: line.qty,
  }));

const displayMoney = (value) => String(value ?? 0);

/** The server response is the only source for this operator-facing message. */
export function buildOrderWhatsAppMessage(order, locale) {
  const translate = (key, values) => t(key, values, locale);
  const lines = (order.items || []).map(
    (item) =>
      `- ${item.product_name}${item.sku ? ` (${item.sku})` : ""} × ${item.quantity}: ${displayMoney(item.line_total)}`,
  );
  return [
    translate("طلب جديد من الموقع"),
    translate("رقم الطلب: {0}", [order.order_number]),
    "",
    translate("بيانات العميل:"),
    translate("الاسم: {0}", [order.customer_name]),
    translate("الهاتف: {0}", [order.customer_phone]),
    translate("العنوان: {0}", [order.address]),
    "",
    translate("المنتجات:"),
    ...lines,
    "",
    translate("المجموع الفرعي: {0}", [displayMoney(order.subtotal)]),
    translate("الخصم: {0}", [displayMoney(order.discount)]),
    translate("التوصيل{0}: {1}", [order.delivery_area_name ? ` (${order.delivery_area_name})` : "", displayMoney(order.delivery_fee)]),
    ...(order.packaging_type === "gift" ? [
      `${translate(packagingTypeLabels.gift)}: ${displayMoney(order.packaging_fee)}`,
    ] : []),
    translate("الإجمالي: {0}", [displayMoney(order.total)]),
    ...(order.customer_notes ? ["", translate("ملاحظات: {0}", [order.customer_notes])] : []),
  ].join("\n");
}

export const checkoutService = {
  /** Re-price the cart server-side. Returns null for an empty cart. */
  async price(cart, { couponCode = null, deliveryAreaId = null, packagingType = "normal" } = {}) {
    if (!cart.length) return null;
    const response = await publicApi.priceCart({
      items: toItems(cart),
      coupon_code: couponCode || null,
      delivery_area_id: deliveryAreaId ?? null,
      packaging_type: packagingType,
    });
    return {
      lines: response.lines,
      subtotal: response.subtotal,
      discount: response.discount,
      shipping: response.delivery_fee,
      total: response.total,
      couponCode: response.coupon_code,
      areaName: response.delivery_area_name,
      packagingType: response.packaging_type ?? "normal",
      packagingFee: response.packaging_fee ?? 0,
    };
  },

  validateCoupon: (code, subtotal) => publicApi.validateCoupon(code, subtotal),

  async placeOrder(cart, customer, clientReference) {
    const normalizedPhone = normalizeCustomerPhone(customer.countryCode, customer.phone);
    if (!normalizedPhone) throw new Error("Invalid customer phone");
    return publicApi.createOrder({
      client_reference: clientReference,
      customer_name: customer.name,
      customer_phone: normalizedPhone,
      address: customer.address,
      delivery_area_id: customer.deliveryAreaId ?? null,
      coupon_code: customer.couponCode || null,
      payment_method: customer.paymentMethod,
      customer_notes: customer.notes || null,
      packaging_type: customer.packagingType ?? "normal",
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
