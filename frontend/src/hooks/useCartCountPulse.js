import { useEffect, useRef, useState } from "react";

/**
 * Returns a counter that increments whenever the cart quantity grows. The header
 * badge uses it both as a React key and as the animation switch, so the pulse
 * replays on every real increase — and never on the first render or on unrelated
 * state changes (a removed line, a coupon, an opened drawer).
 */
export function useCartCountPulse(count) {
  const previous = useRef(count);
  const [pulse, setPulse] = useState(0);

  useEffect(() => {
    if (count > previous.current) setPulse((value) => value + 1);
    previous.current = count;
  }, [count]);

  return pulse;
}
