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
