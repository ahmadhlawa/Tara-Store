import { useLocale } from "../../../i18n/locale.jsx";
import { Link } from "../../../i18n/routing.jsx";
import Media from "../shell/Media.jsx";
import { ArrowForward } from "../shell/icons.jsx";
import { useViewportReveal } from "../../../hooks/useViewportReveal.js";
import { CARD_IMAGE_SIZES } from "../../../utils/responsiveImage.js";

/**
 * Image-only category tile: the artwork fills the card and the name sits centred
 * over it, readable at rest above a base overlay. Hover and keyboard focus do the
 * same thing — scale the image slightly, deepen the overlay and bring up a
 * translucent plate behind the name — so nothing is hover-only and nothing moves.
 *
 * The whole card is one link, and the product count stays in the accessible name
 * rather than on the artwork, which keeps the tile image-led.
 */
export default function CategoryCard({ category, compact = false, eager = false, revealDelay = 0, sizes = CARD_IMAGE_SIZES }) {
  const { t } = useLocale();
  const revealProps = useViewportReveal(revealDelay);
  if (!category) return null;
  return (
    <Link
      to={category.href}
      className={`vs-cat${compact ? " vs-cat--compact" : ""}`}
      {...revealProps}
      aria-label={`${category.name} — ${category.countText}`}
    >
      <Media
        ratio="var(--vs-ar-category)"
        src={category.imageUrl}
        sizes={sizes}
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
            <span className="vs-cat__go">{t("تصفّح القسم")}{" "}<ArrowForward size={14} />
            </span>
          )}
        </span>
      </span>
    </Link>
  );
}
