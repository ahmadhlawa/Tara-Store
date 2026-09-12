import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import sx from "../../sx.js";
import { adminApi } from "../../api/adminApi.js";
import { orderStatusLabels } from "../../store.js";
import { formatDateTime } from "../../utils/format.js";
import { Badge, Notice, PageHeader, Spinner, Table, card } from "../ui.jsx";

const STATUS_TONE = {
  pending: "warn",
  confirmed: "good",
  processing: "neutral",
  ready: "neutral",
  shipped: "neutral",
  delivered: "good",
  cancelled: "bad",
};

function Stat({ title, value, hint }) {
  return (
    <div className="admin-dashboard-stat" style={{ ...card, ...sx`display:flex;flex-direction:column;gap:6px` }}>
      <span style={sx`font-size:12.5px;color:#766669`}>{title}</span>
      <strong style={sx`font-size:26px;color:var(--admin-primary)`}>{value}</strong>
      {hint && <span style={sx`font-size:12px;color:#8A7F95`}>{hint}</span>}
    </div>
  );
}

function TrendChart({ title, totalLabel, data, valueKey }) {
  const width = 720;
  const height = 190;
  const values = data.map((row) => Number(row[valueKey]) || 0);
  const max = Math.max(...values, 1);
  const points = values.map((value, index) => {
    const x = 12 + (index * (width - 24)) / Math.max(values.length - 1, 1);
    const y = height - 24 - (value / max) * (height - 44);
    return `${x},${y}`;
  }).join(" ");
  return (
    <section style={{ ...card, ...sx`min-width:0` }}>
      <div style={sx`display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px`}>
        <div><h2 style={sx`margin:0 0 4px;font-size:16px`}>{title}</h2><span style={sx`font-size:12px;color:#766669`}>آخر 30 يوماً · يومياً</span></div>
        <strong style={sx`color:var(--admin-primary);font-size:20px`}>{totalLabel}</strong>
      </div>
      <div style={sx`overflow-x:auto`}>
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}: ${totalLabel}`} style={sx`display:block;width:100%;min-width:520px;height:auto`}>
          <line x1="12" y1={height - 24} x2={width - 12} y2={height - 24} stroke="#E7DCF2" />
          <polyline points={points} fill="none" stroke="var(--admin-primary)" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
          {data.map((row, index) => {
            const [x, y] = points.split(" ")[index].split(",");
            return <circle key={row.date} cx={x} cy={y} r="3.5" fill="var(--admin-primary)"><title>{row.date}: {row[valueKey]}</title></circle>;
          })}
          <text x="12" y={height - 6} fontSize="11" fill="#766669">{data[0]?.date}</text>
          <text x={width - 12} y={height - 6} textAnchor="end" fontSize="11" fill="#766669">{data.at(-1)?.date}</text>
        </svg>
      </div>
    </section>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    adminApi
      .dashboard()
      .then(setData)
      .catch((cause) => setError(cause.message || "تعذّر تحميل الملخّص."));
  }, []);

  if (error) return <Notice kind="error">{error}</Notice>;
  if (!data) return <Spinner />;

  return (
    <>
      <PageHeader title="لوحة التحكم" description="ملخّص سريع لحالة المتجر." />
      <div className="admin-dashboard-stats" style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:20px`}>
        <Stat title="إجمالي الطلبات" value={data.orders_total} hint={`${data.orders_pending} بانتظار المراجعة`} />
        <Stat title="إجمالي المبيعات" value={Math.round(data.revenue_total)} hint="الطلبات غير الملغاة" />
        <Stat title="المنتجات الفعّالة" value={data.products_active} hint={`من ${data.products_total} منتجاً`} />
        <Stat title="مخزون منخفض" value={data.low_stock_products} hint="منتجات وصلت حد التنبيه" />
        <Stat title="الأقسام" value={data.categories_total} />
        <Stat title="أكواد خصم فعّالة" value={data.coupons_active} />
      </div>

      <div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:14px;margin-bottom:20px`}>
        <TrendChart title="المبيعات" totalLabel={Math.round(data.period_sales_total || 0)} data={data.sales_by_day || []} valueKey="total" />
        <TrendChart title="الطلبات" totalLabel={data.period_orders_total || 0} data={data.orders_by_day || []} valueKey="count" />
      </div>

      <section style={{ ...card, ...sx`margin-bottom:20px` }}>
        <h2 style={sx`margin:0 0 12px;font-size:16px;font-weight:800`}>المخزون المنخفض</h2>
        {(data.low_stock_items || []).length ? (
          <div style={sx`display:flex;flex-direction:column;gap:8px`}>
            {data.low_stock_items.map((item) => (
              <Link key={`${item.product_id}-${item.variant_name || "product"}`} to={`/admin/products/${item.product_id}`} style={sx`display:flex;justify-content:space-between;gap:12px;padding:10px 12px;border:1px solid #E7DCF2;border-radius:10px;text-decoration:none;color:inherit`}>
                <span><strong>{item.product_name}</strong>{item.variant_name && <small style={sx`display:block;color:#766669`}>{item.variant_name}</small>}</span>
                <span style={sx`font-size:13px;text-align:end`}>المخزون: {item.stock}<small style={sx`display:block;color:#766669`}>التنبيه عند: {item.threshold}</small></span>
              </Link>
            ))}
          </div>
        ) : <p style={sx`margin:0;color:#4C7C63`}>المخزون بحالة جيدة.</p>}
      </section>

      <div className="admin-dashboard-orders" style={card}>
        <h2 style={sx`margin:0 0 12px;font-size:16px;font-weight:800`}>أحدث الطلبات</h2>
        <div className="admin-dashboard-orders-table">
          <Table
          columns={[
            {
              key: "order_number",
              title: "رقم الطلب",
              render: (row) => (
                <Link to={`/admin/orders/${row.id}`} style={sx`font-weight:700`}>{row.order_number}</Link>
              ),
            },
            { key: "customer_name", title: "العميل" },
            {
              key: "status",
              title: "الحالة",
              render: (row) => (
                <Badge tone={STATUS_TONE[row.status]}>{orderStatusLabels[row.status] || row.status}</Badge>
              ),
            },
            { key: "total", title: "الإجمالي", render: (row) => Math.round(row.total) },
            { key: "created_at", title: "التاريخ", render: (row) => formatDateTime(row.created_at) },
          ]}
            rows={data.recent_orders}
            empty="لا توجد طلبات بعد."
          />
        </div>
        <div className="admin-dashboard-orders-mobile">
          {data.recent_orders.length ? data.recent_orders.map((row) => (
            <Link key={row.id} to={`/admin/orders/${row.id}`} className="admin-dashboard-order-row">
              <span className="admin-dashboard-order-row__number">{row.order_number}</span>
              <span className="admin-dashboard-order-row__customer">{row.customer_name}</span>
              <Badge tone={STATUS_TONE[row.status]}>{orderStatusLabels[row.status] || row.status}</Badge>
            </Link>
          )) : <div className="admin-dashboard-order-empty">لا توجد طلبات بعد.</div>}
        </div>
      </div>
    </>
  );
}
