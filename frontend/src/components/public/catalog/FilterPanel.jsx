import { useCategoryNav, useMoney } from "../../../hooks/useStorefront.js";

/**
 * Every control here maps onto a query parameter the products endpoint really
 * supports. Nothing decorative: a filter that cannot change the result set does
 * not belong on the page.
 */
export default function FilterPanel({ filters, patch, reset, showCategories, ceiling }) {
  const categories = useCategoryNav();
  const money = useMoney();
  const max = filters.maxPrice ?? ceiling;

  return (
    <div className="vs-filters">
      <div className="vs-filters__group">
        <div className="vs-filters__legend-row">
          <span className="vs-filters__legend">تصفية النتائج</span>
          <button type="button" className="vs-activefilters__clear" onClick={reset}>
            إعادة تعيين
          </button>
        </div>
      </div>

      {showCategories && categories.length > 0 && (
        <fieldset className="vs-filters__group">
          <legend className="vs-filters__legend">الأقسام</legend>
          {categories.map((category) => (
            <label key={category.slug} className="vs-check">
              <input
                type="radio"
                name="vs-filter-category"
                checked={filters.category === category.slug}
                onChange={() => patch({ cat: category.slug })}
              />
              {category.name}
              <span className="vs-check__count">{category.count}</span>
            </label>
          ))}
        </fieldset>
      )}

      <fieldset className="vs-filters__group">
        <legend className="vs-filters__legend">السعر الأقصى — {money(max)}</legend>
        <input
          className="vs-range"
          type="range"
          min="0"
          max={ceiling}
          step={Math.max(1, Math.round(ceiling / 100))}
          value={max}
          onChange={(event) =>
            patch({ max: Number(event.target.value) >= ceiling ? null : event.target.value })
          }
          aria-label="السعر الأقصى"
        />
      </fieldset>

      <fieldset className="vs-filters__group">
        <legend className="vs-filters__legend">التوفّر والعروض</legend>
        <label className="vs-check">
          <input
            type="checkbox"
            checked={filters.onSale}
            onChange={(event) => patch({ sale: event.target.checked })}
          />
          المنتجات المخفّضة فقط
        </label>
        <label className="vs-check">
          <input
            type="checkbox"
            checked={filters.inStock}
            onChange={(event) => patch({ stock: event.target.checked })}
          />
          المتوفر في المخزون فقط
        </label>
      </fieldset>
    </div>
  );
}
