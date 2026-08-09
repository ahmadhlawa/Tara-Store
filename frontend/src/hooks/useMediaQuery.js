import { useEffect, useState } from "react";

/** Reactive media query. Returns false where matchMedia is unavailable. */
export default function useMediaQuery(query) {
  const [matches, setMatches] = useState(() =>
    typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia(query).matches
      : false,
  );

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return undefined;
    const list = window.matchMedia(query);
    const onChange = (event) => setMatches(event.matches);
    setMatches(list.matches);
    list.addEventListener("change", onChange);
    return () => list.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

/** True when the visitor has asked the system for less motion. */
export function useReducedMotion() {
  return useMediaQuery("(prefers-reduced-motion: reduce)");
}
