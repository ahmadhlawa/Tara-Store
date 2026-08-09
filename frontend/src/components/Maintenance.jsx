import sx from "../sx.js";
import { whatsappHref } from "../utils/format.js";

/**
 * Shown in place of the whole storefront while the owner has maintenance mode on.
 *
 * It renders from `StoreSettings` only — the same public projection every visitor can
 * already read, so nothing private is exposed. Nothing here redirects, so a reload
 * simply shows this screen again, and /admin is a separate route branch that never
 * reaches this component.
 */
export default function MaintenanceScreen({ settings }) {
  const contacts = [
    settings.whatsapp && {
      key: "whatsapp",
      label: "واتساب",
      value: settings.whatsapp,
      href: whatsappHref(settings.whatsapp, ""),
    },
    settings.phone && {
      key: "phone",
      label: "هاتف",
      value: settings.phone,
      href: `tel:${String(settings.phone).replace(/\s/g, "")}`,
    },
    settings.email && {
      key: "email",
      label: "البريد الإلكتروني",
      value: settings.email,
      href: `mailto:${settings.email}`,
    },
    settings.hours && { key: "hours", label: "ساعات العمل", value: settings.hours, href: null },
  ].filter(Boolean);

  return (
    <div
      dir="rtl"
      style={sx`direction:rtl;background:#FBF9F6;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:32px 18px`}
    >
      <main
        role="main"
        style={sx`width:100%;max-width:560px;background:#fff;border:1px solid #EAE3D8;border-radius:20px;padding:38px 26px;text-align:center;box-shadow:0 18px 44px rgba(26,24,21,.07)`}
      >
        {settings.logoUrl ? (
          <img
            src={settings.logoUrl}
            alt={settings.storeName}
            style={sx`max-width:180px;max-height:74px;margin:0 auto 18px;display:block;object-fit:contain`}
          />
        ) : (
          <span
            style={sx`display:block;font-family:'Marcellus',serif;font-size:27px;letter-spacing:.14em;color:var(--brand-primary,#1F4E4A);margin-bottom:18px;word-break:break-word`}
          >
            {settings.storeName}
          </span>
        )}

        <div
          aria-hidden="true"
          style={sx`width:62px;height:62px;margin:0 auto 20px;border-radius:50%;background:#F3EEE4;display:flex;align-items:center;justify-content:center;font-size:27px`}
        >
          🛠️
        </div>

        <h1 style={sx`margin:0 0 12px;font-size:23px;line-height:1.5;color:#1A1815`}>
          المتجر في وضع الصيانة
        </h1>
        <p style={sx`margin:0 auto;max-width:420px;font-size:14.5px;line-height:2;color:#5C564D`}>
          نجري بعض التحديثات على المتجر الآن، وسنعود للعمل في أقرب وقت. شكراً لصبركم.
        </p>
        {settings.tagline && (
          <p style={sx`margin:14px 0 0;font-size:13.5px;color:#8D877E`}>{settings.tagline}</p>
        )}

        {contacts.length > 0 && (
          <section
            aria-label="معلومات التواصل"
            style={sx`margin-top:26px;padding-top:22px;border-top:1px solid #EFE9DF;display:flex;flex-direction:column;gap:11px`}
          >
            <strong style={sx`font-size:14px;color:#1A1815`}>للتواصل معنا</strong>
            {contacts.map((contact) => (
              <div
                key={contact.key}
                style={sx`display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:center;font-size:13.5px;color:#5C564D`}
              >
                <span style={sx`color:#8D877E`}>{contact.label}</span>
                {contact.href ? (
                  <a
                    href={contact.href}
                    style={sx`color:var(--brand-primary,#1F4E4A);text-decoration:none;word-break:break-word`}
                  >
                    {contact.value}
                  </a>
                ) : (
                  <span style={sx`word-break:break-word`}>{contact.value}</span>
                )}
              </div>
            ))}
          </section>
        )}
      </main>
    </div>
  );
}
