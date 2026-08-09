import { useEffect, useState } from "react";
import { useStore } from "../app/StoreProvider.jsx";
import { storefrontService } from "../services/storefront.js";
import { whatsappHref } from "../utils/format.js";

export default function ContactRoutePage() {
  const { settings } = useStore();
  const [form, setForm] = useState({ name: "", phone: "", message: "" });
  const [error, setError] = useState("");
  const [lead, setLead] = useState("");

  useEffect(() => {
    let cancelled = false;
    storefrontService
      .page("contact")
      .then((page) => !cancelled && setLead(page.lead || page.body[0] || ""))
      .catch(() => !cancelled && setLead(""));
    return () => {
      cancelled = true;
    };
  }, []);

  // There is no contact endpoint in this MVP. Rather than pretending a message
  // was delivered, the form composes a WhatsApp message the customer sends.
  const submit = (event) => {
    event.preventDefault();
    if (!form.message.trim()) {
      setError("اكتب رسالتك أولاً");
      return;
    }
    if (!settings.whatsapp) {
      setError("رقم الواتساب غير مضبوط في إعدادات المتجر");
      return;
    }
    setError("");
    const text = `الاسم: ${form.name || "-"}\nالهاتف: ${form.phone || "-"}\n\n${form.message}`;
    window.open(whatsappHref(settings.whatsapp, text), "_blank", "noopener");
  };

  const rows = [
    { label: "الهاتف", value: settings.phone, href: `tel:${settings.phone}` },
    { label: "واتساب", value: settings.whatsapp, href: whatsappHref(settings.whatsapp, "") },
    { label: "البريد الإلكتروني", value: settings.email, href: `mailto:${settings.email}` },
    { label: "العنوان", value: settings.address, href: settings.locationUrl },
    { label: "ساعات العمل", value: settings.hours, href: null },
  ].filter((row) => row.value);

  const socials = [
    { label: "إنستغرام", href: settings.instagram },
    { label: "فيسبوك", href: settings.facebook },
    { label: "تيك توك", href: settings.tiktok },
    { label: "يوتيوب", href: settings.youtube },
  ].filter((item) => item.href);

  return (
    <section className="vs-container vs-container--narrow vs-section">
      <h1 className="vs-page__title">تواصل معنا</h1>
      <p className="vs-page__lead">{lead || `يسعدنا استقبال استفساراتك حول منتجات ${settings.storeName}.`}</p>

      <div className="vs-contact">
        <form className="vs-form vs-contact__form" onSubmit={submit}>
          <label className="vs-field">
            الاسم
            <input
              className="vs-input"
              type="text"
              value={form.name}
              onChange={(event) => setForm((c) => ({ ...c, name: event.target.value }))}
              placeholder="اسمك"
            />
          </label>
          <label className="vs-field">
            رقم الهاتف
            <input
              className="vs-input"
              type="tel"
              dir="ltr"
              value={form.phone}
              onChange={(event) => setForm((c) => ({ ...c, phone: event.target.value }))}
              placeholder="05XXXXXXXX"
            />
          </label>
          <label className="vs-field">
            رسالتك
            <textarea
              className="vs-input vs-textarea"
              rows="5"
              value={form.message}
              onChange={(event) => setForm((c) => ({ ...c, message: event.target.value }))}
              placeholder="كيف نساعدك؟"
              aria-describedby={error ? "vs-contact-error" : undefined}
            />
          </label>
          {error && (
            <p className="vs-field__error" id="vs-contact-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="vs-btn vs-btn--primary vs-btn--lg">
            إرسال عبر واتساب
          </button>
          <p className="vs-form__note">
            تفتح الرسالة في واتساب لترسلها بنفسك — لا يحتفظ المتجر بنسخة منها.
          </p>
        </form>

        <aside className="vs-contact__side">
          <h2 className="vs-contact__title">معلومات التواصل</h2>
          {rows.length ? (
            <dl className="vs-specs">
              {rows.map((row) => (
                <div className="vs-specs__row" key={row.label}>
                  <dt>{row.label}</dt>
                  <dd>
                    {row.href ? (
                      <a href={row.href} target={row.href.startsWith("http") ? "_blank" : undefined} rel="noopener">
                        {row.value}
                      </a>
                    ) : (
                      row.value
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="vs-prose vs-prose--muted">
              لم تُضَف بيانات التواصل بعد. تابعنا على حساباتنا للتواصل المباشر.
            </p>
          )}
          {socials.length > 0 && (
            <div className="vs-contact__socials">
              {socials.map((item) => (
                <a
                  key={item.label}
                  href={item.href}
                  className="vs-chip"
                  target="_blank"
                  rel="noopener"
                >
                  {item.label}
                </a>
              ))}
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}
