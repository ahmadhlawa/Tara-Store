import { useLocale } from "../../../i18n/locale.jsx";
import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useStore } from "../../../app/StoreProvider.jsx";
import MaintenanceScreen from "../../Maintenance.jsx";
import PreviewNotice from "../../PreviewNotice.jsx";
import Header from "./Header.jsx";
import Footer from "./Footer.jsx";
import MobileTabBar from "./MobileTabBar.jsx";
import CategoryRail from "../navigation/CategoryRail.jsx";
import { CategoryHoverProvider } from "../navigation/CategoryHover.jsx";
import ShellOverlays from "../overlays/ShellOverlays.jsx";
import { buildStorefrontThemeVariables } from "../../../theme/storefrontTheme.js";
import { trackVisit } from "../../../services/analytics.js";

/**
 * The public chrome. Everything storefront lives under `.vs-public`, which is
 * where the token system is defined — the admin workspace renders outside it and
 * therefore inherits none of it.
 */
export default function PublicShell() {
  const { t } = useLocale();
  const location = useLocation();
  const store = useStore();

  useEffect(() => {
    if (store.ready && !store.settings.maintenanceMode) trackVisit(location.pathname);
  }, [location.pathname, store.ready, store.settings.maintenanceMode]);

  useEffect(() => {
    // scrollTo flushes layout; the initial page is already at the requested position.
    if (window.scrollX !== 0 || window.scrollY !== 0) window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    // A route change always dismisses whatever overlay was open; leaving one up
    // over a page the visitor did not ask for is never right.
    store.closeAll();
    // Only the path matters here: reacting to store changes would fight the user.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.search]);

  // Maintenance mode replaces the storefront in place — no redirect, so there is
  // no loop and no route to get stuck on. /admin never renders this shell.
  if (store.ready && store.settings.maintenanceMode) {
    return <MaintenanceScreen settings={store.settings} />;
  }

  return (
    <div className="vs-public" style={buildStorefrontThemeVariables(store.settings.raw)}>
      <CategoryHoverProvider>
        <a className="vs-skip" href="#vs-content">{t("تخطَّ إلى المحتوى")}{" "}</a>
        <PreviewNotice />
        <Header />
        <CategoryRail />

        <main className="vs-main" id="vs-content">
          {store.loadError && (
            <div className="vs-container" style={{ paddingTop: 16 }}>
              <div role="alert" className="vs-inline-alert">{t("تعذّر تحميل بيانات المتجر من الخادم. تأكد من تشغيل واجهة FastAPI ثم أعد تحميل الصفحة.")}{" "}</div>
            </div>
          )}
          <Outlet />
        </main>

        <Footer />
        <MobileTabBar />
        <ShellOverlays />
      </CategoryHoverProvider>
    </div>
  );
}
