// Products, categories and articles without an uploaded image fall back to the
// storefront's own tone gradients, so the design looks finished before any media
// has been uploaded. Once an image URL exists it takes over.

const TONES = {
  teal: ["#e8f0ef", "#c9dcd8"],
  sand: ["#f1ece5", "#ddd2c2"],
  rose: ["#f3e9ea", "#e2cdd0"],
  cream: ["#f6efe4", "#e8d8bd"],
  lilac: ["#eceaf2", "#d3cfe2"],
  steel: ["#eaeced", "#cfd5d8"],
  olive: ["#eef1e9", "#d5ddca"],
  clay: ["#f2e8e2", "#dfc9bb"],
  mint: ["#e9f2ec", "#c8ddd0"],
  stone: ["#eeece8", "#d6d1c7"],
};

const TONE_NAMES = Object.keys(TONES);
const ANGLES = [145, 215, 120, 35];

function hashOf(value) {
  const text = String(value || "");
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
  return hash;
}

export function toneFor(seed) {
  return TONE_NAMES[hashOf(seed) % TONE_NAMES.length];
}

export function gradient(seed, index = 0) {
  const [from, to] = TONES[toneFor(seed)];
  const angle = ANGLES[index % ANGLES.length];
  return `linear-gradient(${angle}deg,${from} 0%,${to} 100%)`;
}

/** A CSS background value: the real image when there is one, a gradient otherwise. */
export function backgroundFor(imageUrl, seed, index = 0) {
  if (imageUrl) return `url("${imageUrl}") center/cover no-repeat`;
  return gradient(seed, index);
}

/** Four backgrounds for a product gallery, padded with gradients when needed. */
export function galleryFor(images, seed) {
  const urls = (images || []).map((image) => image.url).filter(Boolean);
  if (urls.length) return urls.map((url) => backgroundFor(url, seed));
  return ANGLES.map((_, index) => gradient(seed, index));
}
