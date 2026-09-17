import { useLocale } from "../../../i18n/locale.jsx";
import { Drawer } from "../overlays/Overlay.jsx";
import SearchBox from "./SearchBox.jsx";

/** Mobile search sheet. Same SearchBox, dropped from the top of the screen. */
export default function SearchOverlay({ open, onClose }) {
  const { t } = useLocale();
  return (
    <Drawer
      open={open}
      onClose={onClose}
      side="top"
      label={t("البحث")}
      head={<strong className="vs-drawer__title">{t("ابحث في المتجر")}</strong>}
    >
      <div className="vs-searchsheet">
        <SearchBox autoFocus onNavigate={onClose} />
      </div>
    </Drawer>
  );
}
