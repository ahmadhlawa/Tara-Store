import { Link } from "react-router-dom";
import { useStore } from "../../../app/StoreProvider.jsx";
import { useActiveCategorySlug, useCategoryNav } from "../../../hooks/useStorefront.js";
import { Drawer } from "../overlays/Overlay.jsx";
import { ArrowForward, ChevronDown, TagIcon } from "../shell/icons.jsx";
import { useCategoryHover } from "./CategoryHover.jsx";

/**
 * The category panel, opened from the rail trigger on desktop and from the header
 * trigger on mobile — one component, one overlay state, one data source.
 *
 * Scrim, body scroll lock, Escape, focus trap and focus restoration all come from
 * `Drawer`; a route change closes it through the shell's own `closeAll`.
 */
export default function CategoryDrawer({ open, onClose }) {
  const { navOpenCat, setNavOpenCat } = useStore();
  const activeSlug = useActiveCategorySlug();
  const categories = useCategoryNav(activeSlug);
  const { hoverProps, openedByHover } = useCategoryHover();

  return (
    <Drawer
      open={open}
      onClose={onClose}
      side="right"
      // Hover carries on into the drawer, so the pair reads as one surface; a
      // drawer the pointer merely brushed past must not take the keyboard.
      hoverProps={hoverProps}
      autoFocus={!openedByHover}
      id="vs-catdrawer"
      className="vs-drawer--cats"
      label="تصنيفات المنتجات"
      title="تصنيفات المنتجات"
      bodyClass="vs-catdrawer"
      footer={
        <Link to="/shop" className="vs-btn vs-btn--primary vs-btn--block" onClick={onClose}>
          تصفّح كل المنتجات <ArrowForward size={16} />
        </Link>
      }
    >
      {categories.length === 0 ? (
        <p className="vs-catdrawer__empty">لا توجد أقسام معروضة حالياً.</p>
      ) : (
        <ul className="vs-catdrawer__list">
          {categories.map((category) => {
            const expanded = navOpenCat === category.slug;
            const hasChildren = category.children.length > 0;
            return (
              <li key={category.slug} className="vs-catdrawer__item">
                <div className="vs-catdrawer__row">
                  <Link
                    to={category.href}
                    className="vs-catdrawer__link"
                    data-active={category.active}
                    aria-current={category.active ? "page" : undefined}
                    onClick={onClose}
                  >
                    {/* Same rule as the rail: the category's own picture, or a
                        neutral icon — never a tint pretending to be one. */}
                    <span className="vs-catdrawer__thumb">
                      {category.imageUrl ? (
                        <img src={category.imageUrl} alt="" loading="lazy" />
                      ) : (
                        <TagIcon size={20} />
                      )}
                    </span>
                    <span className="vs-catdrawer__text">
                      <span className="vs-catdrawer__name">{category.name}</span>
                      <span className="vs-catdrawer__count">{category.countText}</span>
                    </span>
                  </Link>

                  {hasChildren && (
                    <button
                      type="button"
                      className="vs-iconbtn vs-iconbtn--bare vs-catdrawer__toggle"
                      onClick={() => setNavOpenCat(expanded ? null : category.slug)}
                      aria-expanded={expanded}
                      aria-label={`الأقسام الفرعية لـ ${category.name}`}
                      data-open={expanded}
                    >
                      <ChevronDown size={16} />
                    </button>
                  )}
                </div>

                {hasChildren && expanded && (
                  <ul className="vs-catdrawer__children">
                    {category.children.map((child) => (
                      <li key={child.slug}>
                        <Link
                          to={child.href}
                          className="vs-catdrawer__child"
                          data-active={child.active}
                          aria-current={child.active ? "page" : undefined}
                          onClick={onClose}
                        >
                          {child.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Drawer>
  );
}
