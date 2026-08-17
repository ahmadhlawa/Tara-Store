import ProductCard from "./ProductCard.jsx";
import PackageCard from "./PackageCard.jsx";

/**
 * Skeleton that matches the real card's box, so nothing shifts when data lands.
 * A card is now its image on desktop and image-plus-panel below 900px, and the
 * skeleton follows exactly that — the placeholder rows are inside the same
 * media-query, so it cannot promise a body the card will not have.
 */
export function CardSkeleton() {
  return (
    <div className="vs-cardskel" aria-hidden="true">
      <div className="vs-skel vs-cardskel__media" />
      <div className="vs-cardskel__body">
        <div className="vs-skel" style={{ height: 13, width: "88%" }} />
        <div className="vs-skel" style={{ height: 13, width: "56%" }} />
        <div className="vs-skel" style={{ height: 40, marginTop: 6 }} />
      </div>
    </div>
  );
}

const WRAPPER = {
  grid: "vs-grid",
  packages: "vs-grid vs-grid--packages",
  categories: "vs-grid vs-grid--cats",
  rail: "vs-rail",
  // "plain" emits the cards with no wrapper, for a parent that already is a grid.
  plain: null,
};

export function GridSkeleton({ count = 8, variant = "grid" }) {
  return (
    <div className={WRAPPER[variant] || WRAPPER.grid} aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <CardSkeleton key={index} />
      ))}
    </div>
  );
}

/**
 * One grid for products and packages alike: a package renders its own card, so
 * a mixed result set still reads correctly.
 */
export default function ProductGrid({ views, variant = "grid", eagerCount = 4 }) {
  if (!views?.length) return null;
  const cards = views.map((view, index) =>
    view.isPackage ? (
      <PackageCard key={view.id} view={view} eager={index < eagerCount} revealDelay={Math.min(index * 70, 280)} />
    ) : (
      <ProductCard key={view.id} view={view} eager={index < eagerCount} revealDelay={Math.min(index * 70, 280)} />
    ),
  );
  const wrapper = WRAPPER[variant];
  return wrapper ? <div className={wrapper}>{cards}</div> : cards;
}
