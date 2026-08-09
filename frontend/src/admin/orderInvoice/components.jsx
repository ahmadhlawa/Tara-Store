import { Fragment, useEffect, useRef, useState } from "react";
import sx from "../../sx.js";
import {
  calculateOrderTotals,
  formatMoney,
  invoiceStatusLabels,
  isMoney,
  isWholeQuantity,
  orderStatusLabels,
  paymentMethodLabels,
  paymentStatusLabels,
} from "./domain.js";

const badgeTones = { new: "#8A6329", pending: "#8A6329", cancelled: "#8E3B34", active: "#3F6B54", completed: "#3F6B54", paid: "#3F6B54", refunded: "#5C4D4F", partially_paid: "#8A6329", partially_refunded: "#8A6329" };
const badge = (tone) => sx`display:inline-flex;align-items:center;inline-size:max-content;padding:4px 10px;border-radius:999px;background:${tone === "#8E3B34" ? "#FBEFEC" : tone === "#3F6B54" ? "#EEF4EF" : "#F8EEDC"};color:${tone};font-size:12px;font-weight:700`;

function StatusBadge({ status, labels, fallback }) {
  const text = labels[status] || fallback || status || "—";
  return <span style={badge(badgeTones[status] || "#5C4D4F")} title={text}>{text}</span>;
}

export const OrderStatusBadge = ({ status }) => <StatusBadge status={status} labels={orderStatusLabels} />;
export const PaymentStatusBadge = ({ status }) => <StatusBadge status={status} labels={paymentStatusLabels} />;
export const InvoiceStatusBadge = ({ status }) => <StatusBadge status={status} labels={invoiceStatusLabels} />;

export function OrderItemsEditor({ items, onChange, disabled = false, currencySymbol = "" }) {
  const update = (index, key, value) => onChange(items.map((item, itemIndex) => itemIndex === index ? { ...item, [key]: value } : item));
  const remove = (index) => onChange(items.filter((_, itemIndex) => itemIndex !== index));
  const addManual = () => onChange([...items, { kind: "manual", name: "", description: "", quantity: 1, unit_price: "0.00" }]);

  return (
    <section dir="rtl" aria-label="أصناف الطلب" style={sx`display:flex;flex-direction:column;gap:12px`}>
      {items.map((item, index) => {
        const line = index + 1;
        return <fieldset key={item.id || `${item.kind}-${index}`} disabled={disabled} style={sx`border:1px solid #E9DED0;border-radius:12px;padding:14px;margin:0;display:grid;grid-template-columns:2fr 90px 130px auto;gap:10px;align-items:end`}>
          <legend style={sx`padding-inline:5px;font-size:13px;font-weight:700`}>الصنف {line}</legend>
          <label style={sx`display:flex;flex-direction:column;gap:5px;font-size:12px;font-weight:700`}>اسم الصنف {line}
            <input aria-label={`اسم الصنف ${line}`} value={item.product_name ?? item.name ?? ""} onChange={(event) => update(index, item.product_name !== undefined ? "product_name" : "name", event.target.value)} style={sx`height:40px;box-sizing:border-box;border:1px solid #E2D5C6;border-radius:8px;padding-inline:10px;font:inherit`} />
          </label>
          <label style={sx`display:flex;flex-direction:column;gap:5px;font-size:12px;font-weight:700`}>الكمية {line}
            <input aria-label={`الكمية ${line}`} type="number" min="1" step="1" value={item.quantity} onChange={(event) => update(index, "quantity", event.target.value)} style={sx`height:40px;box-sizing:border-box;border:1px solid #E2D5C6;border-radius:8px;padding-inline:10px;font:inherit`} />
          </label>
          <label style={sx`display:flex;flex-direction:column;gap:5px;font-size:12px;font-weight:700`}>سعر القطعة {line}
            <input aria-label={`سعر القطعة ${line}`} inputMode="decimal" value={item.unit_price ?? ""} onChange={(event) => update(index, "unit_price", event.target.value)} style={sx`height:40px;box-sizing:border-box;border:1px solid #E2D5C6;border-radius:8px;padding-inline:10px;font:inherit`} />
          </label>
          <button type="button" aria-label={`حذف الصنف ${line}`} onClick={() => remove(index)} style={sx`height:40px;border:1px solid #E5C4BE;border-radius:8px;background:#fff;color:#8E3B34;font:inherit;font-weight:700;cursor:pointer`}>حذف</button>
          <output style={sx`grid-column:1 / -1;text-align:start;color:#766669;font-size:12px`}>إجمالي الصنف: {isMoney(item.unit_price) && isWholeQuantity(item.quantity) ? formatMoney(calculateOrderTotals({ items: [item] }).subtotal, currencySymbol) : "—"}</output>
        </fieldset>;
      })}
      <button type="button" disabled={disabled} onClick={addManual} style={sx`align-self:flex-start;min-height:40px;padding-inline:12px;border:1px solid #7D595B;border-radius:8px;background:#fff;color:#7D595B;font:inherit;font-weight:700;cursor:pointer`}>إضافة صنف يدوي</button>
    </section>
  );
}

export function OrderTotalsSummary({ items, discount = "0", deliveryFee = "0", currencySymbol = "" }) {
  const safeItems = items.map((item) => ({ ...item, unit_price: isMoney(item.unit_price) ? item.unit_price : "0" }));
  const safeDiscount = isMoney(discount) ? discount : "0";
  const safeDeliveryFee = isMoney(deliveryFee) ? deliveryFee : "0";
  const totals = calculateOrderTotals({ items: safeItems, discount: safeDiscount, deliveryFee: safeDeliveryFee });
  const rows = [["المجموع الفرعي", totals.subtotal], ["الخصم", safeDiscount], ["التوصيل", safeDeliveryFee], ["الإجمالي", totals.total]];
  return <dl dir="rtl" aria-label="ملخص إجمالي الطلب" style={sx`margin:0;display:grid;grid-template-columns:1fr auto;gap:8px;max-inline-size:340px;margin-inline-start:auto`}>
    {rows.map(([label, value]) => <Fragment key={label}><dt style={sx`font-size:14px;font-weight:${label === "الإجمالي" ? "800" : "500"}`}>{label}</dt><dd style={sx`margin:0;font-size:14px;font-weight:${label === "الإجمالي" ? "800" : "600"};text-align:end`}>{formatMoney(value, currencySymbol)}</dd></Fragment>)}
  </dl>;
}

const activityLabels = { order_created: "تم إنشاء الطلب", manual_order_created: "تم إنشاء الطلب اليدوي", order_completed: "اكتمل الطلب", order_reopened: "أعيد فتح الطلب", order_cancelled: "تم إلغاء الطلب", order_status_changed: "تم تغيير حالة الطلب", order_notes_updated: "تم تحديث الملاحظات", order_customer_updated: "تم تحديث بيانات العميل", order_item_added: "تمت إضافة صنف", order_item_removed: "تم حذف صنف", order_item_quantity_changed: "تم تحديث كمية الصنف", order_item_price_changed: "تم تحديث سعر الصنف", invoice_issued: "تم إصدار الفاتورة", invoice_replaced: "تم استبدال الفاتورة", invoice_cancelled: "تم إلغاء الفاتورة", payment_updated: "تم تحديث الدفع" };

export function OrderActivityTimeline({ activities = [] }) {
  if (!activities.length) return <p dir="rtl" style={sx`margin:0;color:#766669;font-size:13px`}>لا يوجد نشاط مسجل بعد.</p>;
  return <ol dir="rtl" aria-label="سجل نشاط الطلب" style={sx`list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:12px`}>
    {activities.map((activity) => <li key={activity.id} style={sx`border-inline-start:2px solid #E2D2D4;padding-inline-start:12px;display:flex;flex-direction:column;gap:3px`}>
      <strong style={sx`font-size:13px`}>{activityLabels[activity.event_type] || activity.event_type}</strong>
      {activity.reason && <span style={sx`font-size:13px;color:#5C4D4F`}>{activity.reason}</span>}
      {activity.created_at && <time dateTime={activity.created_at} style={sx`font-size:12px;color:#766669`}>{new Intl.DateTimeFormat("ar", { dateStyle: "medium", timeStyle: "short" }).format(new Date(activity.created_at))}</time>}
    </li>)}
  </ol>;
}

export function CompleteOrderDialog({ isOpen, order, onClose, onComplete, busy = false }) {
  const dialogRef = useRef(null);
  const firstFieldRef = useRef(null);
  const [paymentMethod, setPaymentMethod] = useState("cash_on_delivery");
  const [paidAmount, setPaidAmount] = useState("0.00");
  const [paymentDetails, setPaymentDetails] = useState("");
  const [invoiceNotes, setInvoiceNotes] = useState("");

  useEffect(() => {
    if (!isOpen) return undefined;
    const dialog = dialogRef.current;
    const previouslyFocused = document.activeElement;
    if (dialog?.showModal) dialog.showModal();
    else dialog?.setAttribute("open", "");
    firstFieldRef.current?.focus();
    return () => {
      if (dialog?.open && dialog.close) dialog.close();
      previouslyFocused?.focus?.();
    };
  }, [isOpen]);

  if (!isOpen) return null;
  const review = order?.final_review || order || {};
  const submit = (event) => {
    event.preventDefault();
    if (!isMoney(paidAmount)) return;
    onComplete({ payment_method: paymentMethod, paid_amount: paidAmount, payment_details: paymentDetails.trim() || null, invoice_notes: invoiceNotes.trim() || null });
  };
  return <dialog ref={dialogRef} aria-modal="true" aria-label="إتمام الطلب" onCancel={(event) => { event.preventDefault(); onClose(); }} onKeyDown={(event) => { if (event.key === "Escape") onClose(); }} style={sx`border:0;border-radius:16px;padding:0;max-inline-size:560px;inline-size:calc(100% - 32px);box-shadow:0 30px 70px rgba(26,24,21,.3)`}>
    <form dir="rtl" onSubmit={submit} style={sx`display:flex;flex-direction:column;gap:14px;padding:20px`}>
      <div><h2 style={sx`margin:0;font-size:18px`}>إتمام الطلب وإصدار الفاتورة</h2><p style={sx`margin:5px 0 0;color:#766669;font-size:13px`}>الإجمالي: {formatMoney(review.total ?? "0")}</p></div>
      <div aria-label="مراجعة الطلب النهائية" style={sx`background:#FAF3EA;border-radius:10px;padding:12px`}><OrderTotalsSummary items={review.items || []} discount={review.discount ?? "0"} deliveryFee={review.delivery_fee ?? "0"} /></div>
      <label style={sx`display:flex;flex-direction:column;gap:6px;font-size:13px;font-weight:700`}>طريقة الدفع<select ref={firstFieldRef} value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)} style={sx`height:42px;border:1px solid #E2D5C6;border-radius:8px;padding-inline:10px;font:inherit`}>{Object.entries(paymentMethodLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label style={sx`display:flex;flex-direction:column;gap:6px;font-size:13px;font-weight:700`}>المبلغ المدفوع<input inputMode="decimal" value={paidAmount} onChange={(event) => setPaidAmount(event.target.value)} aria-invalid={!isMoney(paidAmount)} style={sx`height:42px;box-sizing:border-box;border:1px solid #E2D5C6;border-radius:8px;padding-inline:10px;font:inherit`} /></label>
      <label style={sx`display:flex;flex-direction:column;gap:6px;font-size:13px;font-weight:700`}>تفاصيل الدفع (اختياري)<textarea value={paymentDetails} onChange={(event) => setPaymentDetails(event.target.value)} rows="3" style={sx`box-sizing:border-box;border:1px solid #E2D5C6;border-radius:8px;padding:10px;font:inherit;resize:vertical`} /></label>
      <label style={sx`display:flex;flex-direction:column;gap:6px;font-size:13px;font-weight:700`}>ملاحظات الفاتورة (اختياري)<textarea value={invoiceNotes} onChange={(event) => setInvoiceNotes(event.target.value)} rows="3" style={sx`box-sizing:border-box;border:1px solid #E2D5C6;border-radius:8px;padding:10px;font:inherit;resize:vertical`} /></label>
      <div style={sx`display:flex;justify-content:flex-start;gap:10px;flex-wrap:wrap`}><button type="button" onClick={onClose} disabled={busy} style={sx`min-height:42px;padding-inline:14px;border:1px solid #E2D5C6;border-radius:8px;background:#fff;font:inherit;font-weight:700;cursor:pointer`}>إلغاء</button><button type="submit" disabled={busy || !isMoney(paidAmount)} style={sx`min-height:42px;padding-inline:14px;border:1px solid #7D595B;border-radius:8px;background:#7D595B;color:#fff;font:inherit;font-weight:700;cursor:pointer`}>{busy ? "جارٍ الإتمام…" : "إتمام الطلب وإصدار الفاتورة"}</button></div>
    </form>
  </dialog>;
}
