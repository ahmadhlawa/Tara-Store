// One place that turns a normalized product into everything a card, a quick
// view or a detail page needs to display. Pure — no hooks, no store — so the
// same shape is reachable from tests and from every surface.
import { discountPercent } from "./format.js";

export const PRODUCT_ACTION = {
  ADD: "add",
  CHOOSE: "choose",
  SOLD_OUT: "sold-out",
};

const ACTION_LABEL = {
  [PRODUCT_ACTION.ADD]: "أضف إلى العربة",
  [PRODUCT_ACTION.CHOOSE]: "اختر الخيارات",
  [PRODUCT_ACTION.SOLD_OUT]: "غير متوفر حالياً",
};

const PACKAGE_ACTION_LABEL = {
  [PRODUCT_ACTION.ADD]: "أضف البكج إلى العربة",
  [PRODUCT_ACTION.CHOOSE]: "اختر الخيارات",
  [PRODUCT_ACTION.SOLD_OUT]: "غير متوفر حالياً",
};

/** Which of the three add-to-cart behaviours a product gets. */
export function productAction(product) {
  if (!product) return PRODUCT_ACTION.SOLD_OUT;
  if (!product.inStock) return PRODUCT_ACTION.SOLD_OUT;
  if (product.hasOptions) return PRODUCT_ACTION.CHOOSE;
  return PRODUCT_ACTION.ADD;
}

export function productView(product, money) {
  if (!product) return null;
  const hasSale = product.sale != null;
  const effective = hasSale ? product.sale : product.price;
  const isPackage = product.productType === "package";
  const action = productAction(product);
  const labels = isPackage ? PACKAGE_ACTION_LABEL : ACTION_LABEL;

  return {
    id: product.id,
    slug: product.slug,
    name: product.name,
    href: `/product/${product.slug}`,
    categoryName: product.categoryName,
    categoryHref: product.categorySlug ? `/category/${product.categorySlug}` : null,
    short: product.short,
    imageUrl: product.imageUrl,
    // Null unless the product genuinely has a second picture. Cards branch on
    // it rather than inventing one, so a single-image product simply keeps its
    // cover and reveals only the action panel.
    secondaryImageUrl: product.secondaryImageUrl || null,
    bg: product.bg,
    isPackage,
    packageCount: product.packageItemCount || product.packageItems?.length || 0,
    packageItems: product.packageItems || [],
    hasSale,
    price: effective,
    priceText: money(effective),
    oldText: hasSale ? money(product.price) : "",
    discount: hasSale ? discountPercent(product.sale, product.price) : 0,
    discountText: hasSale ? `−${discountPercent(product.sale, product.price)}٪` : "",
    isNew: !!product.isNew,
    featured: !!product.featured,
    bestSeller: !!product.bestSeller,
    soldOut: !product.inStock,
    lowStock: product.trackInventory && product.inStock && product.stock > 0 && product.stock < 5,
    stock: product.stock,
    trackInventory: product.trackInventory,
    action,
    actionLabel: labels[action],
    canAddDirectly: action === PRODUCT_ACTION.ADD,
    product,
  };
}

/** At most two badges, ranked, so a card never turns into a sticker sheet. */
export function productBadges(view) {
  if (!view) return [];
  const all = [];
  if (view.hasSale) all.push({ key: "sale", label: view.discountText, tone: "sale" });
  if (view.isNew) all.push({ key: "new", label: "جديد", tone: "new" });
  if (view.bestSeller) all.push({ key: "best", label: "الأكثر مبيعاً", tone: "best" });
  if (view.featured) all.push({ key: "featured", label: "مُختار", tone: "featured" });
  return all.slice(0, 2);
}
