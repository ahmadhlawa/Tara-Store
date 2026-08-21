import { useEffect, useState } from "react";
import sx from "../../sx.js";
import { adminApi } from "../../api/adminApi.js";
import { Button, Field, PageHeader, Spinner, card, input, useFeedback } from "../ui.jsx";

const CONTACT_FIELDS = [
  ["phone", "الهاتف", "tel"],
  ["whatsapp", "واتساب", "tel"],
  ["email", "البريد الإلكتروني", "email"],
  ["address", "العنوان", "text"],
  ["location_url", "رابط الموقع على الخريطة", "url"],
  ["working_hours", "ساعات العمل", "text"],
  ["order_notifications_email", "بريد إشعارات الطلبات الداخلي", "email"],
];

const SOCIAL_FIELDS = [
  ["instagram", "إنستغرام"],
  ["facebook", "فيسبوك"],
  ["tiktok", "تيك توك"],
  ["youtube", "يوتيوب"],
];

const TEXT_KEYS = [...CONTACT_FIELDS.map(([key]) => key), ...SOCIAL_FIELDS.map(([key]) => `${key}_url`)];
const BOOLEAN_KEYS = SOCIAL_FIELDS.map(([key]) => `${key}_visible`);

export default function SettingsPage() {
  const feedback = useFeedback();
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    adminApi.getSettings().then((row) => {
      setForm({
        ...Object.fromEntries(TEXT_KEYS.map((key) => [key, row[key] ?? ""])),
        ...Object.fromEntries(BOOLEAN_KEYS.map((key) => [key, row[key] !== false])),
      });
    }).catch((error) => feedback.error(error.message || "تعذّر تحميل روابط المتجر."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const save = async () => {
    setSaving(true);
    try {
      const payload = Object.fromEntries(TEXT_KEYS.map((key) => [key, form[key].trim() || null]));
      BOOLEAN_KEYS.forEach((key) => { payload[key] = !!form[key]; });
      await adminApi.updateSettings(payload);
      feedback.success("تم حفظ روابط المتجر.");
    } catch (error) {
      feedback.error(error.message || "تعذّر حفظ روابط المتجر.");
    } finally {
      setSaving(false);
    }
  };

  if (!form) return <Spinner />;

  return (
    <>
      <PageHeader
        title="روابط المتجر"
        description="بيانات التواصل وروابط الظهور في الموقع."
        actions={<Button onClick={save} disabled={saving}>{saving ? "جارٍ الحفظ…" : "حفظ"}</Button>}
      />
      {feedback.node}
      <section style={{ ...card, ...sx`margin-bottom:16px` }}>
        <h2 style={sx`margin:0 0 14px;font-size:16px;font-weight:800`}>بيانات التواصل</h2>
        <div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px`}>
          {CONTACT_FIELDS.map(([key, title, type]) => (
            <Field key={key} title={title}>
              <input type={type} value={form[key]} onChange={(event) => update(key, event.target.value)} style={input} />
            </Field>
          ))}
        </div>
      </section>
      <section style={{ ...card, ...sx`margin-bottom:30px` }}>
        <h2 style={sx`margin:0 0 14px;font-size:16px;font-weight:800`}>روابط التواصل الاجتماعي</h2>
        <div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px`}>
          {SOCIAL_FIELDS.map(([key, title]) => (
            <div key={key} style={sx`display:flex;flex-direction:column;gap:10px`}>
              <Field title={title}>
                <input type="url" value={form[`${key}_url`]} onChange={(event) => update(`${key}_url`, event.target.value)} style={input} />
              </Field>
              <label style={sx`display:flex;align-items:center;gap:10px;font-size:14px;font-weight:700;cursor:pointer`}>
                <input type="checkbox" checked={form[`${key}_visible`]} onChange={(event) => update(`${key}_visible`, event.target.checked)} style={sx`width:18px;height:18px;accent-color:var(--admin-primary)`} />
                إظهار في الموقع
              </label>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
