import { useLocale } from "../i18n/locale.jsx";
import { useEffect, useState } from "react";
import { Link } from "../i18n/routing.jsx";
import { useStore } from "../app/StoreProvider.jsx";
import { useCategoryNav, useMoney } from "../hooks/useStorefront.js";
import { catalogService } from "../services/catalog.js";
import { storefrontService } from "../services/storefront.js";
import { productView } from "../utils/productView.js";
import Hero from "../components/public/home/Hero.jsx";
import TrustStrip from "../components/public/home/TrustStrip.jsx";
import SectionHead from "../components/public/shell/SectionHead.jsx";
import CategoryCard from "../components/public/catalog/CategoryCard.jsx";
import ProductGrid, { GridSkeleton } from "../components/public/catalog/ProductGrid.jsx";
import { ArrowForward } from "../components/public/shell/icons.jsx";
import { useViewportReveal } from "../hooks/useViewportReveal.js";
import useSeo, { absoluteUrl } from "../hooks/useSeo.js";
import { STORE_ROUTES } from "../utils/storeRoutes.js";

/**
 * Each admin-managed section type is rendered by exactly one composition, and
 * every composition is different — a grid, a rail, a package grid, or a
 * split editorial block — so the page has rhythm instead of eight identical rows.
 */
const SECTIONS = {
  categories: { kind: "categories", fallbackTitle: "تسوّق حسب القسم", more: STORE_ROUTES.categories },
  custom_text: { kind: "text", fallbackTitle: "" },
};

function RevealSection({ className, children }) {

  const revealProps = useViewportReveal();
  return <section className={className} {...revealProps}>{children}</section>;
}

export default function HomePage() {
  const { locale, t } = useLocale();
  const store = useStore();
  const money = useMoney();
  const categories = useCategoryNav();
  const { settings } = store;
  const organization = settings.publicBaseUrl ? {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: settings.storeName,
    url: settings.publicBaseUrl,
    ...(settings.logoUrl ? { logo: absoluteUrl(settings.publicBaseUrl, settings.logoUrl) } : {}),
    ...(settings.phone ? { telephone: settings.phone } : {}),
    ...(settings.email ? { email: settings.email } : {}),
  } : null;
  const website = settings.publicBaseUrl ? {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: settings.storeName,
    url: settings.publicBaseUrl,
  } : null;
  useSeo({
    title: settings.seoTitle || settings.storeName,
    description: settings.seoDescription || settings.tagline,
    baseUrl: settings.publicBaseUrl,
    path: "/",
    image: settings.logoUrl,
    jsonLd: [organization, website].filter(Boolean),
  });

  const [hero, setHero] = useState({ slides: [], status: "loading" });
  const [sections, setSections] = useState({ list: [], status: "loading" });
  const [showcases, setShowcases] = useState({ byCategory: {}, status: "loading" });
  useEffect(() => {
    let cancelled = false;
    storefrontService.heroSlides().then(
      slides => { if (!cancelled) setHero({ slides, status: "ready" }); },
      () => { if (!cancelled) setHero({ slides: [], status: "error" }); },
    );
    storefrontService.homeSections().then(
      result => { if (!cancelled) setSections({ list: result.sections, status: "ready" }); },
      () => { if (!cancelled) setSections({ list: [], status: "error" }); },
    );
    catalogService.homeShowcases().then(
      byCategory => { if (!cancelled) setShowcases({ byCategory, status: "ready" }); },
      () => { if (!cancelled) setShowcases({ byCategory: {}, status: "error" }); },
    );
    return () => {
      cancelled = true;
    };
  }, [locale]);

  const rendered = sections.list
    .map((section) => {
      const spec = SECTIONS[section.type];
      if (!spec) return null;
      const title = section.title || t(spec.fallbackTitle);

      if (spec.kind === "categories") {
        if (!categories.length) return null;
        const limit = section.config?.limit || 8;
        return (
          <section key={section.id} className="vs-container vs-section">
            <SectionHead
              eyebrow={section.description || null}
              title={title}
              moreHref={spec.more}
            />
            <div className="vs-grid vs-grid--cats">
              {categories.slice(0, limit).map((category, index) => (
                <CategoryCard key={category.slug} category={category} eager={index < 4} revealDelay={Math.min(index * 70, 280)} />
              ))}
            </div>
          </section>
        );
      }

      if (spec.kind === "text") {
        if (!section.title && !section.description) return null;
        return (
          <RevealSection key={section.id} className="vs-container vs-section">
            <div className="vs-split__panel">
              <h2 className="vs-split__title">{section.title}</h2>
              {section.description && <p className="vs-split__desc">{section.description}</p>}
              <Link to="/shop" className="vs-btn vs-btn--lg vs-split__cta">{t("تصفّح المتجر")}{" "}<ArrowForward size={16} />
              </Link>
            </div>
          </RevealSection>
        );
      }

      return null;
    })
    .filter(Boolean);

  const showcaseSections = categories
    .filter(category => category.parentId == null && category.showOnHome)
    .map(category => ({ category, products: showcases.byCategory[category.id] || [] }))
    .filter(({ products }) => products.length)
    .map(({ category, products }) => (
      <section key={category.id} className="vs-container vs-section">
        <SectionHead title={category.name} moreHref={`/category/${category.slug}`} />
        <ProductGrid
          views={products.map(product => productView(product, money))}
          variant="grid"
          eagerCount={0}
        />
      </section>
    ));

  // Before the catalog arrives there is no hero and every section drops out, which
  // would leave the header sitting straight on top of the trust strip. Say so
  // instead: the store is real and reachable, it just has nothing to show yet.
  const stillLoading =
    hero.status === "loading" ||
    sections.status === "loading" ||
    showcases.status === "loading";
  // Categories are checked too: a store that has a catalog but no configured home
  // sections is not "being prepared", it is merely unarranged, and telling its
  // customers otherwise would be the misleading version of this message.
  const nothingToShow =
    !stillLoading && !hero.slides.length && !rendered.length && !showcaseSections.length && !categories.length;

  return (
    <div className="vs-home">
      {/* Deliberately outside `.vs-container`: the advertising band runs the full
          storefront width, stopping only where the category rail's gutter
          begins. Every section below it stays inside the container. */}
      <div className="vs-herorow">
        {hero.status === "loading" ? (
          <div className="vs-skel vs-hero--skel" />
        ) : (
          <Hero slides={hero.slides} />
        )}
      </div>

      {sections.status === "loading" && (
        <RevealSection className="vs-container vs-section">
          <GridSkeleton count={4} />
        </RevealSection>
      )}

      {rendered}

      {showcaseSections}

      {nothingToShow && (
        <RevealSection className="vs-container vs-section">
          <div className="vs-state">
            <h2 className="vs-state__title">{t("المتجر قيد التجهيز")}</h2>
            <p className="vs-state__body">{t("نعمل على إضافة المنتجات، وسيظهر المعروض هنا فور توفره. يسعدنا تواصلكم معنا في أي وقت.")}{" "}</p>
            <Link to="/contact" className="vs-btn vs-btn--primary vs-btn--lg">{t("تواصل معنا")}{" "}</Link>
          </div>
        </RevealSection>
      )}

      <section className="vs-container vs-section--tight">
        <TrustStrip />
      </section>
    </div>
  );
}
