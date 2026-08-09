import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Modal } from "./Overlay.jsx";
import Media from "../shell/Media.jsx";
import QuantityStepper from "../cart/QuantityStepper.jsx";
import OptionPicker from "../product/OptionPicker.jsx";
import AddToCartButton from "../../AddToCartButton.jsx";
import { useProductDetail, useVariantSelection } from "../../../hooks/useProductDetail.js";
import { useMoney, useProductActions } from "../../../hooks/useStorefront.js";
import { productView } from "../../../utils/productView.js";
import { ArrowForward } from "../shell/icons.jsx";

/**
 * Quick view fetches the real product record — it never renders from the thin
 * catalogue row — so options, stock and gallery are the same ones the product
 * page would show.
 */
export default function QuickView({ slug, open, onClose }) {
  const { product, status } = useProductDetail(open ? slug : null);
  const money = useMoney();
  const { addProduct } = useProductActions();
  const [qty, setQty] = useState(1);
  const [image, setImage] = useState(0);
  const [error, setError] = useState("");
  const selection = useVariantSelection(product);

  useEffect(() => {
    setQty(1);
    setImage(0);
    setError("");
  }, [slug]);

  useEffect(() => setError(""), [selection.variantId]);

  const view = product ? productView(product, money) : null;
  const images = product?.images?.length ? product.images : [];
  const activeImage = images[image] || null;

  // Returns false when the add was refused, so the button does not announce a
  // success that did not happen.
  const add = () => {
    if (!product) return false;
    if (selection.missingChoice) {
      setError("اختر أحد الخيارات المتاحة قبل الإضافة إلى العربة.");
      return false;
    }
    // The modal is closing, so the cart takes over straight away rather than
    // leaving the visitor looking at nothing for half a second.
    addProduct(view, qty, selection.selected, { immediate: true });
  };

  return (
    <Modal open={open} onClose={onClose} label="نظرة سريعة">
      {status === "loading" && (
        <div className="vs-quick vs-quick--loading">
          <div className="vs-skel vs-quick__media" />
          <div className="vs-quick__info">
            <div className="vs-skel" style={{ height: 14, width: "35%" }} />
            <div className="vs-skel" style={{ height: 24, width: "80%" }} />
            <div className="vs-skel" style={{ height: 30, width: "45%" }} />
            <div className="vs-skel" style={{ height: 60 }} />
            <div className="vs-skel" style={{ height: 50 }} />
          </div>
        </div>
      )}

      {(status === "error" || status === "missing") && (
        <div className="vs-state vs-state--error vs-quick__state">
          <p className="vs-state__body">تعذّر تحميل هذا المنتج. جرّب فتح صفحته كاملة.</p>
        </div>
      )}

      {status === "ready" && view && (
        <div className="vs-quick">
          <div className="vs-quick__gallery">
            <Media
              className="vs-quick__media"
              ratio="1 / 1"
              src={activeImage?.url || view.imageUrl}
              fallback={view.bg}
              alt={view.name}
              eager
            />
            {images.length > 1 && (
              <div className="vs-quick__thumbs">
                {images.map((item, index) => (
                  <button
                    key={item.id ?? index}
                    type="button"
                    className="vs-thumb"
                    aria-pressed={index === image}
                    aria-label={`صورة ${index + 1}`}
                    onClick={() => setImage(index)}
                  >
                    <Media src={item.url} fallback={view.bg} alt="" ratio="1 / 1" />
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="vs-quick__info">
            {view.categoryName && <span className="vs-quick__cat">{view.categoryName}</span>}
            <h2 className="vs-quick__title">{view.name}</h2>

            <div className="vs-price">
              <span className="vs-price__now">{money(selection.price)}</span>
              {view.hasSale && <span className="vs-price__was">{view.oldText}</span>}
              {view.hasSale && <span className="vs-badge vs-badge--sale">{view.discountText}</span>}
            </div>

            <p className="vs-quick__stock" data-out={selection.soldOut}>
              {selection.soldOut
                ? "غير متوفر حالياً"
                : product.trackInventory && selection.stock < 5
                  ? `متبقٍ ${selection.stock} فقط`
                  : "متوفر في المخزون"}
            </p>

            {view.short && <p className="vs-quick__short">{view.short}</p>}

            {selection.requiresChoice && (
              <OptionPicker
                product={product}
                variants={selection.variants}
                variantId={selection.variantId}
                onPick={selection.setVariantId}
                error={error}
              />
            )}

            {selection.unavailable && (
              <p className="vs-quick__notice" role="status">
                هذا المنتج يحتاج إلى اختيار خيارات من صفحته الكاملة.
              </p>
            )}

            {view.isPackage && view.packageCount > 0 && (
              <ul className="vs-quick__contents">
                {view.packageItems.slice(0, 6).map((item) => (
                  <li key={item.id}>
                    {item.label}
                    {item.quantity > 1 ? ` ×${item.quantity}` : ""}
                  </li>
                ))}
              </ul>
            )}

            <div className="vs-quick__actions">
              <QuantityStepper
                value={qty}
                onDecrease={() => setQty((value) => Math.max(1, value - 1))}
                onIncrease={() => setQty((value) => value + 1)}
                size="lg"
              />
              {selection.unavailable ? (
                <Link to={view.href} className="vs-btn vs-btn--primary vs-btn--lg vs-quick__cta">
                  عرض صفحة المنتج
                </Link>
              ) : (
                <AddToCartButton
                  onAdd={add}
                  label={selection.soldOut ? "غير متوفر حالياً" : "أضف إلى العربة"}
                  disabled={selection.soldOut}
                  className="vs-btn vs-btn--primary vs-btn--lg vs-quick__cta"
                />
              )}
            </div>

            <Link to={view.href} className="vs-quick__full" onClick={onClose}>
              عرض التفاصيل الكاملة <ArrowForward size={15} />
            </Link>
          </div>
        </div>
      )}
    </Modal>
  );
}
