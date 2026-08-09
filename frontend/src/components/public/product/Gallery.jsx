import { useEffect, useState } from "react";
import Media from "../shell/Media.jsx";

/**
 * Product gallery. Only the selected image is rendered at full size — the
 * thumbnails are small, so a long gallery never ships a screen full of
 * full-resolution pictures the visitor has not asked for.
 */
export default function Gallery({ images, fallback, alt }) {
  const [index, setIndex] = useState(0);
  useEffect(() => setIndex(0), [alt]);

  const list = images?.length ? images : [];
  const active = list[index] || null;

  return (
    <div className="vs-gallery">
      <Media
        className="vs-gallery__main"
        ratio="1 / 1"
        src={active?.url}
        fallback={fallback}
        alt={alt}
        eager
      />
      {list.length > 1 && (
        <div className="vs-gallery__thumbs" role="group" aria-label="صور المنتج">
          {list.map((image, position) => (
            <button
              key={image.id ?? position}
              type="button"
              className="vs-thumb"
              aria-pressed={position === index}
              aria-label={`عرض الصورة ${position + 1}`}
              onClick={() => setIndex(position)}
            >
              <Media src={image.url} fallback={fallback} alt="" ratio="1 / 1" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
