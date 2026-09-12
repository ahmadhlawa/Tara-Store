import { useEffect, useMemo, useState } from "react";
import sx from "../../sx.js";
import { adminApi } from "../../api/adminApi.js";
import { Button, Field, input } from "../ui.jsx";

const keyOf = (ids) => [...ids].map(Number).sort((a, b) => a - b).join("-");

export default function CatalogItemPicker({ products, disabled, onAdd }) {
  const [productId, setProductId] = useState("");
  const [product, setProduct] = useState(null);
  const [choices, setChoices] = useState({});
  const [variantId, setVariantId] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setProduct(null); setChoices({}); setVariantId("");
    if (!productId) return;
    let active = true;
    setLoading(true);
    adminApi.getProduct(productId).then((row) => active && setProduct(row)).catch(() => active && setProduct(null)).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [productId]);

  const axes = (product?.options || []).filter((option) => option.values?.length);
  const variants = (product?.variants || []).filter((variant) => variant.is_active);
  const selectedIds = axes.map((axis) => Number(choices[axis.id])).filter(Boolean);
  const variant = useMemo(() => {
    if (!variants.length) return null;
    if (variantId) return variants.find((row) => String(row.id) === String(variantId)) || null;
    return selectedIds.length === axes.length
      ? variants.find((row) => keyOf(row.option_value_ids || []) === keyOf(selectedIds)) || null
      : null;
  }, [axes.length, selectedIds.join("-"), variantId, variants]);
  const legacyVariantList = variants.length > 0 && !axes.length;
  const requiresVariant = variants.length > 0;
  const inStock = !product?.track_inventory || (variant ? variant.stock_quantity > 0 : product?.stock_quantity > 0);
  const complete = inStock && (!requiresVariant || !!variant);
  const pricedChoice = axes.flatMap((axis) => axis.values || []).find((value) => selectedIds.includes(Number(value.id)) && value.price_override != null);
  const unitPrice = variant?.price_override ?? pricedChoice?.price_override ?? product?.price ?? "0.00";
  const description = axes.flatMap((axis) => (axis.values || []).filter((value) => Number(choices[axis.id]) === Number(value.id)).map((value) => `${axis.name}: ${value.value}`)).join("، ") || variant?.title || null;
  const sku = variant?.sku || product?.sku || null;

  const add = () => {
    if (!product || !complete) return;
    onAdd({ kind: "catalog", product_id: product.id, product_name: product.name, variant_id: variant?.id || null, selected_option_value_ids: variants.length ? [] : selectedIds, variant_description: description, sku, quantity: "1", unit_price: String(unitPrice) });
    setProductId("");
  };

  return <div style={sx`display:flex;gap:8px;align-items:end;flex-wrap:wrap`}>
    <Field title="إضافة منتج من الكتالوج"><select aria-label="إضافة منتج من الكتالوج" value={productId} onChange={(event) => setProductId(event.target.value)} disabled={disabled} style={input}><option value="">اختر منتجاً</option>{products.map((row) => <option key={row.id} value={row.id}>{row.name} · {row.sku || "—"}</option>)}</select></Field>
    {loading && <span>جارٍ تحميل الخيارات…</span>}
    {product && axes.map((axis) => <Field key={axis.id} title={`${axis.name}${requiresVariant ? " *" : " (اختياري)"}`}><select aria-label={axis.name} value={choices[axis.id] || ""} onChange={(event) => { setVariantId(""); setChoices((current) => ({ ...current, [axis.id]: event.target.value })); }} style={input}><option value="">اختر {axis.name}</option>{axis.values.map((value) => <option key={value.id} value={value.id}>{value.value}</option>)}</select></Field>)}
    {product && legacyVariantList && <Field title="الخيار"><select aria-label="الخيار" value={variantId} onChange={(event) => setVariantId(event.target.value)} style={input}><option value="">اختر الخيار</option>{variants.map((row) => <option key={row.id} value={row.id} disabled={product.track_inventory && row.stock_quantity <= 0}>{row.title}{product.track_inventory && row.stock_quantity <= 0 ? " — نفد" : ""}</option>)}</select></Field>}
    {product && complete && <span style={sx`font-size:13px;font-weight:800;align-self:center`}>السعر: {unitPrice}</span>}
    <Button variant="secondary" disabled={disabled || !product || !complete} onClick={add}>إضافة المنتج</Button>
  </div>;
}
