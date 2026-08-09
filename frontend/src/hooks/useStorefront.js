// Small, focused hooks shared by the public components. Deliberately not one
// god view-model: each surface takes only what it needs.
import { useCallback, useEffect, useMemo, useRef } from "react";
import { useLocation } from "react-router-dom";
import { OVERLAY, useStore } from "../app/StoreProvider.jsx";
import { makeMoney } from "../utils/format.js";
import { productView } from "../utils/productView.js";

/** Currency formatter bound to the store's configured symbol. */
export function useMoney() {
  const { settings } = useStore();
  return useMemo(() => makeMoney(settings.currency), [settings.currency]);
}

/** Maps a raw product (or list of them) to the display shape cards expect. */
export function useProductViews(products) {
  const money = useMoney();
  return useMemo(
    () => (products || []).map((product) => productView(product, money)).filter(Boolean),
    [products, money],
  );
}

// The cart drawer opens a beat after the add so the button's success state is
// actually seen. One timer for the whole app: rapid adds queue into one open.
const CART_REVEAL_MS = 620;

/**
 * The two things a card can do: add straight to the cart, or open the quick
 * view because the product needs an option chosen first.
 */
export function useProductActions() {
  const store = useStore();
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  const revealCart = useCallback(
    (immediate) => {
      clearTimeout(timer.current);
      if (immediate) {
        store.openOverlay(OVERLAY.CART);
        return;
      }
      timer.current = setTimeout(() => store.openOverlay(OVERLAY.CART), CART_REVEAL_MS);
    },
    [store],
  );

  /**
   * `immediate` is for callers that close their own overlay as part of the add —
   * the quick view has already acknowledged the action, so waiting would leave
   * the screen empty for half a second.
   */
  const addProduct = useCallback(
    (view, qty = 1, variant = null, { immediate = false } = {}) => {
      if (!view || view.soldOut) return;
      store.addToCart(view.product, qty, variant);
      revealCart(immediate);
    },
    [revealCart, store],
  );

  const openQuick = useCallback(
    (view) => {
      if (!view) return;
      store.openOverlay(OVERLAY.QUICK, view.slug);
    },
    [store],
  );

  /** What a card's primary button should do, given the product's state. */
  const primaryAction = useCallback(
    (view) => () => {
      if (!view || view.soldOut) return;
      if (view.canAddDirectly) addProduct(view, 1, null);
      else openQuick(view);
    },
    [addProduct, openQuick],
  );

  return { addProduct, openQuick, primaryAction };
}

/**
 * The category slug the current route is showing, or null. Derived from the URL
 * rather than stored, so the rail, the drawer and the catalogue page can never
 * disagree about which category is active.
 */
export function useActiveCategorySlug() {
  const { pathname } = useLocation();
  return useMemo(() => {
    const match = /^\/category\/([^/]+)/.exec(pathname);
    return match ? decodeURIComponent(match[1]) : null;
  }, [pathname]);
}

/** Top-level categories with routes and an active flag, ready for navigation. */
export function useCategoryNav(activeSlug = null) {
  const { categories } = useStore();
  return useMemo(
    () =>
      categories.map((category) => ({
        ...category,
        href: `/category/${category.slug}`,
        active: category.slug === activeSlug,
        countText: category.count === 1 ? "منتج واحد" : `${category.count} منتجاً`,
        children: (category.children || []).map((child) => ({
          ...child,
          href: `/category/${child.slug}`,
          active: child.slug === activeSlug,
        })),
      })),
    [categories, activeSlug],
  );
}
