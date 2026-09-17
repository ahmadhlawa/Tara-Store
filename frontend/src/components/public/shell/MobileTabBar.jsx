import { useLocale } from "../../../i18n/locale.jsx";
import { useLocation } from "react-router-dom";
import { Link } from "../../../i18n/routing.jsx";
import { OVERLAY, useStore } from "../../../app/StoreProvider.jsx";
import { CartIcon, HomeIcon, SearchIcon } from "./icons.jsx";

/**
 * Thumb-reachable bar with the four verbs a phone visitor needs most. Every
 * target is a full 64px tall slot, and nothing here depends on hover.
 */
export default function MobileTabBar() {
  const { t } = useLocale();
  const { pathname } = useLocation();
  const store = useStore();
  const count = store.cart.reduce((sum, line) => sum + line.qty, 0);

  return (
    <nav className="vs-tabbar" aria-label={t("تنقّل سريع")}>
      <Link
        to="/"
        className="vs-tabbar__item"
        aria-current={/^\/(ar|en)\/?$/.test(pathname) ? "page" : undefined}
      >
        <HomeIcon size={21} />{t("الرئيسية")}{" "}</Link>

      <button
        type="button"
        className="vs-tabbar__item"
        onClick={() => store.openOverlay(OVERLAY.SEARCH)}
        aria-expanded={store.overlay === OVERLAY.SEARCH}
      >
        <SearchIcon size={21} />{t("البحث")}{" "}</button>

      <button
        type="button"
        className="vs-tabbar__item"
        onClick={() => store.openOverlay(OVERLAY.CART)}
        aria-expanded={store.overlay === OVERLAY.CART}
      >
        <CartIcon size={21} />
        {count > 0 && <span className="vs-tabbar__badge">{count}</span>}{t("العربة")}{" "}</button>
    </nav>
  );
}
