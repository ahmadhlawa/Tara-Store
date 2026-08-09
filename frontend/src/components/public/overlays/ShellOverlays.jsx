import { OVERLAY, useStore } from "../../../app/StoreProvider.jsx";
import { whatsappHref } from "../../../utils/format.js";
import CartDrawer from "../cart/CartDrawer.jsx";
import CategoryDrawer from "../navigation/CategoryDrawer.jsx";
import MobileMenu from "../navigation/MobileMenu.jsx";
import SearchOverlay from "../search/SearchOverlay.jsx";
import QuickView from "./QuickView.jsx";
import Toast from "./Toast.jsx";
import { WhatsAppIcon } from "../shell/icons.jsx";

/**
 * Every shell-level overlay in one place, all driven by the single `overlay`
 * value — which is what makes "only one open at a time" a property of the state
 * rather than a rule each trigger has to remember.
 */
export default function ShellOverlays() {
  const store = useStore();
  const { overlay, closeAll, settings } = store;

  const wa = whatsappHref(settings.whatsapp, `مرحباً، لدي استفسار عن ${settings.storeName}`);

  return (
    <>
      <CategoryDrawer open={overlay === OVERLAY.CATEGORIES} onClose={closeAll} />
      <MobileMenu open={overlay === OVERLAY.MENU} onClose={closeAll} />
      <SearchOverlay open={overlay === OVERLAY.SEARCH} onClose={closeAll} />
      <CartDrawer open={overlay === OVERLAY.CART} onClose={closeAll} />
      <QuickView open={overlay === OVERLAY.QUICK} slug={store.quickSlug} onClose={closeAll} />

      <Toast message={store.toast} onView={() => store.openOverlay(OVERLAY.CART)} />

      {wa !== "#" && (
        <a
          className="vs-wa"
          href={wa}
          target="_blank"
          rel="noopener"
          aria-label="تواصل عبر واتساب"
        >
          <WhatsAppIcon size={24} />
        </a>
      )}
    </>
  );
}
