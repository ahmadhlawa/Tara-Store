// Tara's shipped brand assets and identity fallbacks.
//
// One module for the two things that are true of this instance rather than of
// the software: where the supplied logo lives, and what the store is called
// before StoreSettings has answered. Everything the owner can edit in Admin
// still wins — these are the values that fill the gap, not values that override.
//
// The colours are not here. They belong to the theme layer
// (src/styles/public/tokens.css for the storefront, src/index.css for the
// document) and are echoed into StoreSettings' defaults in services/storefront.js
// so a fresh database boots on brand.

/** The owner's logo, served from public/branding/. Never cropped, recoloured or
 *  regenerated — the only edit is the one the client asked for: the supplied
 *  JPEG's ivory ground is keyed out, so the PNG shipped here is the same mark on
 *  transparency and sits on the white page (and on a lilac band) without
 *  carrying its own square of cream. The original JPEG stays beside it as the
 *  source file. */
export const LOGO_URL = "/branding/tara-logo2.png";

/** The brand name is latin and is shown as such: the storefront's language is
 *  Arabic, but "Tara" is what the logo says and what the store is called. The
 *  Arabic form is kept only as the last resort for an instance that has set an
 *  Arabic name and nothing else — it is not the name this store displays. */
export const STORE_NAME_AR = "تارا";
export const STORE_NAME_LATIN = "Tara";
export const STORE_TAGLINE = "Handmade by Yumna";
