import { Link } from "react-router-dom";
import AddToCartButton from "../../AddToCartButton.jsx";
import Media from "../shell/Media.jsx";
import { useCardReveal } from "../../../hooks/useCardReveal.js";
import { useViewportReveal } from "../../../hooks/useViewportReveal.js";
import { useProductActions } from "../../../hooks/useStorefront.js";
import { ArrowForward, BoxIcon } from "../shell/icons.jsx";

/**
 * Packages are a different product, so they get a different card: a large,
 * editorial cover and nothing else at rest.
 *
 * On hover, on keyboard focus, or on the first tap of a coarse pointer the cover
 * cross-fades to the package's second image — the one showing what is inside —
 * and a panel rises from the bottom with the price and the two things to do with
 * a package. Both come from the list payload the grid already fetched, so
 * hovering a row of cards costs no request. A package with only one picture keeps
 * its cover and reveals just the panel.
 *
 * The panel is absolutely positioned: revealing it cannot change the card's
 * height or move the row. Below 900px it is static and always visible.
 */
export default function PackageCard({ view, eager = false, revealDelay = 0 }) {
  const { primaryAction } = useProductActions();
  const { cardProps } = useCardReveal();
  const revealProps = useViewportReveal(revealDelay);
  if (!view) return null;

  const items = view.packageItems || [];
  // Whatever the payload actually knows about the contents — the item names when
  // the detail projection supplied them, otherwise the count. Never an invention.
  const contents = items.length
    ? items
        .slice(0, 3)
        .map((item) => item.label)
        .filter(Boolean)
        .join(" • ")
    : view.packageCount > 0
      ? view.packageCount === 1
        ? "يحتوي على عنصر واحد"
        : `يحتوي على ${view.packageCount} عناصر`
      : view.short || "";

  return (
    <article className="vs-pkg" {...revealProps} {...cardProps}>
      <div className="vs-pkg__media">
        <Link to={view.href} className="vs-pkg__link" aria-label={view.name}>
          <Media
            ratio="var(--vs-ar-package)"
            src={view.imageUrl}
            fallback={view.bg}
            alt=""
            imgClass="vs-pkg__img"
            eager={eager}
          />
          {view.secondaryImageUrl && (
            <img
              className="vs-pkg__img2"
              src={view.secondaryImageUrl}
              alt=""
              loading="lazy"
              decoding="async"
            />
          )}
        </Link>

        <div className="vs-pkg__badges">
          <span className="vs-badge vs-badge--package">بكج</span>
          {view.hasSale && <span className="vs-badge vs-badge--sale">{view.discountText}</span>}
        </div>

        {view.soldOut && (
          <div className="vs-card__veil">
            <span>غير متوفر حالياً</span>
          </div>
        )}
      </div>

      <div className="vs-pkg__panel">
        <Link to={view.href} className="vs-pkg__title vs-clamp-2">
          {view.name}
        </Link>

        {contents && (
          <span className="vs-pkg__contents vs-clamp-2">
            <BoxIcon size={14} />
            {contents}
          </span>
        )}

        <div className="vs-price">
          <span className="vs-price__now">{view.priceText}</span>
          {view.hasSale && <span className="vs-price__was">{view.oldText}</span>}
        </div>

        <div className="vs-pkg__acts">
          <AddToCartButton
            onAdd={primaryAction(view)}
            label={view.actionLabel}
            disabled={view.soldOut}
            className="vs-btn vs-btn--primary vs-pkg__cta"
          />
          <Link to={view.href} className="vs-btn vs-btn--quiet" data-card-action="details">
            التفاصيل <ArrowForward size={15} />
          </Link>
        </div>
      </div>
    </article>
  );
}
