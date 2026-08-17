import { useEffect, useRef, useState } from "react";

/** One-time, compositor-friendly entrance for meaningful content groups. */
export function useViewportReveal(delay = 0) {
  const ref = useRef(null);
  const [entered, setEntered] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) {
      setEntered(true);
      return undefined;
    }
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      setEntered(true);
      observer.disconnect();
    }, { threshold: 0.14 });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return {
    ref,
    "data-viewport-reveal": entered ? "entered" : "pending",
    style: { "--vs-reveal-delay": `${delay}ms` },
  };
}
