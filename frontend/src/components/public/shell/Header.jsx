import { useLocale } from "../../../i18n/locale.jsx";
import { Link as LanguageLink, useLocation } from "react-router-dom";
import { localePath } from "../../../i18n/locale.jsx";
import { Link, NavLink } from "../../../i18n/routing.jsx";
import { OVERLAY, useStore } from "../../../app/StoreProvider.jsx";
import { useCartCountPulse } from "../../../hooks/useCartCountPulse.js";
import { useLogoFit } from "../../../hooks/useLogoFit.js";
import { useMoney } from "../../../hooks/useStorefront.js";
import { navLinks } from "../../../store.js";
import SearchBox from "../search/SearchBox.jsx";
import { CartIcon, GlobeIcon, GridIcon, MenuIcon, SearchIcon, UserIcon } from "./icons.jsx";

function StoreMark({ settings }) {
  const { t } = useLocale();
  // The file is left exactly as the owner supplied it; only how much of the box
  // its artwork is allowed to fill is decided here. See useLogoFit.
  const { boxRef, style } = useLogoFit(settings.logoUrl);
  return (
    <Link to="/" className="vs-logo" aria-label={t("{0} — الصفحة الرئيسية", [settings.storeName])}>
      {settings.logoUrl && (
        <span className="vs-logo__box" ref={boxRef}>
          <img
            className="vs-logo__img"
            src={settings.logoUrl}
            // Decorative here now that the name is written beside it: without
            // this the mark and the wordmark announce the store twice.
            alt=""
            aria-hidden="true"
            style={style}
          />
        </span>
      )}
      {/* The name is set beside the mark rather than replaced by it. Tara's
          supplied logo is a square lockup, and at the ~46px a navigation bar can
          give it the wordmark inside the file is about eight pixels tall — so
          the header would carry a brand mark and no legible store name at all.
          A store that later supplies a wide wordmark logo can drop the text; the
          markup is one span. */}
      <span className="vs-logo__text">
        <span className="vs-logo__name">{settings.storeName}</span>
        {settings.tagline && <span className="vs-logo__tag">{settings.tagline}</span>}
      </span>
    </Link>
  );
}

export default function Header() {
  const location = useLocation();
  const { locale, t } = useLocale();
  const targetLocale = locale === "ar" ? "en" : "ar";
  const languageLabel = locale === "ar" ? "Switch to English" : "التبديل إلى العربية";
  const store = useStore();
  const money = useMoney();
  const { settings, cart, scrolled, overlay, openOverlay, closeAll } = store;

  const count = cart.reduce((sum, line) => sum + line.qty, 0);
  const subtotal = cart.reduce((sum, line) => sum + line.unit * line.qty, 0);
  const pulse = useCartCountPulse(count);
  const catsOpen = overlay === OVERLAY.CATEGORIES;
  const toggleCats = () => (catsOpen ? closeAll() : openOverlay(OVERLAY.CATEGORIES));

  return (
    <>
      {store.announce && settings.announcement && (
        <div className="vs-announce">
          <div className="vs-container vs-announce__row">
            <span>{settings.announcement}</span>
            <button
              type="button"
              className="vs-announce__close"
              onClick={() => store.setAnnounce(false)}
              aria-label={t("إغلاق شريط الإعلان")}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      <header className="vs-header" data-scrolled={scrolled}>
        <div className="vs-header__main">
          <div className="vs-container vs-header__row">
            <button
              type="button"
              className="vs-iconbtn vs-mob"
              onClick={() => openOverlay(OVERLAY.MENU)}
              aria-label={t("فتح القائمة")}
              aria-expanded={overlay === OVERLAY.MENU}
            >
              <MenuIcon size={20} />
            </button>

            {/* The fixed category rail is desktop-only, so its trigger has to
                exist here for a phone — same overlay, same categories. */}
            <button
              type="button"
              className="vs-iconbtn vs-mob"
              onClick={toggleCats}
              aria-label={t("تصنيفات المنتجات")}
              aria-expanded={catsOpen}
              aria-controls="vs-catdrawer"
            >
              <GridIcon size={19} />
            </button>

            <StoreMark settings={settings} />

            <div className="vs-desk vs-header__search">
              <SearchBox />
            </div>

            <div className="vs-hactions">
              <LanguageLink className="vs-iconbtn vs-language-toggle" lang={targetLocale}
                hrefLang={targetLocale} aria-label={languageLabel} title={languageLabel}
                to={{ pathname: localePath(location.pathname, targetLocale), search: location.search, hash: location.hash }}>
                <GlobeIcon size={17} />
                <span className="vs-language-toggle__label" aria-hidden="true">{locale === "ar" ? "EN" : "ع"}</span>
              </LanguageLink>
              <button
                type="button"
                className="vs-iconbtn vs-mob"
                onClick={() => openOverlay(OVERLAY.SEARCH)}
                aria-label={t("فتح البحث")}
                aria-expanded={overlay === OVERLAY.SEARCH}
              >
                <SearchIcon size={19} />
              </button>

              <Link to="/admin/login" className="vs-iconbtn" aria-label={t("تسجيل دخول الإدارة")} title={t("تسجيل دخول الإدارة")}>
                <UserIcon size={18} />
              </Link>

              <button
                type="button"
                className="vs-cartbtn"
                onClick={() => openOverlay(OVERLAY.CART)}
                aria-label={t("عربة التسوّق")}
                aria-expanded={overlay === OVERLAY.CART}
              >
                <CartIcon size={19} />
                <span className="vs-desk vs-cartbtn__total">{money(subtotal)}</span>
                <span
                  key={pulse}
                  className="vs-cartbtn__badge"
                  data-motion="transform"
                  style={{ animation: pulse ? "vs-pulse .42s ease" : "none" }}
                >
                  {count}
                </span>
              </button>
            </div>
          </div>
        </div>

        <nav className="vs-nav" aria-label={t("التنقّل الرئيسي")}>
          <div className="vs-container vs-nav__row">
            <button
              type="button"
              className="vs-nav__cats"
              onClick={toggleCats}
              aria-expanded={catsOpen}
              aria-controls="vs-catdrawer"
            >
              <MenuIcon size={15} />{t("كل الأقسام")}{" "}</button>

            {navLinks.map((link) => (
              <NavLink
                key={link.href}
                to={link.href}
                end={link.href === "/"}
                className="vs-nav__link"
              >
                {t(link.label)}
              </NavLink>
            ))}

          </div>
        </nav>
      </header>
    </>
  );
}
