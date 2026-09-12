import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import sx from "../../sx.js";
import { adminApi } from "../../api/adminApi.js";
import { Button, Field, PageHeader, Spinner, card, input, textarea, useFeedback } from "../ui.jsx";
import { ORDER_SOURCES, PAYMENT_METHODS, calculateOrderTotals, formatMoney, isMoney, isWholeQuantity, orderSourceLabels } from "../orderInvoice/domain.js";
import CatalogItemPicker from "../orderInvoice/CatalogItemPicker.jsx";

const manualSources = ORDER_SOURCES;
const blankManualItem = () => ({ kind: "manual", name: "", description: "", quantity: "1", unit_price: "" });
const initialValues = () => ({
  source: "whatsapp", source_note: "", customer_name: "", customer_phone: "", customer_email: "", address: "",
  payment_method: "cash_on_delivery", customer_notes: "", admin_notes: "", discount: "0.00", delivery_fee: "0.00",
  items: [], complete: false, paid_amount: "0.00", payment_details: "", invoice_notes: "",
});

function OrderLines({ items, products, catalogQuery, onCatalogQueryChange, onCatalogSearch, onChange, disabled }) {
  const update = (index, values) => onChange(items.map((item, itemIndex) => itemIndex === index ? { ...item, ...values } : item));
  return <section aria-label="أصناف الطلب اليدوي" style={sx`display:flex;flex-direction:column;gap:10px`}>
    {items.map((item, index) => <fieldset key={`${item.kind}-${item.product_id || index}`} disabled={disabled} style={sx`border:1px solid #E7DCF2;border-radius:10px;padding:12px;display:grid;grid-template-columns:minmax(140px,1fr) 90px 120px auto;gap:10px;align-items:end`}>
      <legend style={sx`font-size:13px;font-weight:800;padding-inline:4px`}>{item.kind === "catalog" ? item.product_name : `صنف يدوي ${index + 1}`}</legend>
      {item.kind === "manual" ? <><Field title="اسم الصنف"><input aria-label={`اسم الصنف اليدوي ${index + 1}`} required value={item.name} onChange={(event) => update(index, { name: event.target.value })} style={input} /></Field><Field title="الوصف"><input aria-label={`وصف الصنف اليدوي ${index + 1}`} value={item.description} onChange={(event) => update(index, { description: event.target.value })} style={input} /></Field></> : <span style={sx`font-size:12px;color:#766669;align-self:center`}>{item.variant_description || item.sku || "بدون خيارات"}</span>}
      <Field title="الكمية"><input aria-label={`كمية الصنف ${index + 1}`} inputMode="numeric" required value={item.quantity} onChange={(event) => update(index, { quantity: event.target.value })} style={input} /></Field>
      <Field title="سعر القطعة" hint={item.kind === "catalog" ? "سعر الكتالوج؛ تغييره يُعد تجاوزاً إدارياً." : undefined}><input aria-label={item.kind === "manual" ? `سعر الصنف اليدوي ${index + 1}` : `سعر الصنف ${index + 1}`} inputMode="decimal" required value={item.unit_price} onChange={(event) => update(index, { unit_price: event.target.value })} style={input} /></Field>
      <div style={sx`display:flex;gap:8px;align-items:center`}><span style={sx`font-size:12px;font-weight:800`}>الإجمالي: {isMoney(item.unit_price) && isWholeQuantity(item.quantity) ? formatMoney(Number(item.unit_price) * Number(item.quantity)) : "—"}</span><Button variant="danger" aria-label={`حذف الصنف ${index + 1}`} disabled={disabled} onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))}>حذف</Button></div>
    </fieldset>)}
    <div style={sx`display:flex;gap:8px;align-items:end;flex-wrap:wrap`}><Field title="بحث في الكتالوج"><input aria-label="بحث في الكتالوج" type="search" value={catalogQuery} onChange={(event) => onCatalogQueryChange(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); onCatalogSearch(); } }} disabled={disabled} style={input} /></Field><Button variant="secondary" disabled={disabled} onClick={onCatalogSearch}>بحث</Button><CatalogItemPicker products={products} disabled={disabled} onAdd={(item) => onChange([...items, item])} /><Button variant="secondary" disabled={disabled} onClick={() => onChange([...items, blankManualItem()])}>إضافة صنف يدوي</Button></div>
  </section>;
}

export default function ManualOrderPage() {
  const navigate = useNavigate();
  const feedback = useFeedback();
  const [values, setValues] = useState(initialValues);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [catalogQuery, setCatalogQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const change = (key) => (event) => setValues((current) => ({ ...current, [key]: event.target.type === "checkbox" ? event.target.checked : event.target.value }));
  const load = useCallback(async (query = "") => {
    setCatalogBusy(true);
    try { const result = await adminApi.listProducts({ page_size: 100, ...(query ? { q: query } : {}) }); setProducts(result.items || []); }
    catch (error) { feedback.error(error.message || "تعذّر تحميل الكتالوج."); }
    finally { setLoading(false); setCatalogBusy(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { load(); }, [load]);
  const totals = useMemo(() => calculateOrderTotals({ items: values.items.filter((item) => isWholeQuantity(item.quantity) && isMoney(item.unit_price)), discount: isMoney(values.discount) ? values.discount : "0", delivery_fee: isMoney(values.delivery_fee) ? values.delivery_fee : "0" }), [values.items, values.discount, values.delivery_fee]);
  const submit = async (event) => {
    event.preventDefault();
    if (!values.items.length || values.items.some((item) => !isWholeQuantity(item.quantity) || !isMoney(item.unit_price) || (item.kind === "manual" && !item.name.trim()))) return feedback.error("أضف صنفاً واحداً صحيحاً على الأقل، مع كمية وسعر صالحين.");
    if (!isMoney(values.discount) || !isMoney(values.delivery_fee)) return feedback.error("تحقق من الخصم ورسوم التوصيل.");
    if (values.source === "other" && !values.source_note.trim()) return feedback.error("ملاحظة المصدر مطلوبة عند اختيار «أخرى».");
    if (values.complete && !isMoney(values.paid_amount)) return feedback.error("تحقق من المبلغ المدفوع قبل الإتمام.");
    const payload = {
      source: values.source, source_note: values.source_note.trim() || null, customer_name: values.customer_name.trim(), customer_phone: values.customer_phone.trim(), customer_email: values.customer_email.trim() || null, address: values.address.trim(), payment_method: values.payment_method,
      customer_notes: values.customer_notes.trim() || null, admin_notes: values.admin_notes.trim() || null, discount: values.discount, delivery_fee: values.delivery_fee,
      items: values.items.map((item) => item.kind === "catalog" ? { kind: "catalog", product_id: item.product_id, variant_id: item.variant_id || null, selected_option_value_ids: item.selected_option_value_ids || [], quantity: Number(item.quantity), unit_price: item.unit_price } : { kind: "manual", name: item.name.trim(), description: item.description.trim() || null, quantity: Number(item.quantity), unit_price: item.unit_price }),
      ...(values.complete ? { completion: { payment_method: values.payment_method, paid_amount: values.paid_amount, payment_details: values.payment_details.trim() || null, invoice_notes: values.invoice_notes.trim() || null } } : {}),
    };
    setBusy(true);
    try { const order = await adminApi.createManualOrder(payload); navigate(`/admin/orders/${order.id}`); }
    catch (error) { feedback.error(error.message || "تعذّر حفظ الطلب اليدوي."); }
    finally { setBusy(false); }
  };
  if (loading) return <Spinner label="جارٍ تحميل الكتالوج…" />;
  return <>
    <PageHeader title="طلب يدوي جديد" description="سجّل طلباً من قناة خارج الموقع، ثم احفظه غير مكتمل أو أتمّه لإصدار فاتورة." actions={<Button variant="ghost" onClick={() => navigate("/admin/orders")}>رجوع</Button>} />
    {feedback.node}
    <form dir="rtl" onSubmit={submit} style={sx`display:flex;flex-direction:column;gap:16px`}>
      <section style={card}><h2 style={sx`margin:0 0 14px;font-size:16px`}>المصدر والعميل</h2><div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px`}>
        <Field title="المصدر"><select aria-label="المصدر" value={values.source} onChange={change("source")} style={input}>{manualSources.map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select></Field>
        <Field title="ملاحظة المصدر" hint={values.source === "other" ? "مطلوبة للمصدر الآخر." : "اختيارية."}><input required={values.source === "other"} value={values.source_note} onChange={change("source_note")} style={input} /></Field>
        <Field title="اسم العميل"><input aria-label="اسم العميل" required value={values.customer_name} onChange={change("customer_name")} style={input} /></Field><Field title="الهاتف"><input aria-label="الهاتف" required inputMode="tel" value={values.customer_phone} onChange={change("customer_phone")} style={input} /></Field><Field title="البريد الإلكتروني"><input type="email" value={values.customer_email} onChange={change("customer_email")} style={input} /></Field><Field title="العنوان"><input aria-label="العنوان" required value={values.address} onChange={change("address")} style={input} /></Field>
      </div></section>
      <section style={card}><h2 style={sx`margin:0 0 14px;font-size:16px`}>الأصناف والأسعار</h2><OrderLines items={values.items} products={products} catalogQuery={catalogQuery} onCatalogQueryChange={setCatalogQuery} onCatalogSearch={() => load(catalogQuery.trim())} disabled={busy || catalogBusy} onChange={(items) => setValues((current) => ({ ...current, items }))} /></section>
      <section style={card}><h2 style={sx`margin:0 0 14px;font-size:16px`}>الدفع والملاحظات</h2><div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px`}><Field title="طريقة الدفع"><select value={values.payment_method} onChange={change("payment_method")} style={input}>{PAYMENT_METHODS.map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select></Field><Field title="الخصم"><input aria-label="الخصم" inputMode="decimal" value={values.discount} onChange={change("discount")} style={input} /></Field><Field title="رسوم التوصيل"><input aria-label="رسوم التوصيل" inputMode="decimal" value={values.delivery_fee} onChange={change("delivery_fee")} style={input} /></Field><Field title="ملاحظات العميل"><textarea aria-label="ملاحظات العميل" rows="3" value={values.customer_notes} onChange={change("customer_notes")} style={textarea} /></Field><Field title="ملاحظات داخلية"><textarea aria-label="ملاحظات داخلية" rows="3" value={values.admin_notes} onChange={change("admin_notes")} style={textarea} /></Field></div></section>
      <section style={card}><label style={sx`display:flex;align-items:center;gap:9px;font-weight:800;cursor:pointer`}><input aria-label="إتمام الطلب وإصدار فاتورة" type="checkbox" checked={values.complete} onChange={change("complete")} />إتمام الطلب وإصدار فاتورة</label>{values.complete && <div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:14px`}><Field title="المبلغ المدفوع"><input aria-label="المبلغ المدفوع" inputMode="decimal" value={values.paid_amount} onChange={change("paid_amount")} style={input} /></Field><Field title="تفاصيل الدفع"><input aria-label="تفاصيل الدفع" value={values.payment_details} onChange={change("payment_details")} style={input} /></Field><Field title="ملاحظات الفاتورة"><input value={values.invoice_notes} onChange={change("invoice_notes")} style={input} /></Field></div>}<div aria-label="ملخص إجمالي الطلب" style={sx`margin-top:16px;padding:12px;border-radius:10px;background:#FAF3EA;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-weight:800`}><span>المجموع الفرعي: {formatMoney(totals.subtotal)}</span><span>الإجمالي: {formatMoney(totals.total)}</span></div><div style={sx`display:flex;gap:10px;flex-wrap:wrap;margin-top:14px`}><Button type="submit" disabled={busy}>{busy ? "جارٍ الحفظ…" : "حفظ الطلب اليدوي"}</Button><Button variant="ghost" disabled={busy} onClick={() => setValues(initialValues())}>إعادة تعيين</Button></div></section>
    </form>
  </>;
}
