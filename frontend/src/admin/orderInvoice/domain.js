export const ORDER_STATUSES = [
  ["new", "طلب جديد"], ["confirmed", "طلب مؤكد"], ["ready", "جاهز"],
  ["delivered", "تم تسليمه"], ["completed", "مكتمل"], ["cancelled", "طلب ملغى"],
];

// The first element of every pair is the value the API validates; the second is a
// display label only. They must never drift apart: an unknown value is rejected as
// a 422 that reaches the manager as "البيانات المرسلة غير صالحة." with a filter that
// looks perfectly valid on screen.
export const PAYMENT_STATUSES = [
  ["unpaid", "غير مدفوع"], ["paid", "مدفوع"], ["refunded", "مسترد"],
];

export const INVOICE_STATUSES = [["active", "نشطة"], ["cancelled", "ملغاة"], ["replaced", "مستبدلة"]];
export const ORDER_SOURCES = [["website", "الموقع"], ["whatsapp", "واتساب"], ["other", "أخرى"]];
// Manager-selectable methods only. `card` is a value the API can return on an older
// invoice, so it is labelled below without being offered as a new choice here.
export const PAYMENT_METHODS = [["cash_on_delivery", "الدفع عند الاستلام"], ["bank_transfer", "تحويل يدوي / بنكي"]];

const labels = (entries) => Object.fromEntries(entries);
export const orderStatusLabels = { ...labels(ORDER_STATUSES), pending: "طلب مؤكد", reviewing: "طلب مؤكد", processing: "جاهز", preparing: "جاهز", shipped: "تم تسليمه", out_for_delivery: "تم تسليمه" };
export const paymentStatusLabels = { ...labels(PAYMENT_STATUSES), partially_paid: "غير مدفوع", partially_refunded: "مسترد" };
export const invoiceStatusLabels = labels(INVOICE_STATUSES);
export const orderSourceLabels = { ...labels(ORDER_SOURCES), phone: "أخرى", walk_in: "أخرى", social: "أخرى" };
export const paymentMethodLabels = { ...labels(PAYMENT_METHODS), card: "بطاقة" };

function decimalParts(value) {
  const text = String(value ?? "0").trim();
  if (!/^-?\d+(?:\.\d+)?$/.test(text)) throw new Error("Invalid decimal amount");
  const negative = text.startsWith("-");
  const [whole, fraction = ""] = (negative ? text.slice(1) : text).split(".");
  return { negative, digits: BigInt(`${whole}${fraction}`), scale: fraction.length };
}

function withScale(parts, scale) {
  const digits = parts.digits * (10n ** BigInt(scale - parts.scale));
  return parts.negative ? -digits : digits;
}

function decimalText(value, minimumScale = 2) {
  const parts = decimalParts(value);
  const scale = Math.max(minimumScale, parts.scale);
  const signed = withScale(parts, scale);
  const sign = signed < 0n ? "-" : "";
  const digits = (signed < 0n ? -signed : signed).toString().padStart(scale + 1, "0");
  const whole = digits.slice(0, -scale) || "0";
  return `${sign}${whole}.${digits.slice(-scale)}`;
}

function scaledText(amount, scale) {
  const sign = amount < 0n ? "-" : "";
  const digits = (amount < 0n ? -amount : amount).toString().padStart(scale + 1, "0");
  return `${sign}${digits.slice(0, -scale) || "0"}.${digits.slice(-scale)}`;
}

export const normalizeMoney = (value) => decimalText(value);
export const isMoney = (value) => /^\d+(?:\.\d{1,2})?$/.test(String(value ?? "").trim());
export const isWholeQuantity = (value) => /^[1-9]\d*$/.test(String(value ?? "").trim());

export function multiplyMoney(unitPrice, quantity) {
  if (!isWholeQuantity(quantity)) throw new Error("Quantity must be a positive whole number");
  const parts = decimalParts(unitPrice);
  const scale = Math.max(2, parts.scale);
  return scaledText(withScale(parts, scale) * BigInt(String(quantity)), scale);
}

export function calculateOrderTotals({ items = [], discount = "0", delivery_fee = "0", deliveryFee } = {}) {
  const charges = [discount, deliveryFee ?? delivery_fee];
  const parts = [...items.map((item) => decimalParts(item.unit_price ?? "0")), ...charges.map(decimalParts)];
  const scale = Math.max(2, ...parts.map((part) => part.scale));
  const subtotal = items.reduce((sum, item) => sum + (isWholeQuantity(item.quantity) ? withScale(decimalParts(item.unit_price ?? "0"), scale) * BigInt(String(item.quantity)) : 0n), 0n);
  const total = subtotal - withScale(decimalParts(discount), scale) + withScale(decimalParts(deliveryFee ?? delivery_fee), scale);
  return { subtotal: scaledText(subtotal, scale), total: scaledText(total < 0n ? 0n : total, scale) };
}

export function formatMoney(value, currencySymbol = "") {
  const [whole, fraction] = normalizeMoney(value).split(".");
  const sign = whole.startsWith("-") ? "-" : "";
  const grouped = (sign ? whole.slice(1) : whole).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${currencySymbol ? `${currencySymbol} ` : ""}${sign}${grouped}.${fraction}`;
}

export const isManager = (admin) => admin?.role === "super_admin";
export const isAdmin = (admin) => admin?.role === "admin" || isManager(admin);
export const canCreateManualOrder = (admin) => isManager(admin);
const canManageReopenedOrder = (admin, order) => !order?.completed_at || isManager(admin);
const editableOrderStatuses = new Set(["new", "confirmed", "ready", "delivered"]);
export const canEditIncompleteOrder = (admin, order) => isAdmin(admin) && canManageReopenedOrder(admin, order) && !order?.is_locked && editableOrderStatuses.has(order?.status) && (isManager(admin) || (order?.source === "website" && !(order?.items || []).some((item) => item.item_kind === "manual")));
export const canCompleteOrder = (admin, order) => isAdmin(admin) && canManageReopenedOrder(admin, order) && !order?.is_locked && order?.status !== "cancelled";
export const canReopenOrder = (admin, order) => isManager(admin) && order?.is_locked && order?.status === "completed";
export const canUpdateInvoicePayment = (admin, invoice) => isAdmin(admin) && invoice?.status === "active";
