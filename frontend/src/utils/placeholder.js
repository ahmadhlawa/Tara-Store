// Products, categories and articles without an uploaded image fall back to the
// storefront's own tone gradients, so the design looks finished before any media
// has been uploaded. Once an image URL exists it takes over.

// Ten tones derive from the global brand tokens, with one secondary-colour pair
// kept as the rare highlight. A
// catalogue with no photography yet is the state this store actually launches
// in, so these gradients are most of what a visitor sees. Every pair stays light
// enough for the card's own dark title to sit over it.
const TONES = {
  ivory: ["var(--surface-background)", "var(--brand-soft-hover)"],
  cream: ["var(--brand-soft)", "var(--brand-primary-pale)"],
  blush: ["var(--brand-soft)", "var(--brand-primary-pale)"],
  mauve: ["var(--brand-soft)", "var(--brand-primary-pale)"],
  dusty: ["var(--brand-soft-hover)", "var(--brand-primary-pale)"],
  rose: ["var(--brand-soft)", "var(--brand-primary-pale)"],
  linen: ["var(--brand-soft)", "var(--brand-primary-pale)"],
  clay: ["var(--brand-soft-hover)", "var(--brand-primary-pale)"],
  gold: ["color-mix(in srgb,var(--brand-secondary) 16%,var(--surface-background))", "color-mix(in srgb,var(--brand-secondary) 58%,var(--surface-background))"],
  stone: ["var(--brand-soft-hover)", "var(--brand-primary-pale)"],
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
