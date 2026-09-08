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
  className = "",
  imgClass = "",
  children,
}) {
  const style = ratio ? { aspectRatio: ratio } : undefined;
  return (
    <div className={`vs-mediabox ${className}`.trim()} style={style}>
      {src ? (
        <img
          className={`vs-media ${imgClass}`.trim()}
          src={src}
          alt={alt}
          loading={eager ? "eager" : "lazy"}
          fetchPriority={fetchPriority}
          decoding="async"
        />
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
