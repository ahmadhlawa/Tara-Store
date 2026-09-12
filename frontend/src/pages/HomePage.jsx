import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
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
  featured_products: {
    kind: "products",
    layout: "grid",
    source: "featured",
    fallbackTitle: "منتجات مختارة",
    more: "/shop",
    limit: 8,
  },
  new_products: {
    kind: "products",
    layout: "grid",
    source: "newest",
    fallbackTitle: "وصل حديثاً",
    more: "/shop?sort=newest",
    limit: 8,
  },
  bestsellers: {
    kind: "products",
    layout: "rail",
    source: "bestsellers",
    fallbackTitle: "الأكثر مبيعاً",
    more: "/shop",
    limit: 10,
  },
  packages: {
    kind: "products",
    layout: "packages",
    source: "packages",
    fallbackTitle: "باقات جاهزة",
    more: "/packages",
    limit: 6,
  },
  custom_text: { kind: "text", fallbackTitle: "" },
};

const LOADERS = {
  featured: (limit) => catalogService.featured(limit),
  newest: (limit) => catalogService.newest(limit),
  bestsellers: (limit) => catalogService.bestsellers(limit),
  packages: (limit) => catalogService.packages({ page_size: limit }),
};

function RevealSection({ className, children }) {
  const revealProps = useViewportReveal();
  return <section className={className} {...revealProps}>{children}</section>;
}

export default function HomePage() {
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
  const [lists, setLists] = useState({});
  const [showcases, setShowcases] = useState({});
  const homeCategories = useMemo(
    () => categories.filter((category) => category.showOnHome),
    [categories],
  );

  // Sections first: only the product lists an enabled section actually needs are
  // fetched, so a store with three sections makes three requests, not six.
  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([storefrontService.heroSlides(), storefrontService.homeSections()]).then(
      ([heroResult, sectionResult]) => {
        if (cancelled) return;
        setHero({
          slides: heroResult.status === "fulfilled" ? heroResult.value : [],
          status: heroResult.status === "fulfilled" ? "ready" : "error",
        });
        setSections({
          list: sectionResult.status === "fulfilled" ? sectionResult.value.sections : [],
          status: sectionResult.status === "fulfilled" ? "ready" : "error",
        });
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const needed = useMemo(() => {
    const wanted = new Map();
    sections.list.forEach((section) => {
      const spec = SECTIONS[section.type];
      if (spec?.kind === "products") {
        wanted.set(spec.source, Math.max(wanted.get(spec.source) || 0, spec.limit));
      }
    });
    return [...wanted.entries()];
  }, [sections.list]);

  useEffect(() => {
    if (!needed.length) return undefined;
    let cancelled = false;
    needed.forEach(([source, limit]) => {
      setLists((current) =>
        current[source] ? current : { ...current, [source]: { items: [], status: "loading" } },
      );
      LOADERS[source](limit)
        .then((result) => {
          if (cancelled) return;
          setLists((current) => ({
            ...current,
            [source]: { items: result.items, status: "ready" },
          }));
        })
        .catch(() => {
          // One failed list must not take the homepage with it.
          if (cancelled) return;
          setLists((current) => ({ ...current, [source]: { items: [], status: "error" } }));
        });
    });
    return () => {
      cancelled = true;
    };
  }, [needed]);

  useEffect(() => {
    let cancelled = false;
    setShowcases((current) => {
      const next = {};
      homeCategories.forEach((category) => {
        next[category.slug] = current[category.slug] || { items: [], status: "loading" };
      });
      return next;
    });
    homeCategories.forEach((category) => {
      catalogService
        .list({ category: category.slug, sort: "featured", page_size: 4 })
        .then((result) => {
          if (cancelled) return;
          setShowcases((current) => ({
            ...current,
            [category.slug]: { items: result.items, status: "ready" },
          }));
        })
        .catch(() => {
          if (cancelled) return;
          setShowcases((current) => ({
            ...current,
            [category.slug]: { items: [], status: "error" },
          }));
        });
    });
    return () => {
      cancelled = true;
    };
  }, [homeCategories]);

  const views = (source) =>
    (lists[source]?.items || []).map((product) => productView(product, money));

  const rendered = sections.list
    .map((section) => {
      const spec = SECTIONS[section.type];
      if (!spec) return null;
      const title = section.title || spec.fallbackTitle;

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
              <Link to="/shop" className="vs-btn vs-btn--lg vs-split__cta">
                تصفّح المتجر <ArrowForward size={16} />
              </Link>
            </div>
          </RevealSection>
        );
      }

      const list = lists[spec.source];
      if (!list || list.status === "error") return null;

      if (list.status === "loading") {
        return (
          <RevealSection key={section.id} className="vs-container vs-section">
            <SectionHead title={title} description={section.description} />
            <GridSkeleton count={spec.layout === "packages" ? 3 : 4} />
          </RevealSection>
        );
      }

      const items = views(spec.source).slice(0, spec.limit);
      // A section with nothing in it, or a lone card stranded in a wide row, is
      // worse than no section at all.
      if (items.length < 2) return null;

      if (spec.layout === "split") {
        return (
          <RevealSection key={section.id} className="vs-container vs-section">
            <div className="vs-split">
              <div className="vs-split__panel">
                <h2 className="vs-split__title">{title}</h2>
                {section.description && <p className="vs-split__desc">{section.description}</p>}
                <Link to={spec.more} className="vs-btn vs-btn--lg vs-split__cta">
                  عرض الكل <ArrowForward size={16} />
                </Link>
              </div>
              <div className="vs-split__grid">
                <ProductGrid views={items.slice(0, 4)} variant="plain" eagerCount={0} />
              </div>
            </div>
          </RevealSection>
        );
      }

      return (
        <section key={section.id} className="vs-container vs-section">
          <SectionHead
            title={title}
            description={section.description}
            moreHref={spec.more}
          />
          <ProductGrid views={items} variant={spec.layout} eagerCount={0} />
        </section>
      );
    })
    .filter(Boolean);

  const renderedShowcases = homeCategories.map((category) => {
    const showcase = showcases[category.slug];
    if (!showcase || showcase.status === "loading") {
      return (
        <RevealSection key={category.slug} className="vs-container vs-section">
          <div className="vs-home-showcase">
            <div className="vs-skel vs-home-showcase__category" />
            <div className="vs-home-showcase__content">
              <SectionHead title={category.name} moreHref={category.href} />
              <GridSkeleton count={3} />
            </div>
          </div>
        </RevealSection>
      );
    }
    if (showcase.status === "error" || !showcase.items.length) return null;
    const categoryViews = showcase.items.map((product) => productView(product, money));
    return (
      <RevealSection key={category.slug} className="vs-container vs-section">
        <div className="vs-home-showcase">
          <div className="vs-home-showcase__category">
            <CategoryCard category={category} />
          </div>
          <div className="vs-home-showcase__content">
            <SectionHead title={category.name} moreHref={category.href} />
            <div className="vs-home-showcase__products">
              <ProductGrid views={categoryViews} variant="plain" eagerCount={0} />
            </div>
          </div>
        </div>
      </RevealSection>
    );
  }).filter(Boolean);

  // Before the catalog arrives there is no hero and every section drops out, which
  // would leave the header sitting straight on top of the trust strip. Say so
  // instead: the store is real and reachable, it just has nothing to show yet.
  const stillLoading =
    hero.status === "loading" ||
    sections.status === "loading" ||
    needed.some(([source]) => (lists[source]?.status ?? "loading") === "loading") ||
    homeCategories.some((category) => (showcases[category.slug]?.status ?? "loading") === "loading");
  // Categories are checked too: a store that has a catalog but no configured home
  // sections is not "being prepared", it is merely unarranged, and telling its
  // customers otherwise would be the misleading version of this message.
  const nothingToShow =
    !stillLoading && !hero.slides.length && !rendered.length && !renderedShowcases.length && !categories.length;

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

      {renderedShowcases}

      {nothingToShow && (
        <RevealSection className="vs-container vs-section">
          <div className="vs-state">
            <h2 className="vs-state__title">المتجر قيد التجهيز</h2>
            <p className="vs-state__body">
              نعمل على إضافة المنتجات، وسيظهر المعروض هنا فور توفره. يسعدنا تواصلكم معنا في
              أي وقت.
            </p>
            <Link to="/contact" className="vs-btn vs-btn--primary vs-btn--lg">
              تواصل معنا
            </Link>
          </div>
        </RevealSection>
      )}

      <section className="vs-container vs-section--tight">
        <TrustStrip />
      </section>
    </div>
  );
}
