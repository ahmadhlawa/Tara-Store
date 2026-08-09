import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useStore } from "../../../app/StoreProvider.jsx";
import { useMoney } from "../../../hooks/useStorefront.js";
import { SearchIcon } from "../shell/icons.jsx";
import Media from "../shell/Media.jsx";

/**
 * The storefront's single search implementation: a field, debounced suggestions
 * from the products API, and full keyboard control. The desktop header renders
 * it inline; the mobile search sheet renders the same component.
 */
export default function SearchBox({ autoFocus = false, onNavigate, placeholder }) {
  const store = useStore();
  const money = useMoney();
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [active, setActive] = useState(-1);
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  const term = store.query.trim();

  // One flat list so the arrow keys walk categories and products alike.
  const rows = useMemo(() => {
    if (term.length >= 2) {
      return [
        ...store.suggestions.cats.map((category) => ({
          key: `c-${category.slug}`,
          kind: "category",
          label: category.name,
          to: `/category/${category.slug}`,
        })),
        ...store.suggestions.products.map((product) => ({
          key: `p-${product.slug}`,
          kind: "product",
          label: product.name,
          priceText: money(product.sale ?? product.price),
          imageUrl: product.imageUrl,
          bg: product.bg,
          to: `/product/${product.slug}`,
        })),
      ];
    }
    return store.recentSearches.map((text) => ({
      key: `r-${text}`,
      kind: "recent",
      label: text,
      term: text,
    }));
  }, [term, store.suggestions, store.recentSearches, money]);

  useEffect(() => setActive(-1), [term]);

  const go = useCallback(
    (row) => {
      if (!row) return;
      if (row.kind === "recent") {
        store.rememberSearch(row.term);
        navigate(`/search?q=${encodeURIComponent(row.term)}`);
      } else {
        navigate(row.to);
      }
      setFocused(false);
      onNavigate?.();
    },
    [navigate, onNavigate, store],
  );

  const submit = (event) => {
    event.preventDefault();
    if (active > -1 && rows[active]) {
      go(rows[active]);
      return;
    }
    if (!term) return;
    store.rememberSearch(term);
    setFocused(false);
    navigate(`/search?q=${encodeURIComponent(term)}`);
    onNavigate?.();
  };

  const onKeyDown = (event) => {
    if (!rows.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => (index + 1) % rows.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => (index <= 0 ? rows.length - 1 : index - 1));
    }
  };

  const tried = store.suggestTried && term.length >= 2;
  const open = focused && (rows.length > 0 || tried);

  return (
    <form className="vs-hsearch" role="search" onSubmit={submit}>
      <input
        ref={inputRef}
        type="search"
        className="vs-hsearch__field"
        value={store.query}
        onChange={(event) => store.runSuggest(event.target.value)}
        onFocus={() => setFocused(true)}
        // A blur straight into a suggestion must not close the list first.
        onBlur={() => setTimeout(() => setFocused(false), 140)}
        onKeyDown={onKeyDown}
        aria-label="ابحث في المتجر"
        aria-expanded={open}
        aria-controls="vs-suggest-list"
        role="combobox"
        autoComplete="off"
        placeholder={placeholder || "ابحث عن منتج أو قسم…"}
      />
      <span className="vs-hsearch__icon">
        <SearchIcon size={19} />
      </span>
      <button type="submit" className="vs-hsearch__submit">
        بحث
      </button>

      {open && (
        <div className="vs-suggest" id="vs-suggest-list" role="listbox">
          {rows.length === 0 && tried && (
            <p className="vs-suggest__empty">لا توجد نتائج لـ «{term}» — جرّب كلمة أعم.</p>
          )}
          {rows.length > 0 && term.length < 2 && (
            <div className="vs-suggest__label">عمليات بحث سابقة</div>
          )}
          {rows.map((row, index) => (
            <button
              key={row.key}
              type="button"
              role="option"
              aria-selected={index === active}
              data-active={index === active}
              className="vs-suggest__row"
              onMouseEnter={() => setActive(index)}
              onClick={() => go(row)}
            >
              {row.kind === "product" ? (
                <>
                  <Media
                    className="vs-suggest__thumb"
                    src={row.imageUrl}
                    fallback={row.bg}
                    alt=""
                  />
                  <span className="vs-suggest__text">
                    <span className="vs-suggest__name">{row.label}</span>
                    <span className="vs-suggest__price">{row.priceText}</span>
                  </span>
                </>
              ) : (
                <>
                  <span className="vs-suggest__kind">
                    {row.kind === "category" ? "قسم" : "بحث سابق"}
                  </span>
                  <span className="vs-suggest__name">{row.label}</span>
                </>
              )}
            </button>
          ))}
        </div>
      )}
    </form>
  );
}
