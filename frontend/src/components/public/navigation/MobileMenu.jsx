import { Link } from "react-router-dom";
import { useStore } from "../../../app/StoreProvider.jsx";
import { useCategoryNav } from "../../../hooks/useStorefront.js";
import { whatsappHref } from "../../../utils/format.js";
import { Drawer } from "../overlays/Overlay.jsx";
import Media from "../shell/Media.jsx";
import { ChevronDown, WhatsAppIcon } from "../shell/icons.jsx";
import { navLinks } from "../../../store.js";

export default function MobileMenu({ open, onClose }) {
  const store = useStore();
  const categories = useCategoryNav();
  const { settings, navOpenCat, setNavOpenCat } = store;
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
        <p className="vs-menu__label">الأقسام</p>
        {categories.map((category) => {
          const expanded = navOpenCat === category.slug;
          return (
            <div key={category.slug} className="vs-menu__cat">
              <div className="vs-menu__catrow">
                <Link to={category.href} className="vs-menu__catlink" onClick={onClose}>
                  <Media
                    className="vs-menu__thumb"
                    src={category.imageUrl}
                    fallback={category.bg}
                    alt=""
                  />
                  <span>
                    <span className="vs-menu__catname">{category.name}</span>
                    <span className="vs-menu__catcount">{category.countText}</span>
                  </span>
                </Link>
                {category.children.length > 0 && (
                  <button
                    type="button"
                    className="vs-iconbtn vs-iconbtn--bare vs-menu__toggle"
                    onClick={() => setNavOpenCat(expanded ? null : category.slug)}
                    aria-expanded={expanded}
                    aria-label={`الأقسام الفرعية لـ ${category.name}`}
                    data-open={expanded}
                  >
                    <ChevronDown size={16} />
                  </button>
                )}
              </div>
              {expanded && category.children.length > 0 && (
                <div className="vs-menu__children">
                  {category.children.map((child) => (
                    <Link
                      key={child.slug}
                      to={child.href}
                      className="vs-menu__child"
                      onClick={onClose}
                    >
                      {child.name}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          );
        })}

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
