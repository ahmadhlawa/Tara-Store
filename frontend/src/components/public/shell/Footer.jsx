import { Link } from "react-router-dom";
import { useStore } from "../../../app/StoreProvider.jsx";
import { useCategoryNav } from "../../../hooks/useStorefront.js";
import { useLogoFit } from "../../../hooks/useLogoFit.js";
import { footerLinks } from "../../../store.js";
import { whatsappHref } from "../../../utils/format.js";

/**
 * Everything here is real data or nothing. A field the owner has not filled in
 * is omitted rather than shown as a placeholder — the storefront never invents
 * a phone number, an address or a legal claim.
 */
export default function Footer() {
  const { settings } = useStore();
  const categories = useCategoryNav();
  const year = new Date().getFullYear();
  // The same viewport as the header's, so the mark is the size of the mark here
  // too — and the file's white box is cropped back to it instead of sitting on
  // the dark footer as a pale slab.
  const { boxRef: logoBox, style: logoStyle } = useLogoFit(settings.logoUrl);

  const socials = [
    { key: "ig", label: "إنستغرام", short: "IG", href: settings.instagram },
    { key: "fb", label: "فيسبوك", short: "FB", href: settings.facebook },
    { key: "tt", label: "تيك توك", short: "TT", href: settings.tiktok },
    { key: "yt", label: "يوتيوب", short: "YT", href: settings.youtube },
    {
      key: "wa",
      label: "واتساب",
      short: "WA",
      href: whatsappHref(settings.whatsapp, `مرحباً ${settings.storeName}`),
    },
  ].filter((item) => item.href && item.href !== "#");

  const contact = [
    settings.phone && { key: "phone", node: <a href={`tel:${settings.phone}`}>{settings.phone}</a> },
    settings.email && { key: "email", node: <a href={`mailto:${settings.email}`}>{settings.email}</a> },
    settings.address && {
      key: "address",
      node: settings.locationUrl ? (
        <a href={settings.locationUrl} target="_blank" rel="noopener">
          {settings.address}
        </a>
      ) : (
        <span>{settings.address}</span>
      ),
    },
    settings.hours && { key: "hours", node: <span>{settings.hours}</span> },
  ].filter(Boolean);

  return (
    <footer className="vs-footer">
      <div className="vs-container vs-footer__top">
        <div className="vs-footer__brand">
          {settings.logoUrl ? (
            <span className="vs-logo__box vs-footer__logo" ref={logoBox}>
              <img className="vs-logo__img" src={settings.logoUrl} alt={settings.storeName} style={logoStyle} />
            </span>
          ) : (
            <span className="vs-footer__name">{settings.storeName}</span>
          )}
          {(settings.seoDescription || settings.tagline) && (
            <p className="vs-footer__desc">{settings.seoDescription || settings.tagline}</p>
          )}
          {socials.length > 0 && (
            <div className="vs-footer__social">
              {socials.map((item) => (
                <a
                  key={item.key}
                  href={item.href}
                  target="_blank"
                  rel="noopener"
                  aria-label={item.label}
                  title={item.label}
                >
                  {item.short}
                </a>
              ))}
            </div>
          )}
        </div>

        {categories.length > 0 && (
          <nav className="vs-footer__col" aria-label="الأقسام">
            <h2 className="vs-footer__title">الأقسام</h2>
            {categories.slice(0, 6).map((category) => (
              <Link key={category.slug} to={category.href}>
                {category.name}
              </Link>
            ))}
          </nav>
        )}

        {Object.entries(footerLinks).map(([key, column]) => (
          <nav key={key} className="vs-footer__col" aria-label={column.title}>
            <h2 className="vs-footer__title">{column.title}</h2>
            {column.items.map(([label, href]) => (
              <Link key={href} to={href}>
                {label}
              </Link>
            ))}
          </nav>
        ))}

        <div className="vs-footer__col">
          <h2 className="vs-footer__title">الدفع والتوصيل</h2>
          {contact.map((item) => (
            <span key={item.key}>{item.node}</span>
          ))}
          <div className="vs-footer__pay">
            <span>الدفع عند الاستلام</span>
            <span>تحويل بنكي / يدوي</span>
          </div>
          <span className="vs-footer__note">لا يتم إدخال بيانات بطاقات بنكية في هذا المتجر.</span>
        </div>
      </div>

      <div className="vs-footer__bottom">
        <div className="vs-container vs-footer__bottom-row">
          <span>
            © {year} {settings.storeName} — جميع الحقوق محفوظة
          </span>
          <Link to="/page/terms">الشروط والأحكام</Link>
        </div>
      </div>

      <div className="vs-footer__credit">
        <div className="vs-container vs-footer__credit-row">
          <img src="/branding/tfn.png" alt="TFN Technologies Team" />
          <span>Developed by TFN Technologies Team</span>
        </div>
      </div>
    </footer>
  );
}
