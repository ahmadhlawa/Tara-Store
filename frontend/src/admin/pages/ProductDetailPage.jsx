import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { adminApi } from "../../api/adminApi.js";
import sx from "../../sx.js";
import { Badge, Button, PageHeader, Spinner, card, useFeedback } from "../ui.jsx";

const show = (content) => content ?? "—";

export default function ProductDetailPage() {
  const { productId } = useParams();
  const hasValidProductId = /^\d+$/.test(productId || "") && Number(productId) > 0;
  const navigate = useNavigate();
  const feedback = useFeedback();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(hasValidProductId);
  const [notFound, setNotFound] = useState(!hasValidProductId);

  useEffect(() => {
    if (!hasValidProductId) return;
    setLoading(true);
    setNotFound(false);
    adminApi.getProduct(productId)
      .then(setProduct)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [hasValidProductId, productId]);
  if (loading) return <Spinner />;
  if (notFound || !product) return <><PageHeader title="المنتج غير موجود" actions={<Button variant="ghost" onClick={() => navigate("/admin/products")}>رجوع إلى المنتجات</Button>} /><p style={card}>تحقق من رابط المنتج أو ارجع إلى قائمة المنتجات.</p></>;
  const stock = product.variants?.length ? product.variants.filter((v) => v.is_active).reduce((sum, v) => sum + v.stock_quantity, 0) : product.stock_quantity;

  return <>
    <PageHeader title={product.name} description={`SKU: ${product.sku || "—"}`} actions={<><Button variant="ghost" onClick={() => navigate("/admin/products")}>رجوع إلى المنتجات</Button><Button onClick={() => navigate(`/admin/products/${product.id}/edit`)}>تعديل المنتج</Button></>} />
    {feedback.node}
    <section style={{ ...card, ...sx`display:grid;grid-template-columns:120px minmax(0,1fr);gap:20px;margin-bottom:16px` }}>
      {product.primary_image_url ? <img src={product.primary_image_url} alt="" style={sx`width:120px;height:120px;object-fit:cover;border-radius:12px`} /> : <div style={sx`width:120px;height:120px;background:#F5EDE3;border-radius:12px`} />}
      <div style={sx`display:flex;flex-direction:column;gap:8px`}><h2 style={sx`margin:0`}>{product.name}</h2><div><Badge tone={product.is_active ? "good" : "bad"}>{product.is_active ? "فعّال" : "مخفي"}</Badge> <Badge>{product.product_type === "package" ? "باكيج" : "عادي"}</Badge></div>{product.short_description && <strong>{product.short_description}</strong>}</div>
    </section>
    <section style={{ ...card, ...sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:16px` }}>
      {[["رمز المنتج", product.sku], ["القسم", product.category_name], ["السعر", product.price], ["سعر قبل الخصم", product.compare_at_price], ["المخزون الفعلي", product.track_inventory ? stock : "غير متتبّع"], ["حد المخزون المنخفض", product.low_stock_threshold], ["عدد الصور", product.images?.length || 0]].map(([label, content]) => <div key={label}><small style={sx`display:block;color:#766669;margin-bottom:4px`}>{label}</small><strong>{show(content)}</strong></div>)}
    </section>
    {!!product.options?.length && <section style={card}><h2 style={sx`margin-top:0;font-size:16px`}>الخيارات والمتغيرات</h2>{product.options.map((option) => <p key={option.id}><b>{option.name}:</b> {option.values.map((item) => item.value).join("، ")}</p>)}{product.variants?.map((variant) => <div key={variant.id} style={sx`padding:8px 0;border-top:1px solid #F3EBE0`}>{variant.title} · SKU: {variant.sku || "—"} · المخزون: {variant.stock_quantity} · السعر: {variant.price_override ?? product.price}</div>)}</section>}
  </>;
}
