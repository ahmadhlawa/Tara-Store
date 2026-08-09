import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Media from "../shell/Media.jsx";
import { ArrowForward } from "../shell/icons.jsx";

const INTERVAL_MS = 6000;
// Below this a horizontal drag is a swipe rather than a stray finger movement.
const SWIPE_PX = 45;

/**
 * The admin-managed advertising carousel: one complete image at a time, across
 * the full content width. There is nothing beside it — a slide is the artwork,
 * not a frame around a headline.
 *
 * Copy is rendered only where the Admin actually supplied supporting text — an
 * eyebrow, a paragraph or a button — so an advertisement that already carries
 * its own typography is not overprinted with a second heading. The veil follows
 * the copy for the same reason.
 *
 * Autoplay stops on hover, on focus, on any manual move and while the tab is
 * hidden, and never starts at all under `prefers-reduced-motion`. Swiping is a
 * pair of pointer handlers — no carousel dependency is added.
 */
export default function Hero({ slides }) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [hidden, setHidden] = useState(false);
  const startX = useRef(null);

  const count = slides.length;
  const go = useCallback(
    (next) => setIndex(((next % count) + count) % count),
    [count],
  );

  useEffect(() => {
    const onVisibility = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => {
    if (count < 2 || paused || hidden) return undefined;
    // Someone who has asked for less motion gets a static first slide and the
    // controls; movement they did not ask for is exactly what the setting means.
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return undefined;
    const timer = setInterval(() => setIndex((current) => (current + 1) % count), INTERVAL_MS);
    return () => clearInterval(timer);
  }, [count, paused, hidden]);

  const move = useCallback(
    (delta) => {
      setPaused(true);
      go(index + delta);
    },
    [go, index],
  );

  if (!count) return null;

  return (
    <section
      className="vs-hero"
      aria-roledescription="carousel"
      aria-label="عروض المتجر"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
      onPointerDown={(event) => {
        startX.current = event.clientX;
      }}
      onPointerUp={(event) => {
        if (startX.current === null) return;
        const travelled = event.clientX - startX.current;
        startX.current = null;
        if (Math.abs(travelled) < SWIPE_PX) return;
        // RTL: dragging towards the start edge asks for the next slide.
        move(travelled > 0 ? 1 : -1);
      }}
    >
      {slides.map((slide, slideIndex) => {
        const active = slideIndex === index;
        // `overlay` is what marks a slide as a complete advertisement: see
        // normalizeHeroSlide. Nothing is printed over artwork that says it is
        // already finished — no headline, no paragraph, no eyebrow, no button.
        const hasCopy =
          slide.overlay && !!(slide.title || slide.desc || slide.subtitle || slide.cta);
        return (
          <div
            key={slide.id}
            className="vs-hero__slide"
            data-active={active}
            aria-hidden={!active}
            role="group"
            aria-roledescription="شريحة"
            aria-label={`${slideIndex + 1} من ${count}`}
          >
            <Media
              className="vs-hero__media"
              src={slide.imageUrl}
              fallback={slide.fallback}
              alt={slide.title || ""}
              eager={slideIndex === 0}
            />
            {hasCopy && (
              <>
                <span className="vs-hero__veil" />
                <div className="vs-hero__body">
                  {slide.subtitle && <span className="vs-hero__eyebrow">{slide.subtitle}</span>}
                  {slide.title && <h2 className="vs-hero__title">{slide.title}</h2>}
                  {slide.desc && <p className="vs-hero__desc">{slide.desc}</p>}
                  {slide.cta && (
                    <Link
                      to={slide.href}
                      className="vs-btn vs-btn--primary vs-btn--lg vs-hero__cta"
                      tabIndex={active ? 0 : -1}
                    >
                      {slide.cta}
                      <ArrowForward size={16} />
                    </Link>
                  )}
                </div>
              </>
            )}
          </div>
        );
      })}

      {count > 1 && (
        <>
          <div className="vs-hero__dots" role="tablist" aria-label="شرائح العرض">
            {slides.map((slide, slideIndex) => (
              <button
                key={slide.id}
                type="button"
                role="tab"
                className="vs-hero__dot"
                aria-current={slideIndex === index}
                aria-label={`الشريحة ${slideIndex + 1}`}
                onClick={() => {
                  setPaused(true);
                  go(slideIndex);
                }}
              />
            ))}
          </div>
          <div className="vs-hero__arrows">
            <button
              type="button"
              className="vs-hero__arrow"
              aria-label="الشريحة السابقة"
              onClick={() => move(-1)}
            >
              <ArrowForward size={17} style={{ transform: "scaleX(-1)" }} />
            </button>
            <button
              type="button"
              className="vs-hero__arrow"
              aria-label="الشريحة التالية"
              onClick={() => move(1)}
            >
              <ArrowForward size={17} />
            </button>
          </div>
        </>
      )}
    </section>
  );
}
