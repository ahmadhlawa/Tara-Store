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
  ].filter(Boolean);

  return (
    <div
      dir="rtl"
      style={sx`direction:rtl;background:#FFFFFF;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:32px 18px`}
    >
      <main
        role="main"
        style={sx`width:100%;max-width:560px;background:#fff;border:1px solid #E7DCF2;border-radius:20px;padding:38px 26px;text-align:center;box-shadow:0 18px 44px var(--brand-primary-16)`}
      >
        {/* Mark and name together, as in the header: Tara's logo is a square
            lockup, and a page whose whole job is to reassure a visitor that they
            are in the right place must still say which store this is. */}
        {settings.logoUrl && (
          <img
            src={settings.logoUrl}
            alt=""
            aria-hidden="true"
            style={sx`max-width:150px;max-height:150px;margin:0 auto 12px;display:block;object-fit:contain`}
          />
        )}
        <span
          style={sx`display:block;font-family:'Marcellus','Cairo',serif;font-size:27px;letter-spacing:.05em;color:var(--brand-primary);margin-bottom:18px;word-break:break-word`}
        >
          {settings.storeName}
        </span>

        <div
          aria-hidden="true"
          style={sx`width:62px;height:62px;margin:0 auto 20px;border-radius:50%;background:#F3EAFA;display:flex;align-items:center;justify-content:center;font-size:27px`}
        >
          🛠️
        </div>

        <h1 style={sx`margin:0 0 12px;font-size:23px;line-height:1.5;color:#3B3243`}>
          المتجر في وضع الصيانة
        </h1>
        <p style={sx`margin:0 auto;max-width:420px;font-size:14.5px;line-height:2;color:#4B4155`}>
          نجري بعض التحديثات على المتجر الآن، وسنعود للعمل في أقرب وقت. شكراً لصبركم.
        </p>
        {settings.tagline && (
          <p style={sx`margin:14px 0 0;font-size:13.5px;color:#8A7F95`}>{settings.tagline}</p>
        )}

        {contacts.length > 0 && (
          <section
            aria-label="معلومات التواصل"
            style={sx`margin-top:26px;padding-top:22px;border-top:1px solid #E7DCF2;display:flex;flex-direction:column;gap:11px`}
          >
            <strong style={sx`font-size:14px;color:#3B3243`}>للتواصل معنا</strong>
            {contacts.map((contact) => (
              <div
                key={contact.key}
                style={sx`display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:center;font-size:13.5px;color:#4B4155`}
              >
                <span style={sx`color:#8A7F95`}>{contact.label}</span>
                {contact.href ? (
                  <a
                    href={contact.href}
                    style={sx`color:var(--link-color);text-decoration:none;word-break:break-word`}
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
