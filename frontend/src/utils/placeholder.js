// Products, categories and articles without an uploaded image fall back to the
// storefront's own tone gradients, so the design looks finished before any media
// has been uploaded. Once an image URL exists it takes over.

// Ten warm tones, all inside Tara's own range: ivory and cream through blush
// and mauve to the palest gold. A catalogue with no photography yet is the
// state this store actually launches in, so these gradients are most of what a
// visitor sees — the template's teal, steel and mint made that page read as a
// different brand's placeholder grid. Every pair stays light enough for the
// card's own dark title to sit over it.
const TONES = {
  ivory: ["#fdf8f2", "#eddbc7"],
  cream: ["#f8f0e5", "#e6d3bb"],
  blush: ["#f7ecea", "#e6d0cf"],
  mauve: ["#f2eaec", "#d7c3c8"],
  dusty: ["#efe6e8", "#c9b4ba"],
  rose: ["#f6ebeb", "#e0c8ca"],
  linen: ["#f6f1e9", "#ded0bd"],
  clay: ["#f4ebe4", "#dfc9bb"],
  gold: ["#faf1e2", "#eecc94"],
  stone: ["#f2eeea", "#dbd0c6"],
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
