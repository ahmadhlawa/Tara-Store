import { responsiveImageProps } from "../../../utils/responsiveImage.js";

/**
 * The one way the storefront shows a picture.
 *
 * Always reserves its box through `aspect-ratio`, so nothing shifts while an
 * image decodes; below-fold images are lazy by default; a record with no
 * uploaded image gets a deliberate tone gradient instead of a blank rectangle.
 */
export default function Media({
  src,
  alt = "",
  fallback,
  ratio,
  eager = false,
  fetchPriority,
  sizes = "100vw",
  className = "",
  imgClass = "",
  backdrop = false,
  children,
}) {
  const style = ratio ? { aspectRatio: ratio } : undefined;
  return (
    <div className={`vs-mediabox ${className}`.trim()} style={style}>
      {src ? (
        <>
          {backdrop && (
            <img
              className="vs-media vs-media--backdrop"
              src={src}
              {...responsiveImageProps(src, sizes)}
              alt=""
              aria-hidden="true"
              loading={eager ? "eager" : "lazy"}
              decoding="async"
            />
          )}
          <img
            className={`vs-media ${backdrop ? "vs-media--foreground" : ""} ${imgClass}`.trim()}
            src={src}
            {...responsiveImageProps(src, sizes)}
            alt={alt}
            loading={eager ? "eager" : "lazy"}
            fetchpriority={fetchPriority}
            decoding="async"
          />
        </>
      ) : (
        <span
          className={`vs-media--fallback ${imgClass}`.trim()}
          style={{ background: fallback }}
          role={alt ? "img" : "presentation"}
          aria-label={alt || undefined}
        />
      )}
      {children}
    </div>
  );
}
