import { NavLink } from "react-router-dom";
import { OVERLAY, useStore } from "../../../app/StoreProvider.jsx";
import { useActiveCategorySlug, useCategoryNav } from "../../../hooks/useStorefront.js";
import { MenuIcon, TagIcon } from "../shell/icons.jsx";
import { useCategoryHover } from "./CategoryHover.jsx";

/**
 * The fixed category rail at the far right of the desktop viewport.
 *
 * It is a gutter, not an overlay: `.vs-public` reserves `--vs-rail-gutter` on its
 * physical right, so the rail can never end up on top of the page. Below 900px it
 * leaves the layout entirely and its trigger moves into the header — nothing here
 * is the only way to reach a category, and nothing depends on hover.
 *
 * Content is whatever the categories API returns; there is no hard-coded list in this
 * file, and it shares `OVERLAY.CATEGORIES` with the header trigger so the two can
 * never disagree about whether the drawer is open.
 */
export default function CategoryRail() {
  const { overlay, openOverlay, closeAll } = useStore();
  const activeSlug = useActiveCategorySlug();
  const categories = useCategoryNav(activeSlug);
  const { hoverProps, claimAsClick } = useCategoryHover();

  if (!categories.length) return null;
  const open = overlay === OVERLAY.CATEGORIES;

  // A navigation landmark, not a complementary one: everything in it is a route
  // into the catalogue, and it is labelled so it sits alongside the header nav
  // without either becoming ambiguous.
  return (
    <nav className="vs-catbar" aria-label="أقسام المتجر" data-open={open} {...hoverProps}>
      <button
        type="button"
        className="vs-catbar__trigger"
        onClick={() => {
          claimAsClick();
          if (open) closeAll();
          else openOverlay(OVERLAY.CATEGORIES);
        }}
        aria-expanded={open}
        aria-controls="vs-catdrawer"
        aria-label="تصنيفات المنتجات"
        title="تصنيفات المنتجات"
      >
        <MenuIcon size={18} />
      </button>

      {/* The icon column is the collapsed face of the drawer, not a companion to
          it: while the panel is open it is the panel that lists the categories,
          so the rail drops its copy rather than standing beside it as a second
          column of the same thumbnails. The trigger stays — it is what reports
          and toggles the state. */}
      {!open && (
        <>
          <span className="vs-catbar__rule" aria-hidden="true" />

          <ul className="vs-catbar__list">
            {categories.map((category) => (
              <li key={category.slug}>
                <NavLink
                  to={category.href}
                  className="vs-catbar__item"
                  data-active={category.active}
                  aria-current={category.active ? "page" : undefined}
                  aria-label={category.name}
                  title={category.name}
                >
                  {/* The category's own picture where the store has uploaded one,
                      and a neutral icon where it has not — never a tinted square
                      standing in for a photograph that does not exist. */}
                  {category.imageUrl ? (
                    <img className="vs-catbar__thumb" src={category.imageUrl} alt="" loading="lazy" />
                  ) : (
                    <span className="vs-catbar__ico" aria-hidden="true">
                      <TagIcon size={18} />
                    </span>
                  )}
                  {/* Presentational: the accessible name already comes from
                      aria-label, so a screen reader must not hear it twice. */}
                  <span className="vs-catbar__tip" aria-hidden="true">
                    {category.name}
                  </span>
                </NavLink>
              </li>
            ))}
          </ul>
        </>
      )}
    </nav>
  );
}
