import { Link } from "react-router-dom";
import AddToCartButton from "../../AddToCartButton.jsx";
import Media from "../shell/Media.jsx";
import { productBadges } from "../../../utils/productView.js";
import { useCardReveal } from "../../../hooks/useCardReveal.js";
import { useViewportReveal } from "../../../hooks/useViewportReveal.js";
import { useProductActions } from "../../../hooks/useStorefront.js";
import { EyeIcon, PlusIcon } from "../shell/icons.jsx";

/**
 * The catalogue card. Takes a view built by `productView`, so a card never
 * reaches into the raw API shape and every surface shows the same states.
 *
 * At rest it is its picture: badges and a sold-out state over the artwork and
 * nothing else. Everything a shopper acts on — name, price, stock, the product's
 * own button, quick view — lives in a panel that rises from the bottom on hover,
 * on keyboard focus, or on the first tap of a coarse pointer. The panel is
 * absolutely positioned, so revealing it never changes the card's height and
 * never moves the row. Below 900px it is laid out statically and always visible,
 * because a phone has no hover to depend on.
 *
 * The primary button is the product's own action: a direct add for a simple
 * product, "choose an option" for one that needs a variant, and disabled when
 * the product is sold out.
 */
export default function ProductCard({ view, eager = false, revealDelay = 0 }) {
  const { openQuick, primaryAction } = useProductActions();
  const { cardProps } = useCardReveal();
  const revealProps = useViewportReveal(revealDelay);
  if (!view) return null;

  const badges = productBadges(view);
  // Sold out is already stated over the artwork and on the disabled button, so
  // the panel stays quiet about it rather than saying it a third time.
  const stockLabel = view.soldOut ? "" : view.lowStock ? `بقي ${view.stock} فقط` : "متوفر";

  return (
    <article className="vs-card" {...revealProps} {...cardProps}>
      <div className="vs-card__media">
        <Link to={view.href} className="vs-card__link" aria-label={view.name}>
          <Media
            ratio="var(--vs-ar-product)"
            src={view.imageUrl}
            fallback={view.bg}
            alt=""
            imgClass="vs-card__img"
            eager={eager}
          />
          {/* Only when the product genuinely has a second picture. Nothing is
              substituted for one that does not. */}
          {view.secondaryImageUrl && (
            <img
              className="vs-card__img2"
              src={view.secondaryImageUrl}
              alt=""
              loading="lazy"
              decoding="async"
            />
          )}
        </Link>

        {badges.length > 0 && (
          <div className="vs-card__badges">
            {badges.map((badge) => (
              <span key={badge.key} className={`vs-badge vs-badge--${badge.tone}`}>
                {badge.label}
              </span>
            ))}
          </div>
        )}

        {view.soldOut && (
          <div className="vs-card__veil">
            <span>غير متوفر حالياً</span>
          </div>
        )}
      </div>

      <div className="vs-card__panel">
        <Link to={view.href} className="vs-card__title vs-clamp-2">
          {view.name}
        </Link>

        <div className="vs-card__meta">
          <div className="vs-price">
            <span className="vs-price__now">{view.priceText}</span>
            {view.hasSale && <span className="vs-price__was">{view.oldText}</span>}
          </div>
          {stockLabel && <span className="vs-card__stock">{stockLabel}</span>}
        </div>

        <div className="vs-card__acts">
          <AddToCartButton
            onAdd={primaryAction(view)}
            label={view.actionLabel}
            icon={view.canAddDirectly ? <PlusIcon size={15} /> : null}
            disabled={view.soldOut}
            className="vs-btn vs-btn--primary vs-card__cta"
          />
          <button
            type="button"
            className="vs-iconbtn vs-card__quick"
            onClick={() => openQuick(view)}
            aria-label={`نظرة سريعة على ${view.name}`}
            title="نظرة سريعة"
          >
            <EyeIcon size={16} />
          </button>
        </div>
      </div>
    </article>
  );
}
