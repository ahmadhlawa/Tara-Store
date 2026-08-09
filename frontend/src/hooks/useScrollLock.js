import { useEffect } from "react";

// Reference counted, because a modal opened from a drawer must not unlock the
// page when only the inner one closes.
let locks = 0;
let restore = null;

function lock() {
  locks += 1;
  if (locks > 1) return;
  const { body, documentElement } = document;
  const gap = window.innerWidth - documentElement.clientWidth;
  restore = {
    overflow: body.style.overflow,
    paddingInlineEnd: body.style.paddingInlineEnd,
  };
  body.style.overflow = "hidden";
  // Compensating for the scrollbar keeps the sticky header from shifting.
  if (gap > 0) body.style.paddingInlineEnd = `${gap}px`;
}

function unlock() {
  locks = Math.max(0, locks - 1);
  if (locks > 0 || !restore) return;
  document.body.style.overflow = restore.overflow;
  document.body.style.paddingInlineEnd = restore.paddingInlineEnd;
  restore = null;
}

/** Freezes background scrolling for as long as `active` is true. */
export function useScrollLock(active) {
  useEffect(() => {
    if (!active) return undefined;
    lock();
    return unlock;
  }, [active]);
}

// Test seam: vitest keeps module state between cases in one file.
export function __resetScrollLock() {
  locks = 0;
  restore = null;
  document.body.style.overflow = "";
  document.body.style.paddingInlineEnd = "";
}
