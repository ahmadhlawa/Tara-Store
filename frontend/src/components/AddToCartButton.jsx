import { useCallback, useEffect, useRef, useState } from "react";

// Shared "add to cart" affordance for the product and package cards. The cards
// keep their own dimensions and colours (passed in as `style`); everything the
// interaction needs — hover lift, press scale, the success window and the
// double-click guard — lives here so the two cards cannot drift apart.
export const ADDED_LABEL = "تمت الإضافة";
export const SUCCESS_MS = 1000;

/**
 * Fires `onAdd` once, then holds a success flag for SUCCESS_MS.
 *
 * `onAdd` may return `false` to say the add did not happen — a product whose
 * options have not been chosen, for instance. The button must not claim success
 * for something it refused to do.
 */
export function useAddToCartFeedback(onAdd) {
  const [added, setAdded] = useState(false);
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  const fire = useCallback(() => {
    // While the success state is showing, further activations are swallowed:
    // one click (or Enter/Space) must never add two lines.
    if (added) return;
    if (onAdd?.() === false) return;
    setAdded(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setAdded(false), SUCCESS_MS);
  }, [added, onAdd]);

  return { added, fire };
}

export default function AddToCartButton({
  onAdd,
  label,
  icon,
  disabled = false,
  style,
  className = "",
}) {
  const { added, fire } = useAddToCartFeedback(onAdd);
  return (
    <button
      type="button"
      onClick={fire}
      disabled={disabled}
      aria-live="polite"
      className={`vs-atc ${className}${added ? " is-added" : ""}`.trim()}
      style={style}
    >
      {added ? (
        <>
          <span aria-hidden="true">✓</span>
          {ADDED_LABEL}
        </>
      ) : (
        <>
          {icon}
          {label}
        </>
      )}
    </button>
  );
}
