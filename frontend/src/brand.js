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

/** The owner's logo, served from public/branding/. Used unedited: never cropped,
 *  recoloured or regenerated. It is a square lockup carrying its own ivory
 *  ground, which is why the storefront header is ivory too. */
export const LOGO_URL = "/branding/tara-logo2.jpeg";

/** Arabic is the storefront's own language, so it is the name shown; the latin
 *  form stays the fallback and the document title. */
export const STORE_NAME_AR = "تارا";
export const STORE_NAME_LATIN = "Tara Store";
export const STORE_TAGLINE = "Handmade by Yumna";
