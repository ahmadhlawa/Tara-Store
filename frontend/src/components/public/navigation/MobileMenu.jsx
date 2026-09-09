import { Link } from "react-router-dom";
import { useStore } from "../../../app/StoreProvider.jsx";
import { whatsappHref } from "../../../utils/format.js";
import { Drawer } from "../overlays/Overlay.jsx";
import { WhatsAppIcon } from "../shell/icons.jsx";
import { navLinks } from "../../../store.js";

export default function MobileMenu({ open, onClose }) {
  const { settings } = useStore();
  const wa = whatsappHref(settings.whatsapp, `مرحباً، لدي استفسار عن ${settings.storeName}`);

  return (
    <Drawer
      open={open}
      onClose={onClose}
      side="right"
      label="قائمة التنقّل"
      head={<strong className="vs-drawer__title">{settings.storeName}</strong>}
      footer={
        wa !== "#" && (
            <a
              href={wa}
              target="_blank"
              rel="noopener"
              className="vs-btn vs-btn--block vs-menu__wa"
            >
              <WhatsAppIcon size={18} /> تواصل عبر واتساب
            </a>
        )
      }
    >
      <div className="vs-menu">
        <p className="vs-menu__label">روابط</p>
        {navLinks.map((link) => (
          <Link key={link.href} to={link.href} className="vs-menu__link" onClick={onClose}>
            {link.label}
          </Link>
        ))}
      </div>
    </Drawer>
  );
}
