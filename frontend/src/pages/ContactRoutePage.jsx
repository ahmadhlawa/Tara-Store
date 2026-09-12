import { useEffect, useState } from "react";
import { useStore } from "../app/StoreProvider.jsx";
import useSeo from "../hooks/useSeo.js";
import { storefrontService } from "../services/storefront.js";
import { whatsappHref } from "../utils/format.js";

function ContactIcon({ type }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{type === "instagram" ? <><rect x="3" y="3" width="18" height="18" rx="5" /><circle cx="12" cy="12" r="4" /><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" /></> : <><path d="M20.5 11.8a8.4 8.4 0 0 1-12.4 7.4L4 20.3l1.1-4A8.4 8.4 0 1 1 20.5 11.8Z" /><path d="M9 8.1c.2-.4.4-.4.7-.4h.4c.2 0 .4.1.5.4l.7 1.7c.1.3 0 .5-.2.7l-.6.7c.8 1.6 1.8 2.5 3.4 3.3l.7-.8c.2-.2.4-.3.7-.2l1.7.8c.3.1.4.3.4.6 0 .4-.2 1.4-.9 1.9-.6.5-1.5.7-2.4.4-1.3-.4-2.9-1.1-4.5-2.7-1.3-1.3-2.2-2.8-2.5-4.1-.3-1 .1-1.8.5-2.3.4-.4.9-.5 1.4-.5Z" /></>}</svg>;
}

function instagramValue(url) {
  try { return `@${new URL(url).pathname.split("/").filter(Boolean)[0]}`; }
  catch { return url; }
}

export default function ContactRoutePage() {
  const { settings } = useStore();
  const [lead, setLead] = useState("");
  useSeo({ title: `تواصل معنا | ${settings.storeName}`, description: settings.seoDescription || settings.tagline, baseUrl: settings.publicBaseUrl, path: "/contact" });
  useEffect(() => {
    let cancelled = false;
    storefrontService.page("contact").then((page) => !cancelled && setLead(page.lead || page.body[0] || "")).catch(() => !cancelled && setLead(""));
    return () => { cancelled = true; };
  }, []);
  const methods = [
    settings.whatsapp && { type: "whatsapp", label: "واتساب", value: settings.whatsapp, href: whatsappHref(settings.whatsapp, "") },
    settings.instagramVisible && settings.instagram && { type: "instagram", label: "إنستغرام", value: instagramValue(settings.instagram), href: settings.instagram },
  ].filter(Boolean);

  return <section className="vs-container vs-section vs-contact-page">
    <header className="vs-contact-page__header"><span className="vs-contact-page__eyebrow">نحن بالقرب منك</span><h1 className="vs-page__title">تواصل معنا</h1><p className="vs-page__lead">{lead || "يسعدنا تواصلكم عبر قنواتنا التالية"}</p></header>
    <div className="vs-contact-page__layout">
      <section className="vs-contact-methods" aria-labelledby="contact-methods-title">
        <h2 id="contact-methods-title">كيف يمكننا مساعدتك؟</h2><p>اختاري القناة الأنسب لك، وسنكون سعداء بالرد على استفسارك.</p>
        <div className="vs-contact-methods__list">{methods.map((method) => <a key={method.type} className={`vs-contact-method vs-contact-method--${method.type}`} href={method.href} target="_blank" rel="noopener noreferrer" aria-label={`تواصل عبر ${method.label}`}><span className="vs-contact-method__icon"><ContactIcon type={method.type} /></span><span><strong>{method.label}</strong><small>{method.value}</small></span><span className="vs-contact-method__arrow" aria-hidden="true">←</span></a>)}{!methods.length && <p className="vs-prose vs-prose--muted">ستظهر روابط التواصل هنا فور إضافتها من إعدادات المتجر.</p>}</div>
      </section>
      <aside className="vs-contact-note" aria-label="رسالة ترحيبية"><img src="/branding/contact-note.png" width="1138" height="1402" alt="" loading="lazy" /></aside>
    </div>
  </section>;
}
