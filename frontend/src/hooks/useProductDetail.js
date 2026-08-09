import { useEffect, useMemo, useState } from "react";
import { catalogService } from "../services/catalog.js";

/**
 * Loads a full product by slug. Both the product page and the quick view need
 * the same record — options, variants, gallery — so they share one fetch shape
 * and one status vocabulary.
 */
export function useProductDetail(slug) {
  const [product, setProduct] = useState(null);
  const [status, setStatus] = useState(slug ? "loading" : "idle");

  useEffect(() => {
    if (!slug) {
      setProduct(null);
      setStatus("idle");
      return undefined;
    }
    let cancelled = false;
    setStatus("loading");
    catalogService
      .bySlug(slug)
      .then((value) => {
        if (cancelled) return;
        setProduct(value);
        setStatus("ready");
      })
      .catch((error) => {
        if (cancelled) return;
        setProduct(null);
        setStatus(error.status === 404 ? "missing" : "error");
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  return { product, status };
}

/**
 * Variant selection for a product that has options.
 *
 * Nothing is selected up front: silently defaulting to the first variant would
 * put a size the visitor never chose into the cart.
 */
export function useVariantSelection(product) {
  const [variantId, setVariantId] = useState(null);

  useEffect(() => setVariantId(null), [product?.id]);

  const variants = useMemo(
    () => (product?.variants || []).filter((variant) => variant.is_active),
    [product],
  );

  const selected = useMemo(
    () => variants.find((variant) => variant.id === variantId) || null,
    [variants, variantId],
  );

  // Options declared without any variant row cannot be honoured from a card or a
  // quick view; those products are sent to the full product page instead.
  const requiresChoice = !!product?.hasOptions && variants.length > 0;
  const unavailable = !!product?.hasOptions && variants.length === 0;

  const price = selected?.price_override != null
    ? Number(selected.price_override)
    : (product?.sale ?? product?.price ?? 0);

  const stock = selected ? selected.stock_quantity : product?.stock ?? 0;
  const soldOut = product ? (product.trackInventory ? stock <= 0 : !product.inStock) : true;

  return {
    variants,
    variantId,
    setVariantId,
    selected,
    requiresChoice,
    unavailable,
    missingChoice: requiresChoice && !selected,
    price,
    stock,
    soldOut,
  };
}
