import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

export const SORTS = [
  { value: "featured", label: "المميّزة أولاً" },
  { value: "newest", label: "الأحدث" },
  { value: "price-asc", label: "السعر: الأقل أولاً" },
  { value: "price-desc", label: "السعر: الأعلى أولاً" },
  { value: "name", label: "الاسم" },
];

const SORT_VALUES = SORTS.map((sort) => sort.value);

/**
 * Catalogue state lives in the URL, so a filtered listing can be shared, the
 * back button undoes a filter, and a reload keeps what the visitor chose.
 *
 * Only fields the public products endpoint actually honours are represented —
 * there is no filter here that the server would quietly ignore.
 */
export function useCatalogQuery() {
  const [params, setParams] = useSearchParams();

  const filters = useMemo(() => {
    const sort = params.get("sort");
    const number = (key) => {
      const raw = params.get(key);
      const value = Number(raw);
      return raw !== null && raw !== "" && Number.isFinite(value) ? value : null;
    };
    return {
      q: params.get("q") || "",
      category: params.get("cat") || "",
      sort: SORT_VALUES.includes(sort) ? sort : "featured",
      onSale: params.get("sale") === "1",
      inStock: params.get("stock") === "1",
      minPrice: number("min"),
      maxPrice: number("max"),
    };
  }, [params]);

  const patch = useCallback(
    (changes) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          Object.entries(changes).forEach(([key, value]) => {
            if (value === null || value === "" || value === false) next.delete(key);
            else next.set(key, value === true ? "1" : String(value));
          });
          return next;
        },
        { replace: false },
      );
    },
    [setParams],
  );

  const reset = useCallback(() => {
    setParams(
      (current) => {
        const next = new URLSearchParams();
        // The search term is the page's subject, not a filter — clearing filters
        // must not empty the search results.
        const q = current.get("q");
        if (q) next.set("q", q);
        return next;
      },
      { replace: false },
    );
  }, [setParams]);

  const active = useMemo(() => {
    const chips = [];
    if (filters.category) chips.push({ key: "cat", label: filters.category, clear: { cat: null } });
    if (filters.onSale) chips.push({ key: "sale", label: "المخفّضة فقط", clear: { sale: null } });
    if (filters.inStock) chips.push({ key: "stock", label: "المتوفر فقط", clear: { stock: null } });
    if (filters.minPrice != null || filters.maxPrice != null) {
      chips.push({
        key: "price",
        label: "نطاق السعر",
        clear: { min: null, max: null },
      });
    }
    return chips;
  }, [filters]);

  return { filters, patch, reset, active };
}
