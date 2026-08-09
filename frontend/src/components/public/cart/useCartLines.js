import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useStore } from "../../../app/StoreProvider.jsx";
import { useMoney } from "../../../hooks/useStorefront.js";

// How long the exit animation runs before the line actually leaves the store.
const EXIT_MS = 220;

/**
 * Cart lines shaped for display, plus the totals and the mutations the drawer
 * and the cart page both need. The removal delay lives here rather than in each
 * view so the exit animation cannot drift between the two.
 */
export function useCartLines() {
  const store = useStore();
  const money = useMoney();
  const [leaving, setLeaving] = useState([]);
  const timers = useRef([]);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const remove = useCallback(
    (key) => {
      setLeaving((current) => (current.includes(key) ? current : [...current, key]));
      timers.current.push(
        setTimeout(() => {
          store.removeLine(key);
          setLeaving((current) => current.filter((item) => item !== key));
        }, EXIT_MS),
      );
    },
    [store],
  );

  const lines = useMemo(
    () =>
      store.cart.map((line) => ({
        ...line,
        href: `/product/${line.slug}`,
        unitText: money(line.unit),
        lineText: money(line.unit * line.qty),
        variationText: line.variation || "",
        leaving: leaving.includes(line.key),
        increase: () => store.setLineQty(line.key, 1),
        decrease: () => store.setLineQty(line.key, -1),
        remove: () => remove(line.key),
      })),
    [store, money, leaving, remove],
  );

  const count = store.cart.reduce((sum, line) => sum + line.qty, 0);
  const subtotal = store.cart.reduce((sum, line) => sum + line.unit * line.qty, 0);

  return {
    lines,
    count,
    subtotal,
    subtotalText: money(subtotal),
    empty: store.cart.length === 0,
    money,
  };
}

export { EXIT_MS };
