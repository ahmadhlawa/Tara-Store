import { useEffect, useState } from "react";
import { useStore } from "../app/StoreProvider.jsx";
import { storefrontService } from "../services/storefront.js";
import { whatsappHref } from "../utils/format.js";

function safeMapUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

export default function ContactRoutePage() {
  const { settings } = useStore();
  const [lead, setLead] = useState("");

  useEffect(() => {
    let cancelled = false;
    storefrontService.page("contact").then((page) => !cancelled && setLead(page.lead || page.body[0] || "")).catch(() => !cancelled && setLead(""));
    return () => { cancelled = true; };
  }, []);

  const rows = [
    { label: "الهاتف", value: settings.phone, href: `tel:${settings.phone}` },
    { label: "واتساب", value: settings.whatsapp, href: whatsappHref(settings.whatsapp, "") },
  ].filter((row) => row.value);
  const socials = [
    { label: "إنستغرام", href: settings.instagram, visible: settings.instagramVisible },
    { label: "فيسبوك", href: settings.facebook, visible: settings.facebookVisible },
    { label: "تيك توك", href: settings.tiktok, visible: settings.tiktokVisible },
    { label: "يوتيوب", href: settings.youtube, visible: settings.youtubeVisible },
  ].filter((item) => item.visible && item.href);
  const mapUrl = safeMapUrl(settings.locationUrl);

  return (
    <section className="vs-container vs-container--narrow vs-section">
      <h1 className="vs-page__title">تواصل معنا</h1>
      <p className="vs-page__lead">{lead || `يسعدنا استقبال استفساراتك حول منتجات ${settings.storeName}.`}</p>
      <div className="vs-contact">
        <aside className="vs-contact__side">
          <h2 className="vs-contact__title">معلومات التواصل</h2>
          {rows.length ? (
            <dl className="vs-specs">
              {rows.map((row) => (
                <div className="vs-specs__row" key={row.label}>
                  <dt>{row.label}</dt>
                  <dd>{row.href ? <a href={row.href} target={row.href.startsWith("http") ? "_blank" : undefined} rel="noopener noreferrer">{row.value}</a> : row.value}</dd>
                </div>
              ))}
            </dl>
          ) : <p className="vs-prose vs-prose--muted">لم تُضَف بيانات التواصل بعد.</p>}
          {settings.whatsapp && <a className="vs-btn vs-btn--primary vs-btn--lg vs-contact__whatsapp" href={whatsappHref(settings.whatsapp, "")} target="_blank" rel="noopener noreferrer">تواصل عبر واتساب</a>}
          {socials.length > 0 && <div className="vs-contact__socials">{socials.map((item) => <a key={item.label} href={item.href} className="vs-chip" target="_blank" rel="noopener noreferrer">{item.label}</a>)}</div>}
        </aside>
      </div>
      {mapUrl && (
        <section className="vs-contact__map" aria-labelledby="contact-map-title">
          <h2 id="contact-map-title" className="vs-contact__title">الموقع على الخريطة</h2>
          <iframe title="خريطة الموقع المهيأ" src={mapUrl} loading="lazy" referrerPolicy="no-referrer" />
          <a className="vs-btn vs-btn--ghost" href={mapUrl} target="_blank" rel="noopener noreferrer">عرض الموقع على الخريطة</a>
        </section>
      )}
    </section>
  );
}
