import { useLocale } from "../i18n/locale.jsx";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Link } from "../i18n/routing.jsx";
import { useStore } from "../app/StoreProvider.jsx";
import { useProductDetail, useVariantSelection } from "../hooks/useProductDetail.js";
import useMediaQuery from "../hooks/useMediaQuery.js";
import { useMoney, useProductActions } from "../hooks/useStorefront.js";
import { catalogService } from "../services/catalog.js";
import { productView } from "../utils/productView.js";
import AddToCartButton from "../components/AddToCartButton.jsx";
import Gallery from "../components/public/product/Gallery.jsx";
import OptionPicker from "../components/public/product/OptionPicker.jsx";
import QuantityStepper from "../components/public/cart/QuantityStepper.jsx";
import ProductGrid from "../components/public/catalog/ProductGrid.jsx";
import SectionHead from "../components/public/shell/SectionHead.jsx";
import Media from "../components/public/shell/Media.jsx";
import NotFoundRoutePage from "./NotFoundRoutePage.jsx";
import { BoxIcon } from "../components/public/shell/icons.jsx";
import useSeo, { absoluteUrl } from "../hooks/useSeo.js";

function paragraphsOf(text) {
  return String(text || "")
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export default function ProductDetailPage() {
  const { locale, t } = useLocale();
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
  const baseUrl = store.settings.publicBaseUrl;
  const productPath = `/product/${encodeURIComponent(slug || "")}`;
  const productJsonLd = product && baseUrl ? {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.seoDescription || product.short || product.description || undefined,
    image: (product.images.length ? product.images.map((image) => image.url) : [product.imageUrl])
      .map((image) => absoluteUrl(baseUrl, image))
      .filter(Boolean),
    offers: {
      "@type": "Offer",
      url: absoluteUrl(baseUrl, productPath),
      priceCurrency: store.settings.currencyCode,
      price: String(product.sale ?? product.price),
      availability: product.inStock
        ? "https://schema.org/InStock"
        : "https://schema.org/OutOfStock",
    },
  } : null;
  const breadcrumbs = product?.categorySlug && baseUrl ? {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: store.settings.storeName, item: baseUrl },
      { "@type": "ListItem", position: 2, name: product.categoryName, item: absoluteUrl(baseUrl, `/category/${encodeURIComponent(product.categorySlug)}`) },
      { "@type": "ListItem", position: 3, name: product.name, item: absoluteUrl(baseUrl, productPath) },
    ],
  } : null;
  useSeo({
    title: product ? (product.seoTitle || `${product.name} | ${store.settings.storeName}`) : store.settings.storeName,
    description: product ? (product.seoDescription || product.short || product.description) : "",
    baseUrl,
    path: productPath,
    image: product?.imageUrl,
    type: "product",
    noindex: status === "missing",
    jsonLd: productJsonLd ? [productJsonLd, breadcrumbs].filter(Boolean) : [],
  });

  useEffect(() => {
    setQty(1);
    setError("");
  }, [slug]);

  useEffect(() => setError(""), [selection.variantId, selection.selectedOptionValueIds.join("-")]);

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
  }, [status, product?.slug, locale]);

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
          <p className="vs-state__body">{t("تعذّر تحميل هذا المنتج. حاول مرة أخرى لاحقاً.")}</p>
        </div>
      </div>
    );
  }

  const view = productView(product, money);
  const description = paragraphsOf(product.description || product.short);

  // Returns false when the add was refused, so the button does not announce a
  // success that did not happen.
  const add = () => {
    if (selection.missingChoice) {
      setError(t("اختر أحد الخيارات المتاحة قبل الإضافة إلى العربة."));
      return false;
    }
    addProduct(view, qty, selection.selected);
    return true;
  };

  return (
    <>
      <div className="vs-container vs-pdp-crumbs">
        <nav className="vs-crumbs" aria-label={t("مسار التصفح")}>
          <Link to="/">{t("الرئيسية")}</Link>
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
          <Gallery
            key={selection.selectedPresentationValue?.id ?? "product"}
            images={selection.selectedPresentationValue?.images?.length ? selection.selectedPresentationValue.images : product.images}
            fallback={view.bg}
            alt={view.name}
          />

          <div className="vs-pdp__info">
            <div className="vs-pdp__badges">
              {view.isPackage && <span className="vs-badge vs-badge--package">{t("بكج")}</span>}
              {view.hasSale && <span className="vs-badge vs-badge--sale">{view.discountText}</span>}
              {view.isNew && <span className="vs-badge vs-badge--new">{t("جديد")}</span>}
            </div>

            <h1 className="vs-pdp__title">{view.name}</h1>
            <div className="vs-price vs-price--lg">
              <span className="vs-price__now">{money(selection.price * 1)}</span>
              {view.hasSale && <span className="vs-price__was">{view.oldText}</span>}
            </div>

            {selection.presentationOption ? (
              <h2 className="vs-pdp__headline">{selection.selectedPresentationValue?.presentation_title || selection.selectedPresentationValue?.value}</h2>
            ) : product.short && description[0] !== product.short ? (
              <h2 className="vs-pdp__headline">{product.short}</h2>
            ) : null}

            {selection.requiresChoice && (
              <OptionPicker
                product={product}
                variants={selection.variants}
                variantId={selection.variantId}
                onPick={selection.setVariantId}
                simpleChoices={selection.simpleChoices}
                onSimplePick={selection.setSimpleChoice}
                presentationValueId={selection.presentationValueId}
                onPresentationPick={selection.setPresentationValueId}
                error={error}
              />
            )}

            {selection.unavailable && (
              <p className="vs-pdp__notice" role="status">{t("هذا المنتج بحاجة إلى تحديد الخيارات مع فريق المتجر قبل الطلب.")}{" "}</p>
            )}

            {view.isPackage && product.packageItems.length > 0 && (
              <div className="vs-pkgbox">
                <h2 className="vs-pkgbox__title">
                  <BoxIcon size={17} />{" "}{t("محتويات البكج")}{" "}</h2>
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
                    ? t("غير متوفر حالياً")
                    : t("أضف إلى العربة — {0}", [money(selection.price * qty)])
                }
                disabled={selection.soldOut || selection.unavailable}
                className="vs-btn vs-btn--primary vs-btn--lg vs-pdp__cta"
              />
            </div>

            <section className="vs-pdp__description" aria-labelledby="product-description-title">
              <h2 id="product-description-title">{t("الوصف")}</h2>
              {description.length ? description.map((text, index) => (
                <p key={index} className="vs-prose">{t(text)}</p>
              )) : (
                <p className="vs-prose vs-prose--muted">{t("لا يتوفر وصف تفصيلي لهذا المنتج بعد.")}</p>
              )}
            </section>
          </div>
        </div>
      </div>

      {related.length > 0 && (
        <section className="vs-container vs-section">
          <SectionHead title={t("منتجات ذات صلة")} moreHref={view.categoryHref || "/shop"} />
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
          label={selection.soldOut ? t("غير متوفر") : t("أضف إلى العربة")}
          disabled={selection.soldOut || selection.unavailable}
          className="vs-btn vs-btn--primary vs-buybar__cta"
        />
      </div>
      )}
    </>
  );
}
