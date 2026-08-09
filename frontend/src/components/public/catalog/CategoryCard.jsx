import { Link } from "react-router-dom";
import Media from "../shell/Media.jsx";
import { ArrowForward } from "../shell/icons.jsx";

/**
 * Image-only category tile: the artwork fills the card and the name sits centred
 * over it, readable at rest above a base overlay. Hover and keyboard focus do the
 * same thing — scale the image slightly, deepen the overlay and bring up a
 * translucent plate behind the name — so nothing is hover-only and nothing moves.
 *
 * The whole card is one link, and the product count stays in the accessible name
 * rather than on the artwork, which keeps the tile image-led.
 */
export default function CategoryCard({ category, compact = false, eager = false }) {
  if (!category) return null;
  return (
    <Link
      to={category.href}
      className={`vs-cat${compact ? " vs-cat--compact" : ""}`}
      aria-label={`${category.name} — ${category.countText}`}
    >
      <Media
        ratio="var(--vs-ar-category)"
        src={category.imageUrl}
        fallback={category.bg}
        alt=""
        imgClass="vs-cat__img"
        eager={eager}
      />
      <span className="vs-cat__veil" />
      <span className="vs-cat__center">
        <span className="vs-cat__plate">
          <span className="vs-cat__name">{category.name}</span>
          {!compact && (
            <span className="vs-cat__go">
              تصفّح القسم <ArrowForward size={14} />
            </span>
          )}
        </span>
      </span>
    </Link>
  );
}
