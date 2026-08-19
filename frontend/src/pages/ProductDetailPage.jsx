import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useStore } from "../app/StoreProvider.jsx";
import { useProductDetail, useVariantSelection } from "../hooks/useProductDetail.js";
import useMediaQuery from "../hooks/useMediaQuery.js";
import { useMoney, useProductActions } from "../hooks/useStorefront.js";
import { catalogService } from "../services/catalog.js";
import { productView } from "../utils/productView.js";
import AddToCartButton from "../components/AddToCartButton.jsx";
import Gallery from "../components/public/product/Gallery.jsx";
import OptionPicker from "../components/public/product/OptionPicker.jsx";
import ProductPanels from "../components/public/product/ProductPanels.jsx";
import QuantityStepper from "../components/public/cart/QuantityStepper.jsx";
import ProductGrid from "../components/public/catalog/ProductGrid.jsx";
import SectionHead from "../components/public/shell/SectionHead.jsx";
import Media from "../components/public/shell/Media.jsx";
import NotFoundRoutePage from "./NotFoundRoutePage.jsx";
import { BoxIcon, TruckIcon, WalletIcon } from "../components/public/shell/icons.jsx";

function paragraphsOf(text) {
  return String(text || "")
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export default function ProductDetailPage() {
  const { slug } = useParams();
  const store = useStore();
  const money = useMoney();
  const { addProduct } = useProductActions();
  const { product, status } = useProductDetail(slug);
  const selection = useVariantSelection(product);
  // The sticky buy bar is a phone affordance; rendering it on desktop would only
  // duplicate the price and the button in the accessibility tree.
  const compact = useMediaQuery("(max-width: 899px)");

  const [qty, setQty] = useState(1);
  const [related, setRelated] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    setQty(1);
    setError("");
  }, [slug]);

  useEffect(() => setError(""), [selection.variantId]);

  useEffect(() => {
    if (status !== "ready" || !product) return undefined;
    let cancelled = false;
    store.rememberViewed(product.slug);
    catalogService
      .related(product.slug, 4)
      .then((rows) => !cancelled && setRelated(rows))
      .catch(() => !cancelled && setRelated([]));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, product?.slug]);

  if (status === "loading") {
    return (
      <div className="vs-container vs-section">
        <div className="vs-pdp">
          <div className="vs-skel" style={{ aspectRatio: "1 / 1", borderRadius: 16 }} />
          <div className="vs-pdp__info">
            <div className="vs-skel" style={{ height: 14, width: "30%" }} />
            <div className="vs-skel" style={{ height: 30, width: "80%" }} />
            <div className="vs-skel" style={{ height: 34, width: "45%" }} />
            <div className="vs-skel" style={{ height: 90 }} />
            <div className="vs-skel" style={{ height: 54 }} />
          </div>
        </div>
      </div>
    );
  }

  if (status === "missing") return <NotFoundRoutePage />;

  if (status === "error" || !product) {
    return (
      <div className="vs-container vs-section">
        <div className="vs-state vs-state--error" role="alert">
          <p className="vs-state__body">تعذّر تحميل هذا المنتج. حاول مرة أخرى لاحقاً.</p>
        </div>
      </div>
    );
  }

  const view = productView(product, money);
  const specs = product.specs || [];
  const description = paragraphsOf(product.description || product.short);

  // Returns false when the add was refused, so the button does not announce a
  // success that did not happen.
  const add = () => {
    if (selection.missingChoice) {
      setError("اختر أحد الخيارات المتاحة قبل الإضافة إلى العربة.");
      return false;
    }
    addProduct(view, qty, selection.selected);
    return true;
  };

  const panels = [
    {
      key: "desc",
      label: "الوصف",
      content: description.length ? (
        description.map((text, index) => (
          <p key={index} className="vs-prose">
            {text}
          </p>
        ))
      ) : (
        <p className="vs-prose vs-prose--muted">لا يتوفر وصف تفصيلي لهذا المنتج بعد.</p>
      ),
    },
    {
      key: "specs",
      label: "المواصفات",
      content: specs.length ? (
        <dl className="vs-specs">
          {specs.map(([name, value]) => (
            <div className="vs-specs__row" key={name}>
              <dt>{name}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="vs-prose vs-prose--muted">لا تتوفر مواصفات إضافية لهذا المنتج.</p>
      ),
    },
    {
      key: "delivery",
      label: "التوصيل والدفع",
      content: (
        <ul className="vs-bullets">
          <li>الدفع عند الاستلام نقداً للمندوب عند التسليم.</li>
          <li>لا يطلب المتجر بيانات بطاقات بنكية في أي مرحلة.</li>
          <li>تُحتسب رسوم التوصيل حسب المنطقة في صفحة إتمام الطلب.</li>
          <li>
            راجع <Link to="/page/return-policy">سياسة التبديل والإرجاع</Link> قبل الطلب.
          </li>
        </ul>
      ),
    },
  ];

  return (
    <>
      <div className="vs-container vs-pdp-crumbs">
        <nav className="vs-crumbs" aria-label="مسار التصفح">
          <Link to="/">الرئيسية</Link>
          <span aria-hidden="true">›</span>
          {view.categoryHref ? (
            <>
              <Link to={view.categoryHref}>{view.categoryName}</Link>
              <span aria-hidden="true">›</span>
            </>
          ) : null}
          <span className="vs-crumbs__here">{view.name}</span>
        </nav>
      </div>

      <div className="vs-container">
        <div className="vs-pdp">
          <Gallery images={product.images} fallback={view.bg} alt={view.name} />

          <div className="vs-pdp__info">
            <div className="vs-pdp__badges">
              {view.isPackage && <span className="vs-badge vs-badge--package">بكج</span>}
              {view.hasSale && <span className="vs-badge vs-badge--sale">{view.discountText}</span>}
              {view.isNew && <span className="vs-badge vs-badge--new">جديد</span>}
            </div>

            <h1 className="vs-pdp__title">{view.name}</h1>
            {product.sku && <span className="vs-pdp__sku">رمز المنتج: {product.sku}</span>}

            <div className="vs-price vs-price--lg">
              <span className="vs-price__now">{money(selection.price * 1)}</span>
              {view.hasSale && <span className="vs-price__was">{view.oldText}</span>}
            </div>

            <p className="vs-pdp__stock" data-tone={selection.soldOut ? "out" : selection.stock < 5 && product.trackInventory ? "low" : "ok"}>
              {selection.soldOut
                ? "غير متوفر حالياً"
                : !product.trackInventory
                  ? "متوفر"
                  : selection.stock < 5
                    ? `متبقٍ ${selection.stock} فقط`
                    : "متوفر في المخزون"}
            </p>

            {product.short && description[0] !== product.short && (
              <p className="vs-pdp__short">{product.short}</p>
            )}

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
              <p className="vs-pdp__notice" role="status">
                هذا المنتج بحاجة إلى تحديد الخيارات مع فريق المتجر قبل الطلب.
              </p>
            )}

            {view.isPackage && product.packageItems.length > 0 && (
              <div className="vs-pkgbox">
                <h2 className="vs-pkgbox__title">
                  <BoxIcon size={17} /> محتويات البكج
                </h2>
                <ul>
                  {product.packageItems.map((item) => (
                    <li key={item.id}>
                      {item.slug ? (
                        <Link to={`/product/${item.slug}`}>{item.label}</Link>
                      ) : (
                        item.label
                      )}
                      {item.quantity > 1 ? ` ×${item.quantity}` : ""}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="vs-pdp__buy">
              <QuantityStepper
                value={qty}
                onDecrease={() => setQty((value) => Math.max(1, value - 1))}
                onIncrease={() => setQty((value) => value + 1)}
                size="lg"
              />
              <AddToCartButton
                onAdd={add}
                label={
                  selection.soldOut
                    ? "غير متوفر حالياً"
                    : `أضف إلى العربة — ${money(selection.price * qty)}`
                }
                disabled={selection.soldOut || selection.unavailable}
                className="vs-btn vs-btn--primary vs-btn--lg vs-pdp__cta"
              />
            </div>

            <ul className="vs-pdp__assurance">
              <li>
                <WalletIcon size={17} /> الدفع عند الاستلام
              </li>
              <li>
                <TruckIcon size={17} /> رسوم التوصيل تُحسب حسب المنطقة
              </li>
            </ul>
          </div>

          {/* Inside the product grid rather than under it: on desktop the panels
              fill the column beside the gallery instead of leaving it blank. */}
          <section className="vs-pdp__panels">
            <ProductPanels panels={panels} />
          </section>
        </div>
      </div>

      {related.length > 0 && (
        <section className="vs-container vs-section">
          <SectionHead title="منتجات ذات صلة" moreHref={view.categoryHref || "/shop"} />
          <ProductGrid
            views={related.map((item) => productView(item, money))}
            eagerCount={0}
          />
        </section>
      )}

      {compact && (
      <div className="vs-buybar">
        <div className="vs-buybar__media">
          <Media src={view.imageUrl} fallback={view.bg} alt="" ratio="1 / 1" />
        </div>
        <div className="vs-buybar__text">
          <span className="vs-buybar__name">{view.name}</span>
          <span className="vs-buybar__price">{money(selection.price * qty)}</span>
        </div>
        <AddToCartButton
          onAdd={add}
          label={selection.soldOut ? "غير متوفر" : "أضف إلى العربة"}
          disabled={selection.soldOut || selection.unavailable}
          className="vs-btn vs-btn--primary vs-buybar__cta"
        />
      </div>
      )}
    </>
  );
}
