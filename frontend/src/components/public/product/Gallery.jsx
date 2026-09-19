import { useLocale } from "../../../i18n/locale.jsx";
import { useEffect, useState } from "react";
import Media from "../shell/Media.jsx";

/**
 * Product gallery. Only the selected image is rendered at full size — the
 * thumbnails are small, so a long gallery never ships a screen full of
 * full-resolution pictures the visitor has not asked for.
 */
export default function Gallery({ images, fallback, alt }) {
  const { t } = useLocale();
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  const list = images?.length ? images : [];
  const active = list[index] || null;

  useEffect(() => setIndex(0), [images]);

  useEffect(() => {
    if (list.length <= 1 || paused) return undefined;
    const timer = window.setTimeout(() => {
      setIndex((current) => (current + 1) % list.length);
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [index, list.length, paused]);

  return (
    <div
      className="vs-gallery"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="vs-gallery__stage">
        <Media
          key={active?.id ?? active?.url ?? "fallback"}
          className="vs-gallery__main"
          src={active?.url}
          fallback={fallback}
          alt={alt}
          eager
        />
        {list.length > 1 && (
          <div className="vs-gallery__nav">
            <button type="button" aria-label={t("الصورة السابقة")} onClick={() => setIndex((current) => (current - 1 + list.length) % list.length)}>‹</button>
            <button type="button" aria-label={t("الصورة التالية")} onClick={() => setIndex((current) => (current + 1) % list.length)}>›</button>
          </div>
        )}
      </div>
      {list.length > 1 && (
        <div className="vs-gallery__thumbs" role="group" aria-label={t("صور المنتج")}>
          {list.map((image, position) => (
            <button
              key={image.id ?? position}
              type="button"
              className="vs-thumb"
              aria-pressed={position === index}
              aria-label={t("عرض الصورة {0}", [position + 1])}
              onClick={() => setIndex(position)}
            >
              <Media src={image.url} sizes="76px" fallback={fallback} alt="" ratio="1 / 1" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
