import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { OVERLAY, useStore } from "../app/StoreProvider.jsx";
import { useCatalogQuery, SORTS } from "../hooks/useCatalogQuery.js";
import { useCategoryNav, useMoney } from "../hooks/useStorefront.js";
import { catalogService } from "../services/catalog.js";
import { productView } from "../utils/productView.js";
import ProductGrid, { GridSkeleton } from "../components/public/catalog/ProductGrid.jsx";
import FilterPanel from "../components/public/catalog/FilterPanel.jsx";
import Media from "../components/public/shell/Media.jsx";
import { Drawer } from "../components/public/overlays/Overlay.jsx";
import {
  FilterIcon,
  GridDenseIcon,
  GridIcon,
  SearchIcon,
} from "../components/public/shell/icons.jsx";

const PAGE_SIZE = 12;

const MODES = {
  shop: { title: "كل المنتجات", subtitle: "تصفّح كل ما يوفّره المتجر", filterCategories: true },
  category: { title: "القسم", filterCategories: false },
  offers: {
    title: "العروض",
    subtitle: "منتجات مختارة بأسعار مخفّضة",
    filterCategories: true,
    force: { on_sale: true },
  },
  packages: {
    title: "البكجات",
    subtitle: "باقات جاهزة تجمع أكثر من منتج في طلب واحد",
    filterCategories: false,
    force: { product_type: "package" },
  },
  molds: {
    title: "قوالب سيليكون",
    subtitle: "قوالب للريزن والشمع",
    filterCategories: false,
    force: { product_type: "silicone_mold" },
  },
  search: { title: "نتائج البحث", filterCategories: true },
};

const DENSITIES = [
  { value: "comfortable", label: "عرض واسع", Icon: GridIcon },
  { value: "standard", label: "عرض قياسي", Icon: GridDenseIcon },
];

/**
 * One catalogue template behind /shop, /category/:slug, /offers, /packages,
 * /molds and /search. The mode fixes the parts of the query the visitor cannot
 * change; everything else comes from the URL.
 */
export default function CatalogPage({ mode = "shop" }) {
  const spec = MODES[mode];
  const params = useParams();
  const [search] = useSearchParams();
  const store = useStore();
  const money = useMoney();
  const categories = useCategoryNav(mode === "category" ? params.slug : null);
  const { filters, patch, reset, active } = useCatalogQuery();

  const term = search.get("q") || "";
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState({ total: 0, pages: 0 });
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("loading");
  const [category, setCategory] = useState(null);
  const [ceiling, setCeiling] = useState(500);
  const [density, setDensity] = useState("standard");
  const firstLoad = useRef(true);

  const baseQuery = useMemo(() => {
    const query = { ...(spec.force || {}) };
    if (mode === "category") query.category = params.slug;
    else if (filters.category) query.category = filters.category;
    if (mode === "search" && term) query.q = term;
    if (filters.onSale) query.on_sale = true;
    if (filters.inStock) query.in_stock = true;
    if (filters.minPrice != null) query.min_price = filters.minPrice;
    if (filters.maxPrice != null) query.max_price = filters.maxPrice;
    query.sort = filters.sort;
    return query;
  }, [spec.force, mode, params.slug, filters, term]);

  const queryKey = JSON.stringify(baseQuery);

  useEffect(() => {
    setPage(1);
    firstLoad.current = true;
  }, [queryKey]);

  useEffect(() => {
    let cancelled = false;
    // Nothing to ask the API for until the visitor has typed something.
    if (mode === "search" && !term) {
      setItems([]);
      setMeta({ total: 0, pages: 0 });
      setStatus("ready");
      return undefined;
    }
    if (firstLoad.current) setStatus("loading");
    catalogService
      .list({ ...baseQuery, page, page_size: PAGE_SIZE })
      .then((result) => {
        if (cancelled) return;
        setItems((current) => (page === 1 ? result.items : [...current, ...result.items]));
        setMeta({ total: result.total, pages: result.pages });
        setStatus("ready");
        firstLoad.current = false;
      })
      .catch(() => {
        if (cancelled) return;
        if (page === 1) setItems([]);
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
    // `queryKey` stands in for the whole query object.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryKey, page]);

  // The price slider needs a real upper bound, so it comes from the catalogue
  // itself rather than from a number invented in the UI.
  useEffect(() => {
    let cancelled = false;
    const scope = { ...(spec.force || {}) };
    if (mode === "category") scope.category = params.slug;
    if (mode === "search" && term) scope.q = term;
    catalogService
      .list({ ...scope, sort: "price-desc", page_size: 1 })
      .then((result) => {
        if (cancelled || !result.items.length) return;
        const top = result.items[0].sale ?? result.items[0].price;
        setCeiling(Math.max(50, Math.ceil(top / 50) * 50));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [mode, params.slug, term, spec.force]);

  useEffect(() => {
    let cancelled = false;
    if (mode !== "category") {
      setCategory(null);
      return undefined;
    }
    catalogService
      .category(params.slug)
      .then((value) => !cancelled && setCategory(value))
      .catch(() => !cancelled && setCategory(null));
    return () => {
      cancelled = true;
    };
  }, [mode, params.slug]);

  const views = items.map((product) => productView(product, money));
  const title = mode === "category" ? category?.name || "القسم" : spec.title;
  const subtitle =
    mode === "category"
      ? category?.description || ""
      : mode === "search"
        ? term
          ? `نتائج البحث عن «${term}»`
          : "اكتب كلمة في شريط البحث للبدء"
        : spec.subtitle;

  const children = mode === "category" ? categories.find((c) => c.slug === params.slug)?.children || [] : [];
  const hasImage = mode === "category" && !!category?.imageUrl;
  // An empty search box is a prompt, not a result set: listing the whole
  // catalogue under "search results" would be a lie about what was searched.
  const awaitingTerm = mode === "search" && !term;
  const empty = status === "ready" && items.length === 0;

  const filterPanel = (
    <FilterPanel
      filters={filters}
      patch={patch}
      reset={reset}
      showCategories={spec.filterCategories}
      ceiling={ceiling}
    />
  );

  return (
    <>
      <header className={`vs-cathead ${hasImage ? "vs-cathead--image" : "vs-cathead--plain"}`}>
        {hasImage && (
          <>
            <Media
              className="vs-cathead__media"
              src={category.imageUrl}
              fallback={category.bg}
              alt=""
              eager
            />
            <span className="vs-cathead__veil" />
          </>
        )}
        <div className="vs-container vs-cathead__inner">
          <nav className="vs-crumbs" aria-label="مسار التصفح">
            <Link to="/">الرئيسية</Link>
            <span aria-hidden="true">›</span>
            <span className="vs-crumbs__here">{title}</span>
          </nav>
          <h1 className="vs-cathead__title">{title}</h1>
          {subtitle && <p className="vs-cathead__desc">{subtitle}</p>}
          {children.length > 0 && (
            <div className="vs-cathead__subs">
              {children.map((child) => (
                <Link key={child.slug} to={child.href} className="vs-chip">
                  {child.name}
                </Link>
              ))}
            </div>
          )}
        </div>
      </header>

      {awaitingTerm ? (
        <div className="vs-container vs-section">
          <div className="vs-state">
            <span className="vs-state__icon">
              <SearchIcon size={26} />
            </span>
            <h2 className="vs-state__title">ابدأ بالبحث</h2>
            <p className="vs-state__body">
              اكتب اسم منتج أو قسم في شريط البحث أعلى الصفحة لعرض النتائج.
            </p>
            <Link to="/shop" className="vs-btn vs-btn--primary">
              أو تصفّح كل المنتجات
            </Link>
          </div>
        </div>
      ) : (
      <div className="vs-container vs-section--tight">
        <div className="vs-catalog">
          <aside className="vs-catalog__side" aria-label="تصفية النتائج">
            {filterPanel}
          </aside>

          <div className="vs-catalog__main" data-density={density}>
            <div className="vs-toolbar">
              <button
                type="button"
                className="vs-btn vs-btn--ghost vs-toolbar__filter"
                onClick={() => store.openOverlay(OVERLAY.FILTERS)}
              >
                <FilterIcon size={17} /> التصفية
              </button>
              <span className="vs-toolbar__count">
                {status === "loading" ? "جارٍ التحميل…" : `${meta.total} منتجاً`}
              </span>

              <div className="vs-toolbar__spacer" />

              <div className="vs-toolbar__density vs-desk" role="group" aria-label="كثافة العرض">
                {DENSITIES.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    aria-pressed={density === item.value}
                    aria-label={item.label}
                    onClick={() => setDensity(item.value)}
                  >
                    <item.Icon size={17} />
                  </button>
                ))}
              </div>

              <label className="vs-sortlabel">
                ترتيب حسب
                <select
                  className="vs-select"
                  value={filters.sort}
                  onChange={(event) => patch({ sort: event.target.value })}
                >
                  {SORTS.map((sort) => (
                    <option key={sort.value} value={sort.value}>
                      {sort.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {active.length > 0 && (
              <div className="vs-activefilters">
                {active.map((chip) => (
                  <button
                    key={chip.key}
                    type="button"
                    className="vs-chip vs-chip--active"
                    onClick={() => patch(chip.clear)}
                  >
                    {chip.label} ✕
                  </button>
                ))}
                <button type="button" className="vs-activefilters__clear" onClick={reset}>
                  مسح الكل
                </button>
              </div>
            )}

            {status === "loading" && <GridSkeleton count={8} />}

            {status === "error" && (
              <div className="vs-state vs-state--error" role="alert">
                <p className="vs-state__body">تعذّر تحميل المنتجات. حاول مرة أخرى بعد قليل.</p>
              </div>
            )}

            {empty && (
              <div className="vs-state">
                <span className="vs-state__icon">
                  <SearchIcon size={26} />
                </span>
                <h2 className="vs-state__title">لا توجد منتجات مطابقة</h2>
                <p className="vs-state__body">
                  جرّب توسيع نطاق السعر أو إلغاء بعض عوامل التصفية.
                </p>
                {active.length > 0 && (
                  <button type="button" className="vs-btn vs-btn--primary" onClick={reset}>
                    إعادة تعيين التصفية
                  </button>
                )}
              </div>
            )}

            {views.length > 0 && <ProductGrid views={views} />}

            {page < meta.pages && (
              <button
                type="button"
                className="vs-btn vs-btn--outline vs-btn--lg vs-loadmore"
                onClick={() => setPage((current) => current + 1)}
              >
                عرض المزيد ({Math.max(0, meta.total - items.length)})
              </button>
            )}
          </div>
        </div>
      </div>
      )}

      <Drawer
        open={store.overlay === OVERLAY.FILTERS}
        onClose={store.closeAll}
        side="right"
        label="تصفية النتائج"
        title="تصفية النتائج"
        footer={
          <button
            type="button"
            className="vs-btn vs-btn--primary vs-btn--lg vs-btn--block"
            onClick={store.closeAll}
          >
            عرض {meta.total} منتجاً
          </button>
        }
      >
        <div className="vs-filterdrawer">{filterPanel}</div>
      </Drawer>
    </>
  );
}
