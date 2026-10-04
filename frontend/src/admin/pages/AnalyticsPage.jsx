import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../../api/adminApi.js";
import sx from "../../sx.js";
import { Button, Notice, PageHeader, Spinner, card } from "../ui.jsx";

const PERIODS = [
  ["today", "اليوم"],
  ["7d", "آخر 7 أيام"],
  ["30d", "آخر 30 يوم"],
];

const FUNNEL_STAGES = [
  ["product_views", "مشاهدة المنتجات"],
  ["add_to_cart", "الإضافة إلى السلة"],
  ["checkout_reached", "الوصول إلى إتمام الطلب"],
  ["order_completed", "إنشاء الطلب بنجاح"],
];

function nonnegativeNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, number) : 0;
}

function formatCount(value) {
  return nonnegativeNumber(value).toLocaleString("en-US");
}

function formatDuration(value) {
  const seconds = Math.round(nonnegativeNumber(value));
  const parts = [
    [Math.floor(seconds / 3600), "ساعة"],
    [Math.floor(seconds % 3600 / 60), "دقيقة"],
    [seconds % 60, "ثانية"],
  ];
  return parts.filter(([amount]) => amount > 0).map(([amount, unit]) => `${formatCount(amount)} ${unit}`).join(" و") || "0 ثانية";
}

function Metric({ label, value, note }) {
  return (
    <div style={{ ...card, minWidth: 0 }}>
      <span style={sx`display:block;font-size:13px;font-weight:700;color:#766669;margin-bottom:8px`}>{label}</span>
      <strong style={sx`display:block;font-size:30px;line-height:1.3;color:var(--admin-primary);font-variant-numeric:tabular-nums;overflow-wrap:anywhere`}>{value}</strong>
      {note && <small style={sx`display:block;margin-top:8px;color:#8A7F95;line-height:1.6`}>{note}</small>}
    </div>
  );
}

function Ranking({ title, note, rows, empty, renderName, valueKey, valueLabel, chartLabel }) {
  const values = rows.map((row) => nonnegativeNumber(row[valueKey]));
  const maxValue = Math.max(1, ...values);
  return (
    <section style={{ ...card, minWidth: 0 }}>
      <div style={sx`margin-bottom:12px`}>
        <h2 style={sx`margin:0 0 4px;font-size:16px;color:#3B3243`}>{title}</h2>
        {note && <p style={sx`margin:0;font-size:12.5px;color:#8A7F95;line-height:1.7`}>{note}</p>}
      </div>
      {rows.length === 0 ? (
        <p style={sx`margin:0;padding:24px 0;text-align:center;color:#8A7F95;font-size:13.5px`}>{empty}</p>
      ) : (
        <figure aria-label={chartLabel} style={sx`margin:0;min-width:0`}>
        <ol style={sx`list-style:none;margin:0;padding:0;display:grid;gap:8px`}>
          {rows.map((row, index) => (
            <li key={`${row.name}-${row.product_id || index}`} style={sx`display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:8px 12px;padding:10px 0;border-top:${index ? "1px solid #F3EBE0" : "0"}`}>
              <div style={sx`min-width:0;display:flex;align-items:center;gap:10px`}>
                <span aria-hidden="true" style={sx`width:25px;height:25px;flex:0 0 25px;border-radius:999px;background:var(--admin-soft);color:var(--admin-primary);display:grid;place-items:center;font-size:11px;font-weight:800`}>{index + 1}</span>
                <span style={sx`min-width:0;overflow-wrap:anywhere`}>{renderName ? renderName(row) : row.name}</span>
              </div>
              <strong style={sx`white-space:nowrap;font-size:13px;font-variant-numeric:tabular-nums`}>{formatCount(values[index])} {valueLabel}</strong>
              <div aria-hidden="true" style={sx`grid-column:1 / -1;height:10px;background:var(--admin-soft);border-radius:4px;overflow:hidden`}>
                <div data-view-bar style={{ width: `${values[index] / maxValue * 100}%`, height: "100%", background: "var(--admin-primary)", borderRadius: 4 }} />
              </div>
            </li>
          ))}
        </ol>
        </figure>
      )}
    </section>
  );
}

export default function AnalyticsPage() {
  const [period, setPeriod] = useState("today");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    adminApi.analytics(period)
      .then((payload) => { if (!cancelled) setData(payload); })
      .catch(() => { if (!cancelled) setError("تعذّر تحميل الإحصائيات حالياً. حاول مرة أخرى."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [period]);

  return (
    <div style={sx`min-width:0`}>
      <PageHeader
        title="الإحصائيات"
        description="ملخص لحركة الزوار والمنتجات الأكثر مشاهدة خلال الفترة المحددة."
        actions={(
          <div role="group" aria-label="الفترة الزمنية" style={sx`display:flex;gap:8px;flex-wrap:wrap;max-width:100%`}>
            {PERIODS.map(([value, label]) => (
              <Button key={value} variant={period === value ? "primary" : "ghost"} aria-pressed={period === value} onClick={() => setPeriod(value)}>{label}</Button>
            ))}
          </div>
        )}
      />

      {error && <Notice kind="error">{error}</Notice>}
      {data && !data.location_tracking_configured && (
        <Notice>قد لا تتوفر بيانات الموقع الجغرافي لبعض الزيارات.</Notice>
      )}
      {loading && !data ? <Spinner label="جارٍ تحميل الإحصائيات…" /> : data && (
        <>
          <div data-testid="analytics-summary" style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:12px;margin-bottom:16px;min-width:0`}>
            <Metric label="الزيارات" value={formatCount(data.sessions)} note="إجمالي الزيارات خلال الفترة المحددة." />
            <Metric label="الزوار الفريدون" value={formatCount(data.unique_visitors)} note="عدد الزوار المختلفين خلال الفترة المحددة." />
            <Metric label="متوسط مدة الزيارة" value={formatDuration(data.average_session_duration_seconds)} note="متوسط الوقت بين بداية الزيارة وآخر نشاط فيها." />
            <Metric label="الطلبات المكتملة عبر الموقع" value={formatCount(data.completed_orders)} note="طلبات أُنشئت بنجاح عبر الموقع، بغض النظر عن حالة تجهيزها لاحقاً." />
          </div>

          <div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:16px;align-items:start;min-width:0`}>
            <Ranking
              title="أماكن الزوار"
              note="أكثر الأماكن التي جاءت منها الزيارات."
              rows={data.top_locations || []}
              empty="لا توجد زيارات ضمن هذه الفترة بعد."
              valueKey="sessions"
              valueLabel="زيارة"
              chartLabel="مقارنة زيارات الأماكن"
            />
            <Ranking
              title="المنتجات الأكثر مشاهدة"
              note="المنتجات التي حازت على أكبر عدد من المشاهدات."
              rows={data.top_products || []}
              empty="لا توجد مشاهدات منتجات ضمن هذه الفترة بعد."
              valueKey="views"
              chartLabel="مقارنة مشاهدات المنتجات"
              valueLabel="مشاهدة"
              renderName={(row) => row.product_exists ? (
                <Link to={`/admin/products/${row.product_id}`} style={sx`color:var(--admin-primary);font-weight:700;text-decoration:none;overflow-wrap:anywhere`}>{row.name}</Link>
               ) : row.name}
            />
          </div>

          <section aria-label="مسار الشراء" style={{ ...card, marginTop: 16, minWidth: 0 }}>
            <h2 style={sx`margin:0 0 4px;font-size:16px;color:#3B3243`}>مسار الشراء</h2>
            <p style={sx`margin:0 0 16px;font-size:12.5px;color:#8A7F95;line-height:1.7`}>عدد مرات حدوث كل خطوة خلال الفترة المحددة؛ قد تتكرر الخطوة في الزيارة الواحدة.</p>
            <ol style={sx`list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:16px;min-width:0`}>
              {FUNNEL_STAGES.map(([key, label]) => (
                <li key={key} style={sx`min-width:0;display:grid;gap:8px`}>
                  <span style={sx`font-size:13px;color:#766669;font-weight:700`}>{label}</span>
                  <strong style={sx`font-size:24px;color:var(--admin-primary);font-variant-numeric:tabular-nums;overflow-wrap:anywhere`}>{formatCount(data.funnel?.[key])}</strong>
                </li>
              ))}
            </ol>
          </section>

          <section aria-label="السلات المتروكة" style={sx`margin-top:16px;min-width:0`}>
            <Metric label="السلات المتروكة" value={formatCount(data.abandoned_carts)} note="زيارات أُضيفت فيها منتجات إلى السلة خلال الفترة المحددة، ولم يُنشأ فيها طلب ناجح، وتجاوز آخر نشاط فيها مهلة الخمول المعتمدة." />
          </section>
        </>
      )}
    </div>
  );
}
