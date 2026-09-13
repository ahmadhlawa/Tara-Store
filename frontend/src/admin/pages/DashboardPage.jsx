import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../../api/adminApi.js";
import { orderStatusLabels } from "../../store.js";
import { Notice, PageHeader, Spinner } from "../ui.jsx";

const money = new Intl.NumberFormat("ar-PS", { maximumFractionDigits: 0 });
const shortDate = new Intl.DateTimeFormat("ar-PS", { day: "numeric", month: "short" });
const longDate = new Intl.DateTimeFormat("ar-PS", { day: "numeric", month: "long", year: "numeric" });
const STATUS_COLORS = ["#59415d", "#8c778f", "#b6a9b5", "#d5cbd1", "#9c887d", "#c7b8a7"];
const formatMoney = (value) => `${money.format(Number(value) || 0)} ₪`;
const dateValue = (value) => new Date(`${value}T00:00:00`);

const niceStep = (value) => {
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  return ([1, 2, 5, 10].find((candidate) => normalized <= candidate) || 10) * magnitude;
};

export const salesAxisTicks = (values) => {
  const maximum = Math.max(...values.map((value) => Number(value) || 0), 0);
  if (!maximum) return [0, 1];
  const step = niceStep(maximum / 4);
  const ceiling = Math.ceil(maximum / step) * step;
  return Array.from({ length: Math.round(ceiling / step) + 1 }, (_, index) => index * step);
};

export const orderAxisTicks = (values) => {
  const maximum = Math.max(...values.map((value) => Number(value) || 0), 0);
  if (!maximum) return [0, 1];
  const step = Math.max(1, Math.round(niceStep(maximum / 4)));
  const ceiling = Math.ceil(maximum / step) * step;
  return Array.from({ length: Math.floor(ceiling / step) + 1 }, (_, index) => index * step);
};

function Sparkline({ data }) {
  const values = data.map((row) => Number(row.total) || 0);
  const max = Math.max(...values, 1);
  const points = values.map((value, index) => `${(index * 176) / Math.max(values.length - 1, 1)},${45 - (value / max) * 39}`).join(" ");
  return <svg className="dashboard-sparkline" viewBox="0 0 176 48" role="img" aria-label="اتجاه المبيعات"><defs><linearGradient id="sparklineArea" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#80618c" stopOpacity=".28" /><stop offset="1" stopColor="#80618c" stopOpacity="0" /></linearGradient></defs><polygon points={`0,48 ${points} 176,48`} fill="url(#sparklineArea)" /><polyline points={points} /></svg>;
}

function OrdersDonut({ statuses }) {
  const rows = Object.entries(statuses || {}).filter(([, count]) => count > 0);
  const total = rows.reduce((sum, [, count]) => sum + count, 0);
  let offset = 0;
  return <div className="dashboard-donut-wrap"><div className="dashboard-donut-visual"><svg className="dashboard-donut" viewBox="0 0 42 42" role="img" aria-label={`توزيع ${total} طلبات`}><circle className="dashboard-donut__track" cx="21" cy="21" r="15.9" />{rows.map(([status, count], index) => { const length = (count / total) * 100; const circle = <circle key={status} cx="21" cy="21" r="15.9" pathLength="100" stroke={STATUS_COLORS[index]} strokeDasharray={`${length} ${100 - length}`} strokeDashoffset={-offset} />; offset += length; return circle; })}</svg><strong>{total}</strong></div><div className="dashboard-status-list">{rows.map(([status, count], index) => <span key={status}><i style={{ background: STATUS_COLORS[index] }} />{orderStatusLabels[status] || status} <b>{count}</b></span>)}</div></div>;
}

function SalesOrdersChart({ sales, orders }) {
  const [tooltipIndex, setTooltipIndex] = useState(null);
  const width = 900, height = 290, left = 62, right = 54, top = 18, bottom = 38;
  const tooltipWidth = 190, tooltipHeight = 80, tooltipGap = 12;
  const salesTicks = salesAxisTicks(sales.map((row) => row.total));
  const ordersTicks = orderAxisTicks(orders.map((row) => row.count));
  const salesMax = salesTicks.at(-1);
  const ordersMax = ordersTicks.at(-1);
  const x = (index) => left + (index * (width - left - right)) / Math.max(sales.length - 1, 1);
  const y = (value, max) => top + (1 - value / max) * (height - top - bottom);
  const salesPoints = sales.map((row, index) => `${x(index)},${y(Number(row.total) || 0, salesMax)}`).join(" ");
  const orderPoints = orders.map((row, index) => `${x(index)},${y(Number(row.count) || 0, ordersMax)}`).join(" ");
  const labelEvery = Math.max(1, Math.ceil(sales.length / 6));
  const tooltip = tooltipIndex === null ? null : sales[tooltipIndex];
  const pointX = tooltip ? x(tooltipIndex) : 0;
  const pointY = tooltip ? y(Number(tooltip.total) || 0, salesMax) : 0;
  const tooltipX = tooltip
    ? Math.max(left + 2, Math.min(width - right - tooltipWidth - 2,
      pointX + tooltipGap + tooltipWidth > width - right ? pointX - tooltipWidth - tooltipGap : pointX + tooltipGap))
    : 0;
  const tooltipY = tooltip
    ? Math.max(top + 2, Math.min(height - bottom - tooltipHeight - 2, pointY - tooltipHeight - tooltipGap))
    : 0;
  const orderCount = tooltip ? orders[tooltipIndex]?.count || 0 : 0;
  return <div className="dashboard-chart-scroll"><svg className="dashboard-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="رسم المبيعات والطلبات بمقياسين منفصلين"><defs><linearGradient id="salesArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#735277" stopOpacity=".24" /><stop offset="1" stopColor="#735277" stopOpacity="0" /></linearGradient><filter id="salesGlow"><feGaussianBlur stdDeviation="2.2" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter><filter id="tooltipShadow"><feDropShadow dx="0" dy="5" stdDeviation="6" floodColor="#4d3656" floodOpacity=".16" /></filter></defs>{salesTicks.map((tick) => { const lineY = y(tick, salesMax); return <g key={tick}><line x1={left} x2={width - right} y1={lineY} y2={lineY} className="dashboard-chart__grid" /><text x={left - 10} y={lineY + 4} textAnchor="end">{money.format(tick)}</text></g>; })}{ordersTicks.map((tick) => <text key={tick} x={width - right + 10} y={y(tick, ordersMax) + 4}>{tick}</text>)}{sales.length > 1 && <polygon points={`${left},${height - bottom} ${salesPoints} ${width - right},${height - bottom}`} fill="url(#salesArea)" />}<polyline points={orderPoints} className="dashboard-chart__orders" /><polyline points={salesPoints} className="dashboard-chart__sales" filter="url(#salesGlow)" />{sales.map((row, index) => <g key={row.date}><circle cx={x(index)} cy={y(Number(row.total) || 0, salesMax)} r="10" className="dashboard-chart__hit" onMouseEnter={() => setTooltipIndex(index)} onFocus={() => setTooltipIndex(index)} onMouseLeave={() => setTooltipIndex(null)} onBlur={() => setTooltipIndex(null)} tabIndex="0"><title>{shortDate.format(dateValue(row.date))} — المبيعات: {formatMoney(row.total)}، الطلبات: {orders[index]?.count || 0}</title></circle>{(index % labelEvery === 0 || index === sales.length - 1) && <text x={x(index)} y={height - 12} textAnchor="middle">{shortDate.format(dateValue(row.date))}</text>}</g>)}{tooltip && <g className="dashboard-chart__tooltip" transform={`translate(${tooltipX} ${tooltipY})`} filter="url(#tooltipShadow)"><rect width={tooltipWidth} height={tooltipHeight} rx="11" /><foreignObject width={tooltipWidth} height={tooltipHeight}><div xmlns="http://www.w3.org/1999/xhtml" className="dashboard-chart__tooltip-panel" dir="rtl"><div className="dashboard-chart__tooltip-date">{shortDate.format(dateValue(tooltip.date))}</div><div className="dashboard-chart__tooltip-row"><span>المبيعات:</span><bdi dir="ltr">{formatMoney(tooltip.total)}</bdi></div><div className="dashboard-chart__tooltip-row"><span>الطلبات:</span><bdi dir="ltr">{orderCount}</bdi></div></div></foreignObject></g>}<text className="dashboard-chart__axis" x="8" y="12">المبيعات (₪)</text><text className="dashboard-chart__axis" x={width - 8} y="12" textAnchor="end">الطلبات</text></svg></div>;
}

function KpiCard({ title, children, className = "" }) { return <section className={`dashboard-card dashboard-kpi ${className}`}><h2>{title}</h2>{children}</section>; }

export default function DashboardPage() {
  const [period, setPeriod] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { let ignore = false; setError(""); adminApi.dashboard(period).then((result) => { if (!ignore) setData(result); }).catch((cause) => { if (!ignore) setError(cause.message || "تعذّر تحميل لوحة التحكم."); }); return () => { ignore = true; }; }, [period]);
  const comparison = useMemo(() => { const previous = Number(data?.previous_month_sales) || 0; return previous ? ((Number(data.monthly_sales) - previous) / previous) * 100 : null; }, [data]);
  if (error) return <Notice kind="error">{error}</Notice>;
  if (!data) return <Spinner />;
  const lowStock = data.low_stock_items || [];
  return <div className="dashboard-page"><PageHeader title="لوحة التحكم" description="نظرة تشغيلية سريعة على أداء متجر تارا." /><div className="dashboard-kpi-grid">
    <KpiCard title="أداء المبيعات الشهري" className="dashboard-kpi--sales"><strong className="dashboard-kpi__value">{formatMoney(data.monthly_sales)}</strong><p className={comparison > 0 ? "is-positive" : comparison < 0 ? "is-negative" : ""}>{comparison === null ? "لا توجد بيانات مقارنة" : `${comparison > 0 ? "+" : ""}${comparison.toFixed(1)}% مقارنة بالشهر الماضي`}</p><Sparkline data={data.sales_by_day || []} /></KpiCard>
    <KpiCard title="أحدث الطلبات" className="dashboard-kpi--orders"><div className="dashboard-kpi__heading"><strong className="dashboard-kpi__value">{data.recent_orders_total}</strong><span>آخر 7 أيام</span></div>{data.recent_orders_total ? <OrdersDonut statuses={data.recent_orders_by_status} /> : <p className="dashboard-empty">لا توجد طلبات حديثة</p>}</KpiCard>
    <div className="dashboard-kpi-stack"><KpiCard title="مخزون حرج" className={data.low_stock_products ? "dashboard-kpi--stock is-critical" : "dashboard-kpi--stock"}><Link className="dashboard-kpi-link" to="/admin/products?stock=low"><strong className="dashboard-kpi__value">{data.low_stock_products}</strong><span>{data.low_stock_products ? "منتجات بحاجة لإعادة تعبئة" : "المخزون بحالة جيدة"}</span><span className="dashboard-thumbnails">{lowStock.slice(0, 3).map((item) => item.image_url ? <img key={`${item.product_id}-${item.variant_name || "base"}`} src={item.image_url} alt="" /> : <i key={`${item.product_id}-${item.variant_name || "base"}`}>{item.product_name.slice(0, 1)}</i>)}</span></Link></KpiCard><KpiCard title="أكواد الخصم النشطة" className="dashboard-kpi--coupons"><Link className="dashboard-kpi-link dashboard-kpi-link--row" to="/admin/coupons"><strong className="dashboard-kpi__value">{data.coupons_active}</strong><span>{data.coupons_active ? "كود متاح للاستخدام" : "لا توجد أكواد نشطة"}</span></Link></KpiCard></div>
  </div><section className="dashboard-card dashboard-analytics"><header className="dashboard-analytics__header"><div><h2>تحليل المبيعات والطلبات</h2><p>آخر {period} يوماً · البيانات اليومية</p></div><div className="dashboard-periods" aria-label="الفترة الزمنية">{[7, 30, 90].map((days) => <button key={days} className={period === days ? "is-active" : ""} aria-pressed={period === days} onClick={() => setPeriod(days)}>{days} أيام</button>)}</div></header><div className="dashboard-legend"><span><i className="sales" />المبيعات</span><span><i className="orders" />الطلبات</span></div><SalesOrdersChart sales={data.sales_by_day || []} orders={data.orders_by_day || []} /><div className="dashboard-insights"><div><span>متوسط قيمة الطلب</span><strong>{formatMoney(data.average_order_value)}</strong></div><div><span>أعلى يوم مبيعات</span><strong>{data.best_sales_day ? longDate.format(dateValue(data.best_sales_day.date)) : "لا توجد مبيعات"}</strong>{data.best_sales_day && <small>{formatMoney(data.best_sales_day.total)}</small>}</div></div></section>
  <section className="dashboard-card dashboard-stock"><h2>جدول المخزون المنخفض</h2>{lowStock.length ? <div className="dashboard-table-scroll"><table><thead><tr><th>المنتج</th><th>الاسم</th><th>المتغير</th><th>المخزون</th><th>حد التنبيه</th><th>الإجراء</th></tr></thead><tbody>{lowStock.map((item) => <tr key={`${item.product_id}-${item.variant_name || "base"}`}><td>{item.image_url ? <img src={item.image_url} alt="" /> : <span className="dashboard-product-placeholder">{item.product_name.slice(0, 1)}</span>}</td><td><b>{item.product_name}</b>{item.sku && <small>{item.sku}</small>}</td><td>{item.variant_name || "—"}</td><td><strong>{item.stock}</strong></td><td>{item.threshold}</td><td><Link to={`/admin/products/${item.product_id}`}>تعديل</Link></td></tr>)}</tbody></table></div> : <p className="dashboard-stock__empty">المخزون بحالة جيدة، لا توجد منتجات منخفضة.</p>}</section></div>;
}
