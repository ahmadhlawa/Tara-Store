import { API_BASE_URL } from "../api/client.js";

const WIDTHS = [96, 240, 480, 800, 1440, 2048];
export const CARD_IMAGE_SIZES = "(max-width: 899px) calc((100vw - 52px) / 2), 320px";

/** Only immutable application uploads; external/editorial URLs keep their original delivery. */
export function responsiveImageProps(src, sizes = CARD_IMAGE_SIZES) {
  if (!src) return {};
  const url = new URL(src, "https://storefront.invalid");
  if (!/\/[a-f0-9]{32}\.(png|jpe?g|webp)$/i.test(url.pathname)) return {};
  const key = url.pathname.replace(/^\/media\//, "").replace(/^\//, "");
  const endpoint = `${API_BASE_URL}/storefront-media/${key.split("/").map(encodeURIComponent).join("/")}`;
  return {
    srcSet: WIDTHS.map(width => `${endpoint}?width=${width} ${width}w`).join(", "),
    sizes,
    onError: event => {
      const image = event.currentTarget;
      if (!image.hasAttribute("srcset")) return;
      image.removeAttribute("srcset");
      image.removeAttribute("sizes");
      image.src = src;
    },
  };
}
