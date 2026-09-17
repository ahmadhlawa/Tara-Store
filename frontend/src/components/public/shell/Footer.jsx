import { useLocale } from "../../../i18n/locale.jsx";
import { Link } from "../../../i18n/routing.jsx";
import { useStore } from "../../../app/StoreProvider.jsx";
import { useLogoFit } from "../../../hooks/useLogoFit.js";
import { footerLinks } from "../../../store.js";
import { whatsappHref } from "../../../utils/format.js";

function SocialIcon({ name }) {

  const paths = {
    instagram: <><rect x="3" y="3" width="18" height="18" rx="5" /><circle cx="12" cy="12" r="4" /><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" /></>,
    facebook: <path d="M13.5 21v-8h2.75l.41-3h-3.16V8.08c0-.87.24-1.46 1.49-1.46H16.6V3.94c-.28-.04-1.24-.12-2.36-.12-2.33 0-3.92 1.42-3.92 4.03V10H7.7v3h2.62v8h3.18Z" fill="currentColor" stroke="none" />,
    tiktok: <path d="M14.5 3c.4 2.15 1.61 3.43 3.5 3.83v3.08a7.28 7.28 0 0 1-3.5-1.04v5.96a5.34 5.34 0 1 1-4.61-5.29v3.11a2.25 2.25 0 1 0 1.52 2.13V3h3.09Z" fill="currentColor" stroke="none" />,
    youtube: <path d="M21 7.2a2.8 2.8 0 0 0-1.96-1.98C17.3 4.75 12 4.75 12 4.75s-5.3 0-7.04.47A2.8 2.8 0 0 0 3 7.2C2.53 8.95 2.53 12 2.53 12S2.53 15.05 3 16.8a2.8 2.8 0 0 0 1.96 1.98c1.74.47 7.04.47 7.04.47s5.3 0 7.04-.47A2.8 2.8 0 0 0 21 16.8c.47-1.75.47-4.8.47-4.8S21.47 8.95 21 7.2ZM10.2 15.37V8.63L15.82 12l-5.62 3.37Z" fill="currentColor" stroke="none" />,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{paths[name]}</svg>;
}

function validExternalUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

/**
 * Everything here is real data or nothing. A field the owner has not filled in
 * is omitted rather than shown as a placeholder — the storefront never invents
 * a phone number, an address or a legal claim.
 */
export default function Footer() {
  const { t } = useLocale();
  const { settings } = useStore();
  const year = new Date().getFullYear();
  // The same viewport as the header's, so the mark is the size of the mark here
  // too — and the file's white box is cropped back to it instead of sitting on
  // the dark footer as a pale slab.
  const { boxRef: logoBox, style: logoStyle } = useLogoFit(settings.logoUrl);

  const socials = [
    { key: "instagram", label: t("إنستغرام"), href: settings.instagram, visible: settings.instagramVisible },
    { key: "facebook", label: t("فيسبوك"), href: settings.facebook, visible: settings.facebookVisible },
    { key: "tiktok", label: t("تيك توك"), href: settings.tiktok, visible: settings.tiktokVisible },
    { key: "youtube", label: t("يوتيوب"), href: settings.youtube, visible: settings.youtubeVisible },
  ].map((item) => ({ ...item, href: item.visible ? validExternalUrl(item.href) : null })).filter((item) => item.href);

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
  ].filter(Boolean);

  const informationLinks = footerLinks.policies.items.filter(([, href]) => href !== "/page/terms");

  return (
    <footer className="vs-footer">
      <div className="vs-footer__transition" aria-hidden="true" />

      <div className="vs-container vs-footer__top">
        <nav className="vs-footer__social-area" aria-label={t("روابط التواصل الاجتماعي")}>
          <h2 className="vs-footer__title">{t("تابعونا")}</h2>
          {socials.length > 0 && (
            <div className="vs-footer__social-row">
              {socials.map((item) => (
                <a key={item.key} href={item.href} target="_blank" rel="noopener noreferrer" aria-label={item.label} title={item.label}>
                  <SocialIcon name={item.key} />
                </a>
              ))}
            </div>
          )}
        </nav>

        <div className="vs-footer__brand">
          {settings.logoUrl ? (
            <span className="vs-logo__box vs-footer__logo" ref={logoBox}>
              <img className="vs-logo__img" src={settings.logoUrl} alt={settings.storeName} style={logoStyle} />
            </span>
          ) : (
            <span className="vs-footer__name">{settings.storeName}</span>
          )}
        </div>

        <div className="vs-footer__essentials">
          <nav className="vs-footer__col" aria-label={t("معلومات")}>
            <h2 className="vs-footer__title">{t("معلومات")}</h2>
            {informationLinks.map(([label, href]) => (
              <Link key={href} to={href}>
                {t(label)}
              </Link>
            ))}
          </nav>

          <div className="vs-footer__col">
            <h2 className="vs-footer__title">{t("الدفع والتوصيل")}</h2>
            {contact.map((item) => (
              <span key={item.key}>{item.node}</span>
            ))}
            <div className="vs-footer__pay">
              <span>{t("الدفع عند الاستلام")}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="vs-footer__bottom">
        <div className="vs-container vs-footer__bottom-row">
          <Link to="/page/terms">{t("الشروط والأحكام")}</Link>
          <div className="vs-footer__credit">
            <img src="/branding/tfn.png" alt="TFN Technologies Team" />
            <span>Developed by TFN Technologies Team</span>
          </div>
          <span className="vs-footer__copyright">
            © {year} {settings.storeName}{" "}{t("— جميع الحقوق محفوظة")}{" "}</span>
        </div>
      </div>
    </footer>
  );
}
