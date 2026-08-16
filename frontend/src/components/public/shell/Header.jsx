import { Link, NavLink } from "react-router-dom";
import { OVERLAY, useStore } from "../../../app/StoreProvider.jsx";
import { useCartCountPulse } from "../../../hooks/useCartCountPulse.js";
import { useLogoFit } from "../../../hooks/useLogoFit.js";
import { useMoney } from "../../../hooks/useStorefront.js";
import { navLinks } from "../../../store.js";
import SearchBox from "../search/SearchBox.jsx";
import { CartIcon, GridIcon, MenuIcon, PhoneIcon, SearchIcon, UserIcon } from "./icons.jsx";

function StoreMark({ settings }) {
  // The file is left exactly as the owner supplied it; only how much of the box
  // its artwork is allowed to fill is decided here. See useLogoFit.
  const { boxRef, style } = useLogoFit(settings.logoUrl);
  return (
    <Link to="/" className="vs-logo" aria-label={`${settings.storeName} — الصفحة الرئيسية`}>
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
              aria-label="إغلاق شريط الإعلان"
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
              aria-label="فتح القائمة"
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
              aria-label="تصنيفات المنتجات"
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
              {settings.phone && (
                <a
                  className="vs-iconbtn"
                  href={`tel:${settings.phone}`}
                  aria-label="اتصل بنا"
                  title="اتصل بنا"
                >
                  <PhoneIcon size={18} />
                </a>
              )}

              <button
                type="button"
                className="vs-iconbtn vs-mob"
                onClick={() => openOverlay(OVERLAY.SEARCH)}
                aria-label="فتح البحث"
                aria-expanded={overlay === OVERLAY.SEARCH}
              >
                <SearchIcon size={19} />
              </button>

              <Link to="/admin/login" className="vs-iconbtn" aria-label="تسجيل دخول الإدارة" title="تسجيل دخول الإدارة">
                <UserIcon size={18} />
              </Link>

              <button
                type="button"
                className="vs-cartbtn"
                onClick={() => openOverlay(OVERLAY.CART)}
                aria-label="عربة التسوّق"
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

        <nav className="vs-nav" aria-label="التنقّل الرئيسي">
          <div className="vs-container vs-nav__row">
            <button
              type="button"
              className="vs-nav__cats"
              onClick={toggleCats}
              aria-expanded={catsOpen}
              aria-controls="vs-catdrawer"
            >
              <MenuIcon size={15} />
              كل الأقسام
            </button>

            {navLinks.map((link) => (
              <NavLink
                key={link.href}
                to={link.href}
                end={link.href === "/"}
                className="vs-nav__link"
              >
                {link.label}
              </NavLink>
            ))}

            {settings.hours && (
              <span className="vs-nav__hours">
                <span aria-hidden="true">✦</span>
                {settings.hours}
              </span>
            )}
          </div>
        </nav>
      </header>
    </>
  );
}
