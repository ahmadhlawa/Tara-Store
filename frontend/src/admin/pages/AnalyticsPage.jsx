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

function Metric({ label, value, note }) {
  return (
    <div style={card}>
      <span style={sx`display:block;font-size:13px;font-weight:700;color:#766669;margin-bottom:8px`}>{label}</span>
      <strong style={sx`display:block;font-size:30px;line-height:1;color:var(--admin-primary);font-variant-numeric:tabular-nums`}>{Number(value || 0).toLocaleString("en-US")}</strong>
      {note && <small style={sx`display:block;margin-top:8px;color:#8A7F95;line-height:1.6`}>{note}</small>}
    </div>
  );
}

function Ranking({ title, note, rows, empty, renderName, valueKey, valueLabel }) {
  return (
    <section style={card}>
      <div style={sx`margin-bottom:12px`}>
        <h2 style={sx`margin:0 0 4px;font-size:16px;color:#3B3243`}>{title}</h2>
        {note && <p style={sx`margin:0;font-size:12.5px;color:#8A7F95;line-height:1.7`}>{note}</p>}
      </div>
      {rows.length === 0 ? (
        <p style={sx`margin:0;padding:24px 0;text-align:center;color:#8A7F95;font-size:13.5px`}>{empty}</p>
      ) : (
        <ol style={sx`list-style:none;margin:0;padding:0;display:grid;gap:8px`}>
          {rows.map((row, index) => (
            <li key={`${row.name}-${row.product_id || index}`} style={sx`display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:12px;padding:10px 0;border-top:${index ? "1px solid #F3EBE0" : "0"}`}>
              <div style={sx`min-width:0;display:flex;align-items:center;gap:10px`}>
                <span aria-hidden="true" style={sx`width:25px;height:25px;flex:0 0 25px;border-radius:999px;background:var(--admin-soft);color:var(--admin-primary);display:grid;place-items:center;font-size:11px;font-weight:800`}>{index + 1}</span>
                <span style={sx`min-width:0;overflow-wrap:anywhere`}>{renderName ? renderName(row) : row.name}</span>
              </div>
              <strong style={sx`white-space:nowrap;font-variant-numeric:tabular-nums`}>{Number(row[valueKey] || 0).toLocaleString("en-US")} <small style={sx`font-weight:500;color:#8A7F95`}>{valueLabel}</small></strong>
            </li>
          ))}
        </ol>
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
        description="الزيارات والزوار الفريدون وأماكن الزيارة والمنتجات الأكثر مشاهدة. الموقع الجغرافي تقريبي حسب شبكة الزائر."
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
        <Notice>الزيارات تعمل، لكن بيانات المدن ستبقى «غير محدد» حتى يكتمل إعداد Cloudflare/AOP على الخادم.</Notice>
      )}
      {loading && !data ? <Spinner label="جارٍ تحميل الإحصائيات…" /> : data && (
        <>
          <div data-testid="analytics-summary" style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:12px;margin-bottom:16px;min-width:0`}>
            <Metric label="الزيارات" value={data.sessions} note="جلسة جديدة بعد 30 دقيقة من عدم النشاط." />
            <Metric label="الزوار الفريدون" value={data.unique_visitors} note="معرّف عشوائي first-party بدون fingerprinting أو IP كهوية." />
          </div>

          <div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:16px;align-items:start;min-width:0`}>
            <Ranking
              title="أماكن الزوار"
              note="أعلى 10 أماكن حسب الجلسات، ثم «أخرى»."
              rows={data.top_locations || []}
              empty="لا توجد زيارات ضمن هذه الفترة بعد."
              valueKey="sessions"
              valueLabel="جلسة"
            />
            <Ranking
              title="المنتجات الأكثر مشاهدة"
              note="إعادة التحميل السريعة خلال 30 ثانية لا تضخّم المشاهدات، والجلسة الجديدة تُحسب بشكل مستقل."
              rows={data.top_products || []}
              empty="لا توجد مشاهدات منتجات ضمن هذه الفترة بعد."
              valueKey="views"
              valueLabel="مشاهدة"
              renderName={(row) => row.product_exists ? (
                <Link to={`/admin/products/${row.product_id}`} style={sx`color:var(--admin-primary);font-weight:700;text-decoration:none;overflow-wrap:anywhere`}>{row.name}</Link>
              ) : <span>{row.name}</span>}
            />
          </div>
        </>
      )}
    </div>
  );
}
