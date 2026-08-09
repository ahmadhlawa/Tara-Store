import { useCallback, useRef, useState } from "react";

/**
 * Touch behaviour for a card whose details are revealed on hover.
 *
 * A pointer gets the reveal from `:hover`, a keyboard from `:focus-within` —
 * both are pure CSS. A finger has neither, so the first tap on an inert part of
 * the card reveals it instead of navigating, and any tap after that behaves
 * normally. Buttons are never intercepted: an action inside the panel is already
 * visible by the time it can be pressed, so it stays one tap.
 *
 * Below 900px the panel is laid out statically and always visible, so nothing
 * here is load-bearing on a phone — this only covers a coarse pointer on a
 * screen wide enough to use the overlay form.
 */
export function useCardReveal() {
  const [revealed, setRevealed] = useState(false);
  const coarse = useRef(false);

  const onPointerDown = useCallback((event) => {
    coarse.current = event.pointerType === "touch" || event.pointerType === "pen";
  }, []);

  const onClickCapture = useCallback(
    (event) => {
      if (!coarse.current || revealed) return;
      // Capture phase, so this runs before the link's own handler and can stop
      // the navigation the first tap would otherwise cause.
      if (event.target.closest?.("button, input, select, textarea, [data-card-action]")) return;
      event.preventDefault();
      event.stopPropagation();
      setRevealed(true);
    },
    [revealed],
  );

  return {
    revealed,
    cardProps: { "data-revealed": revealed, onPointerDown, onClickCapture },
  };
}
