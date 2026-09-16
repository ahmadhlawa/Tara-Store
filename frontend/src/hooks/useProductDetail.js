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
  const [simpleChoices, setSimpleChoices] = useState({});
  const [presentationValueId, setPresentationValueId] = useState(null);

  useEffect(() => { setVariantId(null); setSimpleChoices({}); setPresentationValueId(null); }, [product?.id]);

  const variants = useMemo(
    () => (product?.variants || []).filter((variant) => variant.is_active),
    [product],
  );

  const presentationOption = (product?.options || []).find((option) => option.drives_presentation) || null;
  const defaultPresentationValue = presentationOption?.values?.[0] || null;
  const effectivePresentationValueId = presentationValueId ?? defaultPresentationValue?.id ?? null;
  const selectedPresentationValue = presentationOption?.values?.find(
    (value) => Number(value.id) === Number(effectivePresentationValueId),
  ) || null;
  const defaultVariant = presentationOption && (product?.options || []).length === 1
    ? variants.find((variant) => (variant.option_value_ids || []).length === 1
      && Number(variant.option_value_ids[0]) === Number(effectivePresentationValueId)) || null
    : null;
  const selected = variants.find((variant) => variant.id === variantId) || defaultVariant;

  // Options declared without any variant row cannot be honoured from a card or a
  // quick view; those products are sent to the full product page instead.
  const simple = !!product?.hasOptions && variants.length === 0;
  const effectiveSimpleChoices = presentationOption && simpleChoices[presentationOption.id] == null
    ? { ...simpleChoices, [presentationOption.id]: effectivePresentationValueId }
    : simpleChoices;
  const selectedOptionValueIds = Object.values(effectiveSimpleChoices).filter((value) => value != null).map(Number);
  const requiresChoice = !!product?.hasOptions;
  const unavailable = false;
  const simpleComplete = !simple || selectedOptionValueIds.length === (product?.options || []).length;
  const simpleValue = simple ? (product?.options || []).flatMap((option) => option.values || []).find(
    (value) => selectedOptionValueIds.includes(Number(value.id)) && value.price_override != null,
  ) : null;
  const simpleSelection = simpleComplete && simple ? {
    selected_option_value_ids: selectedOptionValueIds,
    title: (product.options || []).flatMap((option) => (option.values || []).filter((value) => selectedOptionValueIds.includes(Number(value.id))).map((value) => `${option.name}: ${value.value}`)).join("، "),
    price_override: simpleValue?.price_override ?? null,
  } : null;

  const price = (selected || simpleSelection)?.price_override != null
    ? Number((selected || simpleSelection).price_override)
    : (product?.sale ?? product?.price ?? 0);

  const stock = selected ? selected.stock_quantity : product?.stock ?? 0;
  const soldOut = product ? (product.trackInventory ? stock <= 0 : !product.inStock) : true;

  return {
    variants,
    variantId: selected?.id ?? variantId,
    setVariantId,
    simpleChoices: effectiveSimpleChoices,
    setSimpleChoice: (optionId, valueId) => {
      setSimpleChoices((current) => ({ ...current, [optionId]: valueId }));
      if (Number(optionId) === Number(presentationOption?.id)) setPresentationValueId(valueId);
    },
    presentationOption,
    selectedPresentationValue,
    presentationValueId: effectivePresentationValueId,
    setPresentationValueId,
    selected: selected || simpleSelection,
    selectedOptionValueIds,
    requiresChoice,
    unavailable,
    missingChoice: requiresChoice && !(selected || simpleSelection),
    price,
    stock,
    soldOut,
  };
}
