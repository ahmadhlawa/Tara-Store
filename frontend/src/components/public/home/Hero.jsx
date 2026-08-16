import { useEffect, useState } from "react";
import Media from "../shell/Media.jsx";

const INTERVAL_MS = 6000;

/** The uploaded artwork is the complete Hero; the application adds no copy or chrome. */
export default function Hero({ slides }) {
  const [index, setIndex] = useState(0);
  const [hidden, setHidden] = useState(false);
  const count = slides.length;

  useEffect(() => {
    const onVisibility = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => {
    if (count < 2 || hidden) return undefined;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return undefined;
    const timer = setInterval(() => setIndex((current) => (current + 1) % count), INTERVAL_MS);
    return () => clearInterval(timer);
  }, [count, hidden]);

  if (!count) return null;

  return (
    <section className="vs-hero" aria-label="العروض">
      {slides.map((slide, slideIndex) => (
        <div
          key={slide.id}
          className="vs-hero__slide"
          data-active={slideIndex === index}
          aria-hidden={slideIndex !== index}
        >
          <Media className="vs-hero__media" src={slide.imageUrl} alt="" eager={slideIndex === 0} />
        </div>
      ))}
    </section>
  );
}
