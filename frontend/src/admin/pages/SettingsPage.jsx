import { useEffect, useState } from "react";
import sx from "../../sx.js";
import { adminApi } from "../../api/adminApi.js";
import { MediaField } from "../MediaPicker.jsx";
import { Button, Field, PageHeader, Spinner, card, input, textarea, useFeedback } from "../ui.jsx";

const GROUPS = [
  {
    title: "هوية المتجر",
    fields: [
      ["store_name", "اسم المتجر"],
      ["store_name_ar", "الاسم بالعربية (يُعرض في المتجر والفاتورة)"],
      ["store_tagline", "الوصف المختصر"],
      ["logo_url", "شعار المتجر", "media"],
      ["favicon_url", "أيقونة المتصفح", "media"],
      ["announcement", "شريط الإعلان أعلى الموقع"],
    ],
  },
  {
    title: "بيانات التواصل",
    fields: [
      ["phone", "الهاتف"],
      ["whatsapp", "واتساب"],
      ["email", "البريد الإلكتروني"],
      ["address", "العنوان"],
      ["location_url", "رابط الموقع على الخريطة"],
      ["working_hours", "ساعات العمل"],
      ["order_notifications_email", "بريد إشعارات الطلبات (داخلي)"],
    ],
  },
  {
    title: "روابط التواصل الاجتماعي",
    fields: [
      ["instagram_url", "إنستغرام"],
      ["facebook_url", "فيسبوك"],
      ["tiktok_url", "تيك توك"],
      ["youtube_url", "يوتيوب"],
    ],
  },
  {
    title: "العملة",
    fields: [
      ["currency_code", "رمز العملة (ILS)"],
      ["currency_symbol", "رمز العرض (₪)"],
    ],
  },
  {
    title: "الألوان",
    colors: true,
    fields: [
      ["primary_color", "اللون الأساسي"],
      ["secondary_color", "اللون الثانوي"],
      ["accent_color", "لون التمييز"],
    ],
  },
  {
    title: "تحسين محركات البحث",
    fields: [["seo_title", "عنوان SEO"]],
    textareas: [["seo_description", "وصف SEO"]],
  },
  {
    title: "الدفع اليدوي",
    note: "تظهر هذه التعليمات للعميل الذي يختار «تحويل بنكي / يدوي». اتركها فارغة حتى تصل تفاصيل الحساب من صاحب المتجر — لا يعرض المتجر أي تعليمات ما دامت فارغة. لا يوجد دفع إلكتروني بالبطاقة في هذه النسخة.",
    textareas: [["manual_payment_instructions", "تعليمات التحويل"]],
  },
  {
    title: "الفوترة",
    note: "تصدر الفاتورة تلقائياً عند تأكيد الطلب. غيّر البادئة قبل إصدار أول فاتورة: الفواتير الصادرة تحتفظ ببادئتها، وتغييرها لاحقاً ينتج سلسلتين مختلفتين.",
    fields: [["invoice_prefix", "بادئة رقم الفاتورة (مثل INV)"]],
    textareas: [["invoice_notes", "ملاحظات أسفل الفاتورة"]],
  },
  {
    title: "البيانات القانونية والضريبة",
    note: "لا تملأ هذه الحقول إلا بتأكيد خطي من صاحب المتجر — تُطبع على فواتير العملاء. الضريبة معطّلة افتراضياً، وعند تعطيلها يساوي إجمالي الفاتورة إجمالي الطلب تماماً.",
    fields: [
      ["legal_business_name", "الاسم القانوني للنشاط"],
      ["registration_number", "رقم التسجيل التجاري"],
      ["tax_number", "الرقم الضريبي"],
    ],
    numbers: [["tax_rate", "نسبة الضريبة ٪"]],
    checkboxes: [
      ["tax_enabled", "تفعيل الضريبة على الفواتير"],
      ["prices_include_tax", "الأسعار المعروضة شاملة الضريبة"],
    ],
  },
];

const TEXT_KEYS = GROUPS.flatMap((group) => [
  ...(group.fields || []).map(([key]) => key),
  ...(group.textareas || []).map(([key]) => key),
]);
const NUMBER_KEYS = GROUPS.flatMap((group) => (group.numbers || []).map(([key]) => key));
const BOOLEAN_KEYS = [
  "maintenance_mode",
  ...GROUPS.flatMap((group) => (group.checkboxes || []).map(([key]) => key)),
];

export default function SettingsPage() {
  const feedback = useFeedback();
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    adminApi
      .getSettings()
      .then((row) => {
        const values = {};
        TEXT_KEYS.forEach((key) => {
          values[key] = row[key] ?? "";
        });
        NUMBER_KEYS.forEach((key) => {
          values[key] = row[key] ?? 0;
        });
        BOOLEAN_KEYS.forEach((key) => {
          values[key] = !!row[key];
        });
        setForm(values);
      })
      .catch((error) => feedback.error(error.message || "تعذّر تحميل الإعدادات."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const payload = {};
      TEXT_KEYS.forEach((key) => {
        const value = typeof form[key] === "string" ? form[key].trim() : form[key];
        payload[key] = value === "" ? null : value;
      });
      NUMBER_KEYS.forEach((key) => {
        payload[key] = Number(form[key]) || 0;
      });
      BOOLEAN_KEYS.forEach((key) => {
        payload[key] = !!form[key];
      });
      // Required strings on the server; never send null. invoice_prefix joins them —
      // clearing it would leave new invoices with no series at all.
      ["store_name", "currency_code", "currency_symbol", "invoice_prefix"].forEach((key) => {
        if (!payload[key]) delete payload[key];
      });
      await adminApi.updateSettings(payload);
      feedback.success("تم حفظ الإعدادات. أعد تحميل المتجر لرؤية التغييرات.");
    } catch (error) {
      feedback.error(error.message || "تعذّر حفظ الإعدادات.");
    } finally {
      setSaving(false);
    }
  };

  if (!form) return <Spinner />;

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  return (
    <>
      <PageHeader
        title="إعدادات المتجر"
        description="هوية المتجر وبيانات التواصل والألوان والعملة — تنعكس مباشرة على الواجهة."
        actions={<Button onClick={save} disabled={saving}>{saving ? "جارٍ الحفظ…" : "حفظ"}</Button>}
      />
      {feedback.node}

      {GROUPS.map((group) => (
        <div key={group.title} style={{ ...card, ...sx`margin-bottom:16px` }}>
          <h2 style={sx`margin:0 0 ${group.note ? "8px" : "14px"};font-size:16px;font-weight:800`}>{group.title}</h2>
          {group.note && (
            <p style={sx`margin:0 0 14px;font-size:12.5px;color:#766669;line-height:1.9`}>{group.note}</p>
          )}
          <div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px`}>
            {(group.fields || []).map(([key, title, kind]) =>
              kind === "media" ? (
                <MediaField key={key} title={title} value={form[key] ?? ""} onChange={(value) => update(key, value)} />
              ) : (
                <Field key={key} title={title}>
                  <input
                    type={group.colors ? "color" : "text"}
                    value={form[key] ?? ""}
                    onChange={(event) => update(key, event.target.value)}
                    style={input}
                  />
                </Field>
              ),
            )}
            {(group.numbers || []).map(([key, title]) => (
              <Field key={key} title={title}>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.001"
                  value={form[key] ?? 0}
                  onChange={(event) => update(key, event.target.value)}
                  style={input}
                />
              </Field>
            ))}
          </div>
          {(group.textareas || []).map(([key, title]) => (
            <Field key={key} title={title}>
              <textarea rows="3" value={form[key] ?? ""} onChange={(event) => update(key, event.target.value)} style={textarea} />
            </Field>
          ))}
          {(group.checkboxes || []).map(([key, title]) => (
            <label key={key} style={sx`display:flex;align-items:center;gap:10px;margin-top:12px;font-size:14px;font-weight:700;cursor:pointer`}>
              <input
                type="checkbox"
                checked={!!form[key]}
                onChange={(event) => update(key, event.target.checked)}
                style={sx`width:18px;height:18px;accent-color:#7F568F`}
              />
              {title}
            </label>
          ))}
        </div>
      ))}

      <div style={{ ...card, ...sx`margin-bottom:30px` }}>
        <label style={sx`display:flex;align-items:center;gap:10px;font-size:14px;font-weight:700;cursor:pointer`}>
          <input
            type="checkbox"
            checked={!!form.maintenance_mode}
            onChange={(event) => update("maintenance_mode", event.target.checked)}
            style={sx`width:18px;height:18px;accent-color:#7F568F`}
          />
          وضع الصيانة
        </label>
        <p style={sx`margin:8px 0 0;font-size:12.5px;color:#8A7F95`}>يُعلن هذا الحقل عبر واجهة المتجر ليستخدمه المطوّر لاحقاً؛ لا يوقف المتجر تلقائياً في هذه النسخة.</p>
      </div>

      <div style={sx`margin-bottom:30px`}>
        <Button onClick={save} disabled={saving}>{saving ? "جارٍ الحفظ…" : "حفظ الإعدادات"}</Button>
      </div>
    </>
  );
}
