import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import sx from "../../sx.js";
import { adminApi } from "../../api/adminApi.js";
import { formatDateTime } from "../../utils/format.js";
import { useAdminAuth } from "../AdminAuth.jsx";
import {
  Badge, Button, ConfirmDialog, Field, PageHeader, Pagination, Spinner, Table, card, input, textarea, useFeedback,
} from "../ui.jsx";
import {
  CompleteOrderDialog, InvoiceStatusBadge, OrderActivityTimeline, OrderStatusBadge, OrderTotalsSummary, PaymentStatusBadge,
} from "../orderInvoice/components.jsx";
import {
  ORDER_SOURCES, ORDER_STATUSES, PAYMENT_STATUSES, PAYMENT_METHODS, canCompleteOrder, canEditIncompleteOrder,
  canReopenOrder, isMoney, isWholeQuantity, orderSourceLabels, orderStatusLabels, paymentMethodLabels, paymentStatusLabels,
} from "../orderInvoice/domain.js";

const filterStyle = sx`display:flex;flex-direction:column;gap:5px;font-size:12px;font-weight:700;min-width:130px;flex:1`;
const asText = (value) => String(value ?? "");
const phoneDigits = (phone) => String(phone || "").replace(/[^\d]/g, "");
const number = (value) => (Number.isFinite(Number(value)) ? Number(value) : 0);

function OrderFilters({ values, onChange }) {
  const update = (key, value) => onChange({ ...values, [key]: value });
  return <div style={{ ...card, ...sx`display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px` }}>
    <label style={{ ...filterStyle, ...sx`flex:2;min-width:210px` }}>بحث
      <input type="search" value={values.q} onChange={(event) => update("q", event.target.value)} placeholder="رقم الطلب أو العميل أو الهاتف…" style={input} />
    </label>
    <label style={filterStyle}>الحالة
      <select value={values.status} onChange={(event) => update("status", event.target.value)} style={input}><option value="">كل الحالات</option>{ORDER_STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
    </label>
    <label style={filterStyle}>المصدر
      <select value={values.source} onChange={(event) => update("source", event.target.value)} style={input}><option value="">كل المصادر</option>{ORDER_SOURCES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
    </label>
    <label style={filterStyle}>حالة الدفع
      <select value={values.payment_status} onChange={(event) => update("payment_status", event.target.value)} style={input}><option value="">كل حالات الدفع</option>{PAYMENT_STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
    </label>
    <label style={filterStyle}>من تاريخ<input type="date" value={values.date_from} onChange={(event) => update("date_from", event.target.value)} style={input} /></label>
    <label style={filterStyle}>إلى تاريخ<input type="date" value={values.date_to} onChange={(event) => update("date_to", event.target.value)} style={input} /></label>
  </div>;
}

export function OrdersPage() {
  const navigate = useNavigate();
  const feedback = useFeedback();
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [filters, setFilters] = useState({ q: "", status: "", source: "", payment_status: "", date_from: "", date_to: "" });
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.listOrders({ page, page_size: 20, ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value)) });
      setRows(result.items); setPages(result.pages || 1);
    } catch (error) { feedback.error(error.message || "تعذّر تحميل الطلبات."); }
    finally { setLoading(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, filters]);
  useEffect(() => { load(); }, [load]);
  const changeFilters = (next) => { setPage(1); setFilters(next); };
  return <>
    <PageHeader title="الطلبات" description="بحث ومتابعة الطلبات من كل القنوات." />
    {feedback.node}<OrderFilters values={filters} onChange={changeFilters} />
    <div style={card}>{loading ? <Spinner /> : <Table rows={rows} empty="لا توجد طلبات مطابقة." columns={[
      { key: "order_number", title: "رقم الطلب", render: (row) => <Link to={`/admin/orders/${row.id}`} style={sx`font-weight:800`}>{row.order_number}</Link> },
      { key: "customer", title: "العميل", render: (row) => <div style={sx`display:flex;flex-direction:column;gap:4px`}><strong>{row.customer_name}</strong><a aria-label={`واتساب مع ${row.customer_name}`} href={`https://wa.me/${phoneDigits(row.customer_phone)}`} target="_blank" rel="noreferrer" style={sx`color:#3F6B54;font-size:12px;font-weight:700`}>واتساب</a></div> },
      { key: "source", title: "المصدر", render: (row) => orderSourceLabels[row.source] || row.source || "—" },
      { key: "items_count", title: "الأصناف" }, { key: "total", title: "الإجمالي", render: (row) => Math.round(number(row.total)) },
      { key: "payment", title: "الدفع", render: (row) => <div style={sx`display:flex;flex-direction:column;gap:4px`}><span>{paymentMethodLabels[row.payment_method] || row.payment_method}</span><PaymentStatusBadge status={row.payment_status} /></div> },
      { key: "status", title: "الحالة", render: (row) => <OrderStatusBadge status={row.status} /> },
      { key: "created_at", title: "التاريخ", render: (row) => formatDateTime(row.created_at) },
      { key: "actions", title: "", render: (row) => <Button variant="ghost" aria-label={`عرض الطلب ${row.order_number}`} style={sx`min-height:36px;padding:0 12px;font-size:13px`} onClick={() => navigate(`/admin/orders/${row.id}`)}>عرض</Button> },
    ]} />}</div><Pagination page={page} pages={pages} onChange={setPage} />
  </>;
}

function CatalogItemsEditor({ items, products, onChange, disabled }) {
  const [productId, setProductId] = useState("");
  const update = (index, key, value) => onChange(items.map((item, itemIndex) => itemIndex === index ? { ...item, [key]: value } : item));
  const add = () => {
    const product = products.find((row) => String(row.id) === productId);
    if (!product || items.some((item) => item.product_id === product.id && !item.variant_id)) return;
    onChange([...items, { kind: "catalog", product_id: product.id, product_name: product.name, sku: product.sku, quantity: 1, unit_price: asText(product.price) }]); setProductId("");
  };
  return <section aria-label="أصناف الطلب" style={sx`display:flex;flex-direction:column;gap:10px`}>
    {items.map((item, index) => item.kind === "manual" ? <fieldset key={item.order_item_id || `manual-${index}`} disabled={disabled} style={sx`border:1px solid #E9DED0;border-radius:10px;padding:12px;display:grid;grid-template-columns:minmax(130px,1fr) minmax(130px,1fr) 90px 120px auto;gap:10px;align-items:end`}>
      <legend style={sx`font-size:13px;font-weight:800;padding-inline:4px`}>صنف يدوي</legend>
      <label style={filterStyle}>الاسم<input aria-label={`اسم ${item.name}`} value={item.name} onChange={(event) => update(index, "name", event.target.value)} style={input} /></label>
      <label style={filterStyle}>الوصف<input aria-label={`وصف ${item.name}`} value={item.description} onChange={(event) => update(index, "description", event.target.value)} style={input} /></label>
      <label style={filterStyle}>الكمية<input aria-label={`كمية ${item.name}`} inputMode="numeric" value={item.quantity} onChange={(event) => update(index, "quantity", event.target.value)} style={input} /></label>
      <label style={filterStyle}>سعر الطلب<input aria-label={`سعر ${item.name}`} inputMode="decimal" value={item.unit_price} onChange={(event) => update(index, "unit_price", event.target.value)} style={input} /></label>
      <Button variant="danger" aria-label={`حذف ${item.name}`} disabled={disabled || items.length === 1} onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))}>حذف</Button>
    </fieldset> : <fieldset key={`${item.product_id}-${item.variant_id || "base"}`} disabled={disabled} style={sx`border:1px solid #E9DED0;border-radius:10px;padding:12px;display:grid;grid-template-columns:minmax(130px,1fr) 90px 120px auto;gap:10px;align-items:end`}>
      <legend style={sx`font-size:13px;font-weight:800;padding-inline:4px`}>{item.product_name}{item.variant_description ? ` · ${item.variant_description}` : ""}</legend>
      <span style={sx`font-size:12px;color:#766669`}>{item.sku || "بدون SKU"}</span>
      <label style={filterStyle}>الكمية<input aria-label={`كمية ${item.product_name}`} inputMode="numeric" value={item.quantity} onChange={(event) => update(index, "quantity", event.target.value)} style={input} /></label>
      <label style={filterStyle}>سعر الطلب<input aria-label={`سعر ${item.product_name}`} inputMode="decimal" value={item.unit_price} onChange={(event) => update(index, "unit_price", event.target.value)} style={input} /></label>
      <Button variant="danger" aria-label={`حذف ${item.product_name}`} disabled={disabled || items.length === 1} onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))}>حذف</Button>
    </fieldset>)}
    <div style={sx`display:flex;gap:8px;align-items:end;flex-wrap:wrap`}><label style={{ ...filterStyle, ...sx`min-width:240px;flex:1` }}>إضافة منتج من الكتالوج<select aria-label="إضافة منتج من الكتالوج" value={productId} onChange={(event) => setProductId(event.target.value)} disabled={disabled} style={input}><option value="">اختر منتجاً</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name} · {product.sku || "—"}</option>)}</select></label><Button variant="secondary" disabled={disabled || !productId} onClick={add}>إضافة</Button></div>
  </section>;
}

function ReadOnlyOrderItems({ order }) {
  return <section style={{ ...card, ...sx`margin-bottom:16px` }}><h2 style={sx`margin:0 0 12px;font-size:16px`}>أصناف الطلب</h2><Table rows={order.items || []} empty="لا توجد أصناف في هذا الطلب." columns={[
    { key: "product_name", title: "المنتج" },
    { key: "variant_description", title: "الخيار", render: (item) => item.variant_description || "—" },
    { key: "sku", title: "SKU", render: (item) => item.sku || "—" },
    { key: "unit_price", title: "سعر القطعة" },
    { key: "quantity", title: "الكمية" },
    { key: "line_total", title: "الإجمالي" },
  ]} /><div style={sx`margin-top:14px`}><OrderTotalsSummary items={order.items || []} discount={order.discount} deliveryFee={order.delivery_fee} /></div></section>;
}

const initialDraft = (row) => ({
  customer_name: row.customer_name || "", customer_phone: row.customer_phone || "", customer_email: row.customer_email || "", address: row.address || "", payment_method: row.payment_method || "cash_on_delivery", customer_notes: row.customer_notes || "", admin_notes: row.admin_notes || "", discount: asText(row.discount), delivery_fee: asText(row.delivery_fee), status: row.status, reason: "",
  items: (row.items || []).map((item) => item.product_id ? { ...item, kind: "catalog", quantity: asText(item.quantity), unit_price: asText(item.unit_price) } : { kind: "manual", order_item_id: item.id, name: item.product_name, description: item.manual_description || "", quantity: asText(item.quantity), unit_price: asText(item.unit_price) }),
});

export function OrderDetailPage() {
  const { orderId } = useParams(); const navigate = useNavigate(); const { admin } = useAdminAuth(); const feedback = useFeedback();
  const [order, setOrder] = useState(null); const [draft, setDraft] = useState(null); const [products, setProducts] = useState([]); const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false); const [nextStatus, setNextStatus] = useState(""); const [statusNote, setStatusNote] = useState(""); const [confirming, setConfirming] = useState(false); const [completing, setCompleting] = useState(false); const [reopenReason, setReopenReason] = useState(""); const [reopenConfirming, setReopenConfirming] = useState(false);
  const load = useCallback(async () => { setLoading(true); try { const row = await adminApi.getOrder(orderId); setOrder(row); setDraft(initialDraft(row)); setNextStatus(row.status); } catch (error) { feedback.error(error.message || "تعذّر تحميل الطلب."); } finally { setLoading(false); } // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId]);
  useEffect(() => { load(); }, [load]);
  const editable = canEditIncompleteOrder(admin, order);
  useEffect(() => { if (!editable || products.length) return; adminApi.listProducts({ page_size: 100 }).then((result) => setProducts(result.items || [])).catch(() => feedback.error("تعذّر تحميل الكتالوج.")); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editable]);
  const applyStatus = async () => { setBusy(true); try { const row = await adminApi.updateOrderStatus(orderId, nextStatus, statusNote.trim() || null); setOrder(row); setDraft(initialDraft(row)); setStatusNote(""); feedback.success("تم تحديث الحالة."); } catch (error) { feedback.error(error.message || "تعذّر تحديث الحالة."); } finally { setBusy(false); setConfirming(false); } };
  const saveOrder = async () => {
    if (!draft.reason.trim()) { feedback.error("سبب التعديل مطلوب."); return; }
    if (!draft.items.length || draft.items.some((item) => !isWholeQuantity(item.quantity) || !isMoney(item.unit_price))) { feedback.error("راجِع الكمية وسعر كل صنف."); return; }
    setBusy(true); try {
      const row = await adminApi.updateOrder(orderId, { ...draft, customer_email: draft.customer_email.trim() || null, customer_notes: draft.customer_notes.trim() || null, admin_notes: draft.admin_notes.trim() || null, discount: draft.discount || "0", delivery_fee: draft.delivery_fee || "0", items: draft.items.map((item) => item.kind === "manual" ? { kind: "manual", order_item_id: item.order_item_id, name: item.name, description: item.description.trim() || null, quantity: Number(item.quantity), unit_price: item.unit_price } : { kind: "catalog", product_id: item.product_id, variant_id: item.variant_id || null, quantity: Number(item.quantity), unit_price: item.unit_price }) });
      setOrder(row); setDraft(initialDraft(row)); setNextStatus(row.status); feedback.success("تم حفظ تعديلات الطلب.");
    } catch (error) { feedback.error(error.message || "تعذّر حفظ تعديلات الطلب."); } finally { setBusy(false); }
  };
  const openComplete = async () => { setBusy(true); try { const latest = await adminApi.getOrder(orderId); setOrder(latest); setDraft(initialDraft(latest)); setCompleting(true); } catch (error) { feedback.error(error.message || "تعذّر جلب المراجعة النهائية."); } finally { setBusy(false); } };
  const complete = async (payload) => { setBusy(true); try { const row = await adminApi.completeOrder(orderId, payload); setOrder(row); setDraft(initialDraft(row)); setCompleting(false); feedback.success("اكتمل الطلب وصُدرت الفاتورة."); } catch (error) { feedback.error(error.message || "تعذّر إتمام الطلب."); } finally { setBusy(false); } };
  const reopen = async () => { if (!reopenReason.trim()) { feedback.error("سبب إعادة الفتح مطلوب."); return; } setBusy(true); try { const row = await adminApi.reopenOrder(orderId, reopenReason.trim()); setOrder(row); setDraft(initialDraft(row)); setNextStatus(row.status); setReopenReason(""); setReopenConfirming(false); feedback.success("أعيد فتح الطلب واستُبدلت الفاتورة النشطة."); } catch (error) { feedback.error(error.message || "تعذّر إعادة فتح الطلب."); } finally { setBusy(false); } };
  if (loading) return <Spinner />; if (!order || !draft) return <p role="alert">تعذّر تحميل الطلب.</p>;
  const invoice = order.active_invoice || order.invoice;
  const canManageWorkflow = canCompleteOrder(admin, order);
  const invoiceHistory = order.invoices || (invoice ? [invoice] : []);
  return <>
    <PageHeader title={`الطلب ${order.order_number}`} description={`${orderSourceLabels[order.source] || order.source} · ${formatDateTime(order.created_at)}`} actions={<Button variant="ghost" onClick={() => navigate("/admin/orders")}>رجوع</Button>} />
    {feedback.node}
    <div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px;margin-bottom:16px`}>
      <section style={card}><h2 style={sx`margin:0 0 12px;font-size:16px`}>العميل</h2><p style={sx`margin:0;line-height:1.9`}>{order.customer_name}<br />{order.customer_phone}<br />{order.address}</p><a aria-label={`واتساب مع ${order.customer_name}`} href={`https://wa.me/${phoneDigits(order.customer_phone)}`} target="_blank" rel="noreferrer" style={sx`display:inline-block;margin-top:10px;color:#3F6B54;font-weight:800`}>فتح واتساب</a></section>
      <section style={card}><h2 style={sx`margin:0 0 12px;font-size:16px`}>الحالة والدفع</h2><div style={sx`display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px`}><OrderStatusBadge status={order.status} /><PaymentStatusBadge status={order.payment_status} /></div><p style={sx`margin:0;font-size:13px`}>{paymentMethodLabels[order.payment_method] || order.payment_method}</p>{invoice && <p style={sx`margin:12px 0 0`}><InvoiceStatusBadge status={invoice.status} /></p>}</section>
    </div>
    <section style={{ ...card, ...sx`margin-bottom:16px` }}><h2 style={sx`margin:0 0 12px;font-size:16px`}>الفاتورة</h2>{invoice ? <div style={sx`display:flex;align-items:center;gap:10px;flex-wrap:wrap`}><InvoiceStatusBadge status={invoice.status} /><Link to={`/admin/invoices/${invoice.invoice_number}`} style={sx`font-weight:800`}>{invoice.invoice_number}</Link><span style={sx`font-size:13px;color:#766669`}>صادرة</span>{invoice.issued_at && <span style={sx`font-size:13px;color:#766669`}>{formatDateTime(invoice.issued_at)}</span>}<div style={sx`display:flex;gap:8px;margin-inline-start:auto;flex-wrap:wrap`}><Button variant="ghost" onClick={() => navigate(`/admin/invoices/${invoice.invoice_number}`)}>عرض الفاتورة</Button></div></div> : <p style={sx`margin:0;color:#766669;font-size:13px`}>تصدر الفاتورة تلقائياً عند تغيير الحالة إلى «تم التأكيد».</p>}{invoiceHistory.length > 0 && <div aria-label="سجل الفواتير والاستبدالات" style={sx`display:flex;gap:10px;flex-wrap:wrap;margin-top:14px;padding-top:12px;border-top:1px solid #E9DED0`}>{invoiceHistory.map((entry) => <Link key={entry.invoice_number} to={`/admin/invoices/${entry.invoice_number}`} style={sx`font-size:13px;font-weight:800`}>{entry.invoice_number} <InvoiceStatusBadge status={entry.status} /></Link>)}</div>}</section>
    <ReadOnlyOrderItems order={order} />
    {editable && <section style={{ ...card, ...sx`margin-bottom:16px` }}><h2 style={sx`margin:0 0 14px;font-size:16px`}>تعديل الطلب</h2><div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-bottom:14px`}>
      {[["اسم العميل", "customer_name"], ["الهاتف", "customer_phone"], ["البريد الإلكتروني", "customer_email"], ["العنوان", "address"]].map(([label, key]) => <Field key={key} title={label}><input value={draft[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} style={input} /></Field>)}
      <Field title="طريقة الدفع"><select value={draft.payment_method} onChange={(event) => setDraft({ ...draft, payment_method: event.target.value })} style={input}>{PAYMENT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field><Field title="الخصم"><input inputMode="decimal" value={draft.discount} onChange={(event) => setDraft({ ...draft, discount: event.target.value })} style={input} /></Field><Field title="رسوم التوصيل"><input inputMode="decimal" value={draft.delivery_fee} onChange={(event) => setDraft({ ...draft, delivery_fee: event.target.value })} style={input} /></Field>
    </div><CatalogItemsEditor items={draft.items} products={products} onChange={(items) => setDraft({ ...draft, items })} disabled={busy} /><div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px;margin-top:14px`}><Field title="ملاحظات العميل"><textarea rows="3" value={draft.customer_notes} onChange={(event) => setDraft({ ...draft, customer_notes: event.target.value })} style={textarea} /></Field><Field title="ملاحظات داخلية"><textarea rows="3" value={draft.admin_notes} onChange={(event) => setDraft({ ...draft, admin_notes: event.target.value })} style={textarea} /></Field><Field title="سبب التعديل *" hint="يظهر في سجل النشاط."><textarea aria-label="سبب التعديل *" required rows="3" value={draft.reason} onChange={(event) => setDraft({ ...draft, reason: event.target.value })} style={textarea} /></Field></div><div style={sx`display:flex;justify-content:flex-start;gap:12px;align-items:start;flex-wrap:wrap;margin-top:14px`}><OrderTotalsSummary items={draft.items} discount={draft.discount} deliveryFee={draft.delivery_fee} /><Button disabled={busy || !draft.reason.trim()} onClick={saveOrder}>{busy ? "جارٍ الحفظ…" : "حفظ التعديلات"}</Button></div></section>}
    {canReopenOrder(admin, order) && <section style={{ ...card, ...sx`margin-bottom:16px;border-color:#E5C4BE;background:#FDF6F4` }}><h2 style={sx`margin:0 0 8px;font-size:16px`}>إعادة فتح الطلب المكتمل</h2><p style={sx`margin:0 0 12px;line-height:1.8;font-size:13px;color:#8E3B34`}>{invoice ? `سيتم استبدال الفاتورة النشطة ${invoice.invoice_number}` : "سيُعاد فتح الطلب لتصحيح بياناته."}، وستبقى الفاتورة السابقة متاحة في سجل الاستبدالات.</p><div style={sx`display:flex;gap:12px;align-items:end;flex-wrap:wrap`}><div style={sx`min-width:min(100%,320px);flex:1`}><Field title="سبب إعادة الفتح" hint="يسجل السبب في نشاط الطلب والفاتورة المستبدلة."><textarea aria-label="سبب إعادة الفتح" required rows="3" value={reopenReason} onChange={(event) => setReopenReason(event.target.value)} style={textarea} /></Field></div><Button variant="danger" disabled={busy || !reopenReason.trim()} onClick={() => setReopenConfirming(true)}>إعادة فتح الطلب</Button></div></section>}
    <section style={{ ...card, ...sx`margin-bottom:16px` }}><h2 style={sx`margin:0 0 12px;font-size:16px`}>تقدم الطلب</h2>{canManageWorkflow ? <div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;align-items:end`}><Field title="تغيير الحالة"><select disabled={busy || !canManageWorkflow} value={nextStatus} onChange={(event) => setNextStatus(event.target.value)} style={input}>{ORDER_STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field><Field title="ملاحظة الحالة"><input disabled={busy || !canManageWorkflow} value={statusNote} onChange={(event) => setStatusNote(event.target.value)} style={input} /></Field><Button disabled={busy || !canManageWorkflow || nextStatus === order.status} onClick={() => nextStatus === "cancelled" ? setConfirming(true) : applyStatus()}>تحديث الحالة</Button><Button disabled={busy || !canManageWorkflow} onClick={openComplete}>إتمام الطلب</Button></div> : <p style={sx`margin:0;color:#766669;font-size:13px`}>لا تملك صلاحية تعديل سير هذا الطلب.</p>}</section>
    <section style={{ ...card, ...sx`margin-bottom:30px` }}><h2 style={sx`margin:0 0 12px;font-size:16px`}>سجل النشاط</h2><OrderActivityTimeline activities={order.activities || []} /></section>
    {confirming && <ConfirmDialog title="تأكيد إلغاء الطلب" message="سيُلغى الطلب ولا يمكن إتمامه بعد ذلك." confirmLabel="إلغاء الطلب" onConfirm={applyStatus} onCancel={() => setConfirming(false)} />}
    {reopenConfirming && <ConfirmDialog title="تأكيد إعادة فتح الطلب" message="ستُستبدل الفاتورة النشطة، وسيبقى سجلها متاحاً للمراجعة." confirmLabel="تأكيد إعادة الفتح" onConfirm={reopen} onCancel={() => setReopenConfirming(false)} />}
    <CompleteOrderDialog isOpen={completing} order={order} busy={busy} onClose={() => setCompleting(false)} onComplete={complete} />
  </>;
}
