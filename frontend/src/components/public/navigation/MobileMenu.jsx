import { localePath, useLocale } from "../../../i18n/locale.jsx";
import { Link as LanguageLink, useLocation } from "react-router-dom";
import { Link } from "../../../i18n/routing.jsx";
import { useStore } from "../../../app/StoreProvider.jsx";
import { whatsappHref } from "../../../utils/format.js";
import { Drawer } from "../overlays/Overlay.jsx";
import { GlobeIcon, WhatsAppIcon } from "../shell/icons.jsx";
import { navLinks } from "../../../store.js";

export default function MobileMenu({ open, onClose }) {
  const { locale, t } = useLocale();
  const location = useLocation();
  const { settings } = useStore();
  const wa = whatsappHref(settings.whatsapp, t("مرحباً، لدي استفسار عن {0}", [settings.storeName]));

  return (
    <Drawer
      open={open}
      onClose={onClose}
      side="right"
      label={t("قائمة التنقّل")}
      head={<strong className="vs-drawer__title">{settings.storeName}</strong>}
      footer={
        wa !== "#" && (
            <a
              href={wa}
              target="_blank"
              rel="noopener"
              className="vs-btn vs-btn--block vs-menu__wa"
            >
              <WhatsAppIcon size={18} />{" "}{t("تواصل عبر واتساب")}{" "}</a>
        )
      }
    >
      <div className="vs-menu">
        <p className="vs-menu__label">{t("روابط")}</p>
        {navLinks.map((link) => (
          <Link key={link.href} to={link.href} className="vs-menu__link" onClick={onClose}>
            {t(link.label)}
          </Link>
        ))}
        <nav className="vs-menu__languages" aria-label={t("اللغة")}>
          <p className="vs-menu__label"><GlobeIcon size={17} />{t("اللغة")}</p>
          {[{ locale: "ar", label: "العربية" }, { locale: "en", label: "English" }].map((language) => (
            <LanguageLink key={language.locale} className="vs-menu__link vs-menu__language"
              lang={language.locale} hrefLang={language.locale}
              aria-current={locale === language.locale ? "true" : undefined}
              to={{ pathname: localePath(location.pathname, language.locale), search: location.search, hash: location.hash }}
              onClick={onClose}>
              <span>{language.label}</span>
              {locale === language.locale && <span aria-hidden="true">✓</span>}
            </LanguageLink>
          ))}
        </nav>
      </div>
    </Drawer>
  );
}
