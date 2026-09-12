import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { catalogService } from "../services/catalog.js";
import { storefrontService, FALLBACK_SETTINGS, normalizeSettings } from "../services/storefront.js";
import { cartStorage, lineKey, searchStorage, viewedStorage } from "../storage/cartStorage.js";

const StoreContext = createContext(null);

/**
 * Exactly one overlay can be open at a time, so the value is a single name
 * rather than a set of booleans — drawer exclusivity becomes structural instead
 * of something every call site has to remember.
 */
export const OVERLAY = {
  CART: "cart",
  MENU: "menu",
  CATEGORIES: "categories",
  SEARCH: "search",
  FILTERS: "filters",
  QUICK: "quick",
};

export function useStore() {
  const context = useContext(StoreContext);
  if (!context) throw new Error("useStore must be used inside <StoreProvider>");
  return context;
}

export function StoreProvider({ children }) {
  const [settings, setSettings] = useState(() => normalizeSettings(FALLBACK_SETTINGS));
  const [categories, setCategories] = useState([]);
  const [deliveryAreas, setDeliveryAreas] = useState([]);
  const [ready, setReady] = useState(false);
  const [loadError, setLoadError] = useState(null);

  const [cart, setCart] = useState(() => cartStorage.load());
  const [bump, setBump] = useState(0);
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  // `overlay` is the open overlay's name; `quickSlug` carries the product the
  // quick view is showing, which is the only overlay with a payload.
  const [overlay, setOverlay] = useState(null);
  const [quickSlug, setQuickSlug] = useState(null);
  const [navOpenCat, setNavOpenCat] = useState(null);
  const [announce, setAnnounce] = useState(true);
  const [scrolled, setScrolled] = useState(false);

  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState({ products: [], cats: [] });
  const [suggestTried, setSuggestTried] = useState(false);
  const [recentSearches, setRecentSearches] = useState(() => searchStorage.load());
  const suggestTimer = useRef(null);

  const [viewed, setViewed] = useState(() => viewedStorage.load());

  // Coupon and checkout form state live here because the cart drawer, the cart
  // page and the checkout page all read and write them.
  const [coupon, setCoupon] = useState({
    input: "",
    applied: "",
    label: "",
    message: "",
    ok: false,
    discount: 0,
  });
  const [checkoutForm, setCheckoutForm] = useState({
    name: "",
    phone: "",
    areaId: null,
    address: "",
    notes: "",
    payment: "cash_on_delivery",
    terms: false,
  });

  // ── bootstrap ──────────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const results = await Promise.allSettled([
        storefrontService.settings(),
        catalogService.categories(),
        storefrontService.deliveryAreas(),
      ]);
      if (cancelled) return;
        const [settingsResult, categoriesResult, areasResult] = results;
      if (settingsResult.status === "fulfilled") setSettings(settingsResult.value);
      if (categoriesResult.status === "fulfilled") setCategories(categoriesResult.value);
      if (areasResult.status === "fulfilled") setDeliveryAreas(areasResult.value);

      const failure = results.find((result) => result.status === "rejected");
      // A failed bootstrap must not blank the storefront: defaults stay in place
      // and the shell renders with an explicit message.
      setLoadError(failure ? failure.reason : null);
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const closeAll = useCallback(() => {
    setOverlay(null);
    setQuickSlug(null);
  }, []);

  /** Opening any overlay closes whatever was open — never two at once. */
  const openOverlay = useCallback((name, payload = null) => {
    setOverlay(name);
    setQuickSlug(name === OVERLAY.QUICK ? payload : null);
  }, []);

  useEffect(() => {
    // Backstop for an Escape pressed while focus sits outside the open dialog;
    // the dialog's own trap handles the normal case and stops propagation.
    const onKey = (event) => {
      if (event.key === "Escape") closeAll();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeAll]);

  useEffect(
    () => () => {
      clearTimeout(toastTimer.current);
      clearTimeout(suggestTimer.current);
    },
    [],
  );

  // ── toast ──────────────────────────────────────────────────────────────────
  const showToast = useCallback((message) => {
    clearTimeout(toastTimer.current);
    setToast(message);
    toastTimer.current = setTimeout(() => setToast(null), 3600);
  }, []);

  // ── cart ───────────────────────────────────────────────────────────────────
  const persistCart = useCallback((next) => {
    cartStorage.save(next);
    setCart(next);
  }, []);

  const addToCart = useCallback(
    (product, qty = 1, variant = null) => {
      if (!product) return;
      const selectedOptionValueIds = variant?.selected_option_value_ids || [];
      const unit = variant?.price_override != null ? Number(variant.price_override) : (product.sale ?? product.price);
      const key = lineKey(product.id, variant?.id, selectedOptionValueIds);
      const next = cart.slice();
      const index = next.findIndex((line) => line.key === key);
      if (index > -1) {
        next[index] = { ...next[index], qty: next[index].qty + qty };
      } else {
        const selectedIds = new Set((variant?.option_value_ids || []).map(Number));
        const options = product.options || [];
        const sameCombination = (product.variants || []).filter((row) => {
          const ids = (row.option_value_ids || []).map(Number);
          return ids.length === selectedIds.size && ids.every((id) => selectedIds.has(id));
        });
        const describesExactCombination = selectedIds.size === options.length
          && options.every((option) => option.values.filter((value) => selectedIds.has(Number(value.id))).length === 1)
          && sameCombination.length === 1;
        const optionSummary = describesExactCombination ? options
          .flatMap((option) => (option.values || [])
            .filter((value) => selectedIds.has(Number(value.id)))
            .map((value) => `${option.name}: ${value.value}`))
          .join("، ") : "";
        next.push({
          key,
          productId: product.id,
          variantId: variant?.id ?? null,
          selectedOptionValueIds,
          slug: product.slug,
          name: product.name,
          unit,
          bg: product.bg,
          imageUrl: product.imageUrl || null,
          variation: optionSummary || variant?.title || "",
          qty,
        });
      }
      persistCart(next);
      setBump((value) => value + 1);
      const label = product.name.length > 34 ? `${product.name.slice(0, 34)}…` : product.name;
      showToast(`تمت إضافة «${label}» إلى العربة`);
    },
    [cart, persistCart, showToast],
  );

  const setLineQty = useCallback(
    (key, delta) => {
      persistCart(
        cart.map((line) =>
          line.key === key ? { ...line, qty: Math.max(1, line.qty + delta) } : line,
        ),
      );
    },
    [cart, persistCart],
  );

  const removeLine = useCallback(
    (key) => persistCart(cart.filter((line) => line.key !== key)),
    [cart, persistCart],
  );

  const clearCart = useCallback(() => persistCart([]), [persistCart]);

  // ── search suggestions ─────────────────────────────────────────────────────
  const runSuggest = useCallback(
    (value) => {
      clearTimeout(suggestTimer.current);
      setQuery(value);
      setSuggestTried(false);
      if (value.trim().length < 2) {
        setSuggestions({ products: [], cats: [] });
        return;
      }
      suggestTimer.current = setTimeout(async () => {
        try {
          const result = await catalogService.list({ q: value.trim(), page_size: 6 });
          const needle = value.trim();
          setSuggestions({
            products: result.items,
            cats: categories.filter((category) => category.name.includes(needle)).slice(0, 3),
          });
        } catch {
          setSuggestions({ products: [], cats: [] });
        } finally {
          setSuggestTried(true);
        }
      }, 260);
    },
    [categories],
  );

  const rememberSearch = useCallback((term) => {
    setRecentSearches(searchStorage.push(term));
  }, []);

  const rememberViewed = useCallback((slug) => {
    setViewed(viewedStorage.push(slug));
  }, []);

  const value = useMemo(
    () => ({
      ready,
      loadError,
      settings,
      categories,
      deliveryAreas,
      cart,
      bump,
      addToCart,
      setLineQty,
      removeLine,
      clearCart,
      toast,
      showToast,
      overlay,
      quickSlug,
      openOverlay,
      closeAll,
      navOpenCat,
      setNavOpenCat,
      announce,
      setAnnounce,
      scrolled,
      query,
      setQuery,
      suggestions,
      suggestTried,
      runSuggest,
      recentSearches,
      rememberSearch,
      viewed,
      rememberViewed,
      coupon,
      setCoupon,
      checkoutForm,
      setCheckoutForm,
    }),
    [
       ready, loadError, settings, categories, deliveryAreas, cart, bump,
      addToCart, setLineQty, removeLine, clearCart, toast, showToast, overlay, quickSlug,
      openOverlay, closeAll, navOpenCat, announce, scrolled, query,
      suggestions, suggestTried, runSuggest, recentSearches, rememberSearch,
      viewed, rememberViewed, coupon, checkoutForm,
    ],
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}
