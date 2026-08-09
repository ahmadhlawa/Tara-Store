// Fits a store logo to its header viewport when the file carries its own margin.
import { useEffect, useRef, useState } from "react";

// The file is sampled on a small square grid; the mark's bounds only need to be
// accurate to half a percent, and a 200×200 read is instant on any device.
const SAMPLE = 200;
// How far from white a pixel has to be, summed over the three channels, before
// it counts as part of the mark. Low enough for a pale tint, high enough that
// JPEG ringing along the edge of a white box does not register.
const INK = 60;
const ALPHA = 24;
// The mark is allowed this much of the viewport, so it never touches the clip.
const FILL = 0.94;
// A near-blank file must not be blown up to fill the box.
const MAX_ZOOM = 4;
// A mark already this large fills its own file: nothing to trim, so nothing is
// done. That is the case a properly prepared logo falls into.
const TRIMMED = 0.9;

/**
 * Finds where the artwork actually sits inside a logo file.
 *
 * Returns the mark's bounds as fractions of the file, or null when there is
 * nothing to correct — no canvas (server render, jsdom), a cross-origin file
 * that would taint it, a file that fails to load, or one that is already
 * trimmed. Every one of those falls back to plain `object-fit: contain`.
 */
function measureMark(src) {
  return new Promise((resolve) => {
    if (typeof document === "undefined") {
      resolve(null);
      return;
    }
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext?.("2d", { willReadFrequently: true });
    if (!ctx) {
      resolve(null);
      return;
    }
    const image = new Image();
    // Without this the pixels are unreadable from a CDN-hosted logo; with it a
    // host that sends no CORS header fails the load instead, which is the same
    // fallback either way.
    image.crossOrigin = "anonymous";
    image.onerror = () => resolve(null);
    image.onload = () => {
      canvas.width = SAMPLE;
      canvas.height = SAMPLE;
      let data;
      try {
        ctx.drawImage(image, 0, 0, SAMPLE, SAMPLE);
        data = ctx.getImageData(0, 0, SAMPLE, SAMPLE).data;
      } catch {
        resolve(null);
        return;
      }
      let minX = SAMPLE;
      let minY = SAMPLE;
      let maxX = -1;
      let maxY = -1;
      for (let y = 0; y < SAMPLE; y += 1) {
        for (let x = 0; x < SAMPLE; x += 1) {
          const i = (y * SAMPLE + x) * 4;
          const away = 765 - data[i] - data[i + 1] - data[i + 2];
          if (data[i + 3] <= ALPHA || away <= INK) continue;
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }
      if (maxX < 0) {
        resolve(null);
        return;
      }
      const bounds = {
        x0: minX / SAMPLE,
        x1: (maxX + 1) / SAMPLE,
        y0: minY / SAMPLE,
        y1: (maxY + 1) / SAMPLE,
        ratio: image.naturalWidth / image.naturalHeight,
      };
      const wide = bounds.x1 - bounds.x0 >= TRIMMED;
      const tall = bounds.y1 - bounds.y0 >= TRIMMED;
      resolve(wide && tall ? null : bounds);
    };
    image.src = src;
  });
}

/** The image geometry that centres the mark in the box and fills it. */
function fitTo(mark, box) {
  if (!mark || !box?.w || !box?.h) return undefined;
  const markW = mark.x1 - mark.x0;
  const markH = mark.y1 - mark.y0;
  if (!markW || !markH || !mark.ratio) return undefined;

  // The image is sized by whichever axis the mark runs out of first, so its own
  // proportions are kept exactly — the file is scaled, never squeezed.
  const height = Math.min(
    (box.h * FILL) / markH,
    (box.w * FILL) / (markW * mark.ratio),
  );
  const contained = Math.min(box.h, box.w / mark.ratio);
  const used = Math.max(contained, Math.min(height, contained * MAX_ZOOM));
  const width = used * mark.ratio;

  // Physical left/top: the geometry is computed in device space, and the header
  // around it is RTL, where a logical inset would flip the sign.
  return {
    width: `${Math.round(width * 100) / 100}px`,
    height: `${Math.round(used * 100) / 100}px`,
    left: `${Math.round((box.w / 2 - ((mark.x0 + mark.x1) / 2) * width) * 100) / 100}px`,
    top: `${Math.round((box.h / 2 - ((mark.y0 + mark.y1) / 2) * used) * 100) / 100}px`,
  };
}

/**
 * Scales a logo inside a fixed, clipped viewport so the mark itself is the
 * thing sized, not the file's padding.
 *
 * `boxRef` goes on the viewport, `style` on the image inside it. With nothing to
 * correct the style is undefined and the stylesheet's `object-fit: contain`
 * stands, which is exactly the behaviour every other client instance gets.
 */
export function useLogoFit(src) {
  const boxRef = useRef(null);
  const [mark, setMark] = useState(null);
  const [box, setBox] = useState(null);

  useEffect(() => {
    if (!src) {
      setMark(null);
      return undefined;
    }
    let cancelled = false;
    measureMark(src).then((result) => {
      if (!cancelled) setMark(result);
    });
    return () => {
      cancelled = true;
    };
  }, [src]);

  // The viewport is sized in CSS and changes at every breakpoint, so it is
  // observed rather than assumed.
  useEffect(() => {
    const node = boxRef.current;
    if (!node || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      if (rect) setBox({ w: rect.width, h: rect.height });
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [src]);

  return { boxRef, style: fitTo(mark, box) };
}
