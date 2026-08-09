import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import sx from "../../sx.js";
import { adminApi } from "../../api/adminApi.js";
import { useAdminAuth } from "../AdminAuth.jsx";
import {
  INVOICE_STATUSES,
  ORDER_SOURCES,
  PAYMENT_METHODS,
  PAYMENT_STATUSES,
  invoiceStatusLabels,
  isMoney,
  orderSourceLabels,
  paymentMethodLabels,
  paymentStatusLabels,
} from "../orderInvoice/domain.js";
import { OrderActivityTimeline } from "../orderInvoice/components.jsx";
import { formatDateTime } from "../../utils/format.js";
import { Badge, Button, Field, PageHeader, Pagination, Spinner, Table, card, input, textarea, useFeedback } from "../ui.jsx";

const amount = (value, symbol) => `${Number(value || 0).toFixed(2)} ${symbol || ""}`.trim();
const tone = (status) => ({ active: "good", cancelled: "bad", replaced: "warn", paid: "good", unpaid: "warn", partially_paid: "warn", refunded: "neutral", partially_refunded: "warn" }[status] || "neutral");

export function InvoicesPage() {
  const navigate = useNavigate();
  const feedback = useFeedback();
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [filters, setFilters] = useState({ q: "", status: "", payment_status: "", source: "", employee_id: "", issued_from: "", issued_to: "" });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.listInvoices({ page, page_size: 20, ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== "")) });
      setRows(result.items);
      setPages(result.pages || 1);
    } catch (error) {
      feedback.error(error.message || "تعذّر تحميل أرشيف الفواتير.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, filters]);

  useEffect(() => { load(); }, [load]);
  const change = (key) => (event) => {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: event.target.value }));
  };

  return <>
    <PageHeader title="أرشيف الفواتير" description="سجل مالي داخلي للبحث والمراجعة؛ الفواتير لا تُطبع أو تُشارك من هذه الشاشة." />
    {feedback.node}
    <section aria-label="مرشحات أرشيف الفواتير" style={{ ...card, ...sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:14px` }}>
      <Field title="بحث في الفواتير"><input type="search" value={filters.q} onChange={change("q")} placeholder="فاتورة أو طلب أو عميل" aria-label="بحث في الفواتير" style={input} /></Field>
      <Field title="حالة الفاتورة"><select value={filters.status} onChange={change("status")} aria-label="حالة الفاتورة" style={input}><option value="">كل الحالات</option>{INVOICE_STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <Field title="حالة الدفع"><select value={filters.payment_status} onChange={change("payment_status")} aria-label="حالة الدفع" style={input}><option value="">كل حالات الدفع</option>{PAYMENT_STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <Field title="مصدر الطلب"><select value={filters.source} onChange={change("source")} aria-label="مصدر الطلب" style={input}><option value="">كل المصادر</option>{ORDER_SOURCES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <Field title="رقم الموظف المصدر"><input type="number" min="1" value={filters.employee_id} onChange={change("employee_id")} aria-label="رقم الموظف المصدر" style={input} /></Field>
      <Field title="من تاريخ"><input type="date" value={filters.issued_from} onChange={change("issued_from")} aria-label="من تاريخ" style={input} /></Field>
      <Field title="إلى تاريخ"><input type="date" value={filters.issued_to} onChange={change("issued_to")} aria-label="إلى تاريخ" style={input} /></Field>
    </section>
    <div style={card}>{loading ? <Spinner label="جارٍ تحميل الأرشيف…" /> : <Table rows={rows} empty="لا توجد فواتير مطابقة للبحث." columns={[
      { key: "invoice_number", title: "رقم الفاتورة", render: (row) => <Link to={`/admin/invoices/${row.invoice_number}`} style={sx`font-weight:700`}>{row.invoice_number}</Link> },
      { key: "order_number", title: "الطلب", render: (row) => <Link to={`/admin/orders/${row.order_id}`}>{row.order_number}</Link> },
      { key: "customer_name", title: "العميل" },
      { key: "issued_at", title: "الإصدار", render: (row) => formatDateTime(row.issued_at) },
      { key: "grand_total", title: "الإجمالي النهائي", render: (row) => amount(row.grand_total, row.currency_symbol) },
      { key: "payment_status", title: "الدفع", render: (row) => <Badge tone={tone(row.payment_status)}>{paymentStatusLabels[row.payment_status] || row.payment_status}</Badge> },
      { key: "status", title: "الحالة", render: (row) => <Badge tone={tone(row.status)}>{invoiceStatusLabels[row.status] || row.status}</Badge> },
      { key: "actions", title: "", render: (row) => <Button variant="ghost" style={sx`min-height:36px;padding:0 12px;font-size:13px`} onClick={() => navigate(`/admin/invoices/${row.invoice_number}`)}>عرض</Button> },
    ]} />}</div>
    <Pagination page={page} pages={pages} onChange={setPage} />
  </>;
}

function InvoiceLinks({ invoice }) {
  const links = [...(invoice.history || []), invoice.replacement_invoice, invoice.replaces_invoice].filter((link) => link?.invoice_number && link.invoice_number !== invoice.invoice_number);
  const unique = [...new Map(links.map((link) => [link.invoice_number, link])).values()];
  if (!unique.length) return null;
  return <section style={{ ...card, ...sx`margin-bottom:14px` }}><h2 style={sx`margin:0 0 10px;font-size:16px`}>الفواتير المرتبطة</h2><div style={sx`display:flex;gap:10px;flex-wrap:wrap`}>{unique.map((link) => <Link key={link.invoice_number} to={`/admin/invoices/${link.invoice_number}`}>{link.invoice_number} · {invoiceStatusLabels[link.status] || link.status}</Link>)}</div></section>;
}

function PaymentEditor({ invoice, manager, onSave, busy }) {
  const [values, setValues] = useState({ paid_amount: String(invoice.paid_amount ?? "0"), refunded_amount: String(invoice.refunded_amount ?? "0"), payment_method: invoice.payment_method || "cash_on_delivery", payment_details: invoice.payment_details || "", reason: "" });
  const [error, setError] = useState("");
  useEffect(() => setValues({ paid_amount: String(invoice.paid_amount ?? "0"), refunded_amount: String(invoice.refunded_amount ?? "0"), payment_method: invoice.payment_method || "cash_on_delivery", payment_details: invoice.payment_details || "", reason: "" }), [invoice]);
  const change = (key) => (event) => setValues((current) => ({ ...current, [key]: event.target.value }));
  const submit = (event) => {
    event.preventDefault();
    const paid = Number(values.paid_amount);
    const refunded = Number(values.refunded_amount);
    const correction = paid < Number(invoice.paid_amount || 0) || refunded !== Number(invoice.refunded_amount || 0);
    if (!isMoney(values.paid_amount) || (manager && !isMoney(values.refunded_amount)) || paid > Number(invoice.grand_total) || refunded > paid) return setError("تحقق من المبالغ: لا يمكن أن يتجاوز المدفوع الإجمالي أو المسترد المدفوع.");
    if (!manager && paid < Number(invoice.paid_amount || 0)) return setError("لا يمكن تخفيض المدفوع إلا بواسطة مدير أعلى.");
    if (manager && correction && !values.reason.trim()) return setError("سبب التصحيح أو الاسترداد مطلوب.");
    setError("");
    onSave({ paid_amount: values.paid_amount, ...(manager ? { refunded_amount: values.refunded_amount, reason: correction ? values.reason.trim() : null } : {}), payment_method: values.payment_method, payment_details: values.payment_details.trim() || null });
  };
  if (invoice.status !== "active") return null;
  return <section style={{ ...card, ...sx`margin-bottom:14px` }}><h2 style={sx`margin:0 0 5px;font-size:16px`}>{manager ? "تصحيح أو استرداد الدفع" : "تسجيل دفعة"}</h2><p style={sx`margin:0 0 12px;font-size:13px;color:#7C766D`}>{manager ? "يُسجل السبب في النشاط عند تخفيض دفعة أو تسجيل استرداد." : "يمكن زيادة المبلغ المدفوع وتحديث طريقة وتفاصيل الدفع فقط."}</p><form dir="rtl" onSubmit={submit} style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px`}>
    <Field title="المبلغ المدفوع"><input inputMode="decimal" value={values.paid_amount} onChange={change("paid_amount")} aria-label="المبلغ المدفوع" aria-invalid={!!error} style={input} /></Field>
    <Field title="طريقة الدفع"><select value={values.payment_method} onChange={change("payment_method")} aria-label="طريقة الدفع" style={input}>{PAYMENT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
    {manager && <Field title="المبلغ المسترد"><input inputMode="decimal" value={values.refunded_amount} onChange={change("refunded_amount")} aria-label="المبلغ المسترد" aria-invalid={!!error} style={input} /></Field>}
    <div style={sx`grid-column:1 / -1`}><Field title="تفاصيل الدفع"><textarea rows="3" value={values.payment_details} onChange={change("payment_details")} aria-label="تفاصيل الدفع" style={textarea} /></Field></div>
    {manager && <div style={sx`grid-column:1 / -1`}><Field title="سبب التصحيح أو الاسترداد"><textarea rows="2" value={values.reason} onChange={change("reason")} aria-label="سبب التصحيح أو الاسترداد" style={textarea} /></Field></div>}
    {error && <p role="alert" style={sx`grid-column:1 / -1;margin:0;color:#8C2F22;font-size:13px`}>{error}</p>}
    <div style={sx`grid-column:1 / -1`}><Button type="submit" disabled={busy}>{busy ? "جارٍ الحفظ…" : "حفظ تحديث الدفع"}</Button></div>
  </form></section>;
}

export function InvoiceDetailPage() {
  const { invoiceNumber } = useParams();
  const navigate = useNavigate();
  const { isSuperAdmin } = useAdminAuth();
  const feedback = useFeedback();
  const [invoice, setInvoice] = useState(null);
  const [missing, setMissing] = useState(false);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    setMissing(false);
    try { setInvoice(await adminApi.getInvoice(invoiceNumber)); }
    catch (error) { setMissing(true); feedback.error(error.message || "تعذّر تحميل الفاتورة."); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoiceNumber]);
  useEffect(() => { load(); }, [load]);
  const savePayment = async (payload) => {
    setBusy(true);
    try { setInvoice(await adminApi.updateInvoicePayment(invoiceNumber, payload)); feedback.success("تم حفظ تحديث الدفع."); }
    catch (error) { feedback.error(error.message || "تعذّر حفظ تحديث الدفع."); }
    finally { setBusy(false); }
  };
  if (missing) return <><PageHeader title="الفاتورة غير موجودة" actions={<Button variant="ghost" onClick={() => navigate("/admin/invoices")}>رجوع</Button>} />{feedback.node}</>;
  if (!invoice) return <Spinner label="جارٍ تحميل الفاتورة…" />;
  const symbol = invoice.currency_symbol;
  return <>
    <PageHeader title={`الفاتورة ${invoice.invoice_number}`} description={`الطلب ${invoice.order_number} · ${formatDateTime(invoice.issued_at)}`} actions={<><Button variant="ghost" onClick={() => navigate("/admin/invoices")}>رجوع</Button><Button variant="ghost" onClick={() => navigate(`/admin/orders/${invoice.order_id}`)}>عرض الطلب</Button></>} />
    {feedback.node}
    <section aria-label="تفاصيل الفاتورة" style={{ ...card, ...sx`margin-bottom:14px` }}><div style={sx`display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px`}><Badge tone={tone(invoice.status)}>{invoiceStatusLabels[invoice.status] || invoice.status}</Badge><Badge tone={tone(invoice.payment_status)}>{paymentStatusLabels[invoice.payment_status] || invoice.payment_status}</Badge><span style={sx`font-size:13px;color:#7C766D`}>{paymentMethodLabels[invoice.payment_method] || invoice.payment_method}</span></div>
      <div style={sx`overflow-x:auto`}><table style={sx`width:max-content;min-width:100%;border-collapse:collapse`}><thead><tr>{["الصنف", "الخيار", "سعر البيع النهائي", "الكمية", "الإجمالي النهائي"].map((title) => <th key={title} style={sx`text-align:start;padding:9px;border-bottom:1px solid #E4E0D9;font-size:13px`}>{title}</th>)}</tr></thead><tbody>{(invoice.items || []).map((item) => <tr key={item.id}><td style={sx`padding:9px;border-bottom:1px solid #F2EFE9`}>{item.product_name}</td><td style={sx`padding:9px;border-bottom:1px solid #F2EFE9`}>{item.variant_description || "—"}</td><td style={sx`padding:9px;border-bottom:1px solid #F2EFE9`}>{amount(item.unit_price, symbol)}</td><td style={sx`padding:9px;border-bottom:1px solid #F2EFE9`}>{item.quantity}</td><td style={sx`padding:9px;border-bottom:1px solid #F2EFE9`}>{amount(item.line_total, symbol)}</td></tr>)}</tbody></table></div>
      <dl aria-label="ملخص الأسعار النهائية" style={sx`margin:16px 0 0;display:grid;grid-template-columns:1fr auto;gap:8px;max-width:360px;margin-inline-start:auto`}><dt>المجموع الفرعي</dt><dd>{amount(invoice.subtotal, symbol)}</dd><dt>التوصيل</dt><dd>{amount(invoice.delivery_fee, symbol)}</dd><dt style={sx`font-weight:800;border-top:1px solid #1F4E4A;padding-top:8px`}>الإجمالي النهائي</dt><dd style={sx`font-weight:800;border-top:1px solid #1F4E4A;padding-top:8px`}>{amount(invoice.grand_total, symbol)}</dd><dt>المدفوع / المسترد / المتبقي</dt><dd>{amount(invoice.paid_amount, symbol)} / {amount(invoice.refunded_amount, symbol)} / {amount(invoice.remaining_amount, symbol)}</dd></dl>
    </section>
    <PaymentEditor invoice={invoice} manager={isSuperAdmin} onSave={savePayment} busy={busy} />
    <InvoiceLinks invoice={invoice} />
    <section style={card}><h2 style={sx`margin:0 0 12px;font-size:16px`}>سجل النشاط</h2><OrderActivityTimeline activities={invoice.activities || []} /></section>
  </>;
}
