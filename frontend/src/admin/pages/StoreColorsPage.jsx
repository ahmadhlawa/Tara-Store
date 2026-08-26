import { useEffect, useMemo, useState } from "react";
import sx from "../../sx.js";
import { adminApi } from "../../api/adminApi.js";
import { buildStorefrontThemeVariables, contrastRatio, staticThemeDefaults, THEME_KEYS } from "../../theme/storefrontTheme.js";
import { Button, ConfirmDialog, Field, Notice, PageHeader, Spinner, card, input, useFeedback } from "../ui.jsx";

const HEX = /^#[0-9A-F]{6}$/i;
const GROUPS = [
  ["ألوان الهوية", [["theme_primary_color", "اللون الرئيسي"], ["theme_secondary_color", "اللون الثانوي"], ["theme_soft_color", "الخلفية الخفيفة"]]],
  ["أجزاء الموقع", [["theme_nav_strip_background", "خلفية شريط التنقل"], ["theme_nav_strip_text", "نص شريط التنقل"], ["theme_footer_background", "خلفية الفوتر"], ["theme_footer_text", "نص الفوتر"], ["theme_footer_muted_text", "النص الثانوي في الفوتر"]]],
];

function ColorField({ name, label, value, onChange }) {
  const color = HEX.test(value) ? value : "#000000";
  return <Field title={label}><div style={sx`display:flex;gap:8px`}><input aria-label={`${label} picker`} type="color" value={color} onChange={(e) => onChange(name, e.target.value.toUpperCase())} style={sx`width:46px;height:44px;padding:3px;border:1px solid #DFD2EC;border-radius:10px;background:#FAF7FD`} /><input aria-label={label} value={value} onChange={(e) => onChange(name, e.target.value.toUpperCase())} maxLength="7" style={input} dir="ltr" /></div></Field>;
}

export default function StoreColorsPage() {
  const feedback = useFeedback();
  const [defaults, setDefaults] = useState(null);
  const [form, setForm] = useState(null);
  const [customButton, setCustomButton] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);

  useEffect(() => { adminApi.getSettings().then((row) => { const base = staticThemeDefaults(); setDefaults(base); setForm(Object.fromEntries(THEME_KEYS.map((key) => [key, row[key] ?? null]))); setCustomButton(!!(row.theme_button_primary_background || row.theme_button_primary_text)); }).catch((e) => feedback.error(e.message || "تعذر تحميل ألوان المتجر.")); }, []);
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const effective = form && { ...Object.fromEntries(THEME_KEYS.map((key) => [key, form[key] || defaults[key]])), theme_button_primary_background: customButton ? (form.theme_button_primary_background || defaults.theme_button_primary_background) : (form.theme_primary_color || defaults.theme_primary_color), theme_button_primary_text: customButton ? (form.theme_button_primary_text || defaults.theme_button_primary_text) : defaults.theme_button_primary_text };
  const contrastWarnings = useMemo(() => {
    if (!effective) return [];
    const pairs = [["شريط التنقل", effective.theme_nav_strip_background, effective.theme_nav_strip_text], ["الفوتر", effective.theme_footer_background, effective.theme_footer_text], ["النص الثانوي في الفوتر", effective.theme_footer_background, effective.theme_footer_muted_text], ["الزر الرئيسي", effective.theme_button_primary_background, effective.theme_button_primary_text]];
    return pairs.filter(([, background, text]) => HEX.test(background) && HEX.test(text)).map(([label, background, text]) => ({ label, background, ratio: contrastRatio(background, text) })).filter(({ ratio }) => ratio < 4.5).map((warning) => {
      const black = contrastRatio(warning.background, "#181818");
      const white = contrastRatio(warning.background, "#FFFFFF");
      const suggestion = black >= white ? ["#181818", black] : ["#FFFFFF", white];
      return { ...warning, suggestion: suggestion[1] >= warning.ratio + 1 ? suggestion[0] : null };
    });
  }, [effective]);
  const hasInvalidHex = !!form && THEME_KEYS.some((key) => form[key] && !HEX.test(form[key]));
  const save = async () => {
    if (hasInvalidHex) return;
    setSaving(true);
    try { const payload = Object.fromEntries(THEME_KEYS.map((key) => [key, customButton || !key.startsWith("theme_button_") ? form[key] : null])); await adminApi.updateSettings(payload); feedback.success("تم حفظ ألوان المتجر."); }
    catch (e) { feedback.error(e.message || "تعذر حفظ ألوان المتجر."); } finally { setSaving(false); }
  };
  const reset = async () => { setSaving(true); try { await adminApi.updateSettings(Object.fromEntries(THEME_KEYS.map((key) => [key, null]))); setForm(Object.fromEntries(THEME_KEYS.map((key) => [key, null]))); setCustomButton(false); setConfirmReset(false); feedback.success("تمت استعادة الألوان الافتراضية."); } catch (e) { feedback.error(e.message || "تعذرت استعادة الألوان."); } finally { setSaving(false); } };
  if (!form) return <Spinner />;
  const preview = buildStorefrontThemeVariables(effective);
  return <>
    <PageHeader title="ألوان المتجر" description="تخصيص ألوان واجهة المتجر العامة فقط." actions={<><Button variant="ghost" onClick={() => setConfirmReset(true)} disabled={saving}>استعادة الألوان الافتراضية</Button><Button onClick={save} disabled={saving || hasInvalidHex}>{saving ? "جارٍ الحفظ…" : "حفظ التغييرات"}</Button></>} />
    {feedback.node}{contrastWarnings.map(({ label, ratio, suggestion }) => <Notice key={label} kind="info">تنبيه: نسبة التباين في {label} هي {ratio.toFixed(2)}:1. المستوى الموصى به للنص العادي هو 4.5:1.{suggestion && ` قد يوفر ${suggestion} تبايناً أفضل.`}</Notice>)}
    <div className="admin-store-colors-layout" style={sx`display:grid;grid-template-columns:var(--admin-store-colors-grid,minmax(0,1fr) minmax(280px,380px));gap:18px;align-items:start`}>
      <div>{GROUPS.map(([title, fields]) => <section key={title} style={{ ...card, marginBottom: 16 }}><h2 style={sx`margin:0 0 14px;font-size:16px`}>{title}</h2><div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px`}>{fields.map(([key, label]) => <ColorField key={key} name={key} label={label} value={effective[key]} onChange={update} />)}</div></section>)}
        <section style={card}><h2 style={sx`margin:0 0 14px;font-size:16px`}>الأزرار الرئيسية</h2><label style={sx`display:flex;gap:9px;align-items:center;font-size:14px;font-weight:700;margin-bottom:14px`}><input type="checkbox" checked={customButton} onChange={(e) => setCustomButton(e.target.checked)} />استخدام لون مخصص للأزرار الرئيسية</label>{customButton && <div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px`}><ColorField name="theme_button_primary_background" label="لون الزر" value={effective.theme_button_primary_background} onChange={update} /><ColorField name="theme_button_primary_text" label="لون نص الزر" value={effective.theme_button_primary_text} onChange={update} /></div>}</section>
      </div>
      <section style={{ ...card, position: "sticky", top: 90 }}><h2 style={sx`margin:0 0 12px;font-size:16px`}>معاينة مباشرة</h2><div className="store-theme-preview" style={{ ...preview, border: "1px solid #ddd", borderRadius: 10, overflow: "hidden", background: "#fff", color: "#181818" }}><div style={sx`padding:12px;background:#fff;font-weight:800`}>متجر تارا</div><div style={{ padding: 10, background: "var(--nav-strip-background)", color: "var(--nav-strip-text)" }}>الرئيسية · المنتجات · تواصل</div><div style={{ padding: 16, background: "var(--brand-soft)" }}><strong style={{ color: "var(--brand-primary)" }}>عنوان تجريبي</strong><p style={sx`font-size:13px`}>نص ومحتوى للمتجر</p><button type="button" style={{ border: 0, borderRadius: 7, padding: "9px 14px", background: "var(--button-primary-background)", color: "var(--button-primary-text)" }}>تسوق الآن</button></div><div style={{ padding: 12, background: "var(--footer-background)", color: "var(--footer-text)" }}>الفوتر <small style={{ color: "var(--footer-muted-text)" }}>نص ثانوي</small></div></div></section>
    </div>
    {confirmReset && <ConfirmDialog title="استعادة الألوان الافتراضية" message="سيتم حذف جميع تخصيصات الألوان والعودة إلى ملف الثيم الافتراضي." confirmLabel="استعادة الافتراضي" onCancel={() => setConfirmReset(false)} onConfirm={reset} />}
  </>;
}
