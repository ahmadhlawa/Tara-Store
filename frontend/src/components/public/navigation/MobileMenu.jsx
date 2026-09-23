import { useState } from "react";
import { useActiveCategorySlug, useCategoryNav } from "../../../hooks/useStorefront.js";
import { localePath, useLocale } from "../../../i18n/locale.jsx";
import { Link as LanguageLink, useLocation } from "react-router-dom";
import { Link, NavLink } from "../../../i18n/routing.jsx";
import { useStore } from "../../../app/StoreProvider.jsx";
import { whatsappHref } from "../../../utils/format.js";
import { Drawer } from "../overlays/Overlay.jsx";
import { ChevronDown, GlobeIcon, WhatsAppIcon } from "../shell/icons.jsx";
import { navLinks } from "../../../store.js";

export default function MobileMenu({ open, onClose }) {
  const { locale, t } = useLocale();
  const location = useLocation();
  const { settings } = useStore();
  const categories = useCategoryNav(useActiveCategorySlug());
  const [expanded, setExpanded] = useState(() => new Set());
  const [categoriesOpen, setCategoriesOpen] = useState(true);
  const mobileLinks = ["/offers", "/packages", "/shop", "/contact"].map((href) => navLinks.find((link) => link.href === href));
  const toggle = (slug) => setExpanded((current) => {
    const next = new Set(current);
    next.has(slug) ? next.delete(slug) : next.add(slug);
    return next;
  });
  const categoryList = (rows, depth = 0) => <ul style={{ listStyle: "none", margin: 0, padding: 0, paddingInlineStart: depth ? 18 : 0 }}>
    {rows.map((category) => <li key={category.slug}>
      <div style={{ display: "flex", alignItems: "center" }}>
        <Link to={category.href} className="vs-menu__link" style={{ flex: 1 }} aria-current={category.active ? "page" : undefined} onClick={onClose}>{category.name}</Link>
        {category.children.length > 0 && <button type="button" className="vs-iconbtn vs-iconbtn--bare" aria-label={t("الأقسام الفرعية لـ {0}", [category.name])} aria-expanded={expanded.has(category.slug)} onClick={() => toggle(category.slug)}>
          <ChevronDown size={16} style={{ transform: expanded.has(category.slug) ? "rotate(180deg)" : undefined }} />
        </button>}
      </div>
      {category.children.length > 0 && expanded.has(category.slug) && categoryList(category.children, depth + 1)}
    </li>)}
  </ul>;
  const wa = whatsappHref(settings.whatsapp, t("مرحباً، لدي استفسار عن {0}", [settings.storeName]));

  return (
    <Drawer
      open={open}
      onClose={onClose}
      side="right"
      id="vs-mobile-menu"
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
        <NavLink to="/" end className="vs-menu__link" onClick={onClose}>{t("الرئيسية")}</NavLink>
        <button type="button" className="vs-menu__link vs-menu__categories" aria-expanded={categoriesOpen} aria-controls="vs-menu-categories" onClick={() => setCategoriesOpen((value) => !value)}>
          {t("أقسام")}<ChevronDown size={16} style={{ transform: categoriesOpen ? "rotate(180deg)" : undefined }} />
        </button>
        <div id="vs-menu-categories" hidden={!categoriesOpen}>{categoryList(categories)}</div>
        {mobileLinks.map((link) => (
          <NavLink key={link.href} to={link.href} className="vs-menu__link" onClick={onClose}>
            {t(link.label)}
          </NavLink>
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
