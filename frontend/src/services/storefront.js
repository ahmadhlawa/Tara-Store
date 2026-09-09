// Store identity, homepage composition and editorial content.
import { LOGO_URL, STORE_NAME_AR, STORE_NAME_LATIN, STORE_TAGLINE } from "../brand.js";
import { publicApi } from "../api/publicApi.js";
import { heroDestination } from "../utils/storeRoutes.js";

// Tara's own identity and colours, sampled from the owner's logo, so the
// storefront is on brand from the first paint. The API's StoreSettings still
// wins the moment it arrives — these only cover the gap before it does, a fresh
// database that has not been filled in yet, and a failed bootstrap. Everything
// here stays editable from Admin.
// Only what a store genuinely has no other source for. Identity — the names,
// the strapline, the logo — is deliberately *not* here: `raw` is handed on to
// callers as the store's saved record, and seeding it with Tara's defaults would
// report values the owner never saved. Those fall back one level down instead,
// where they can be applied without being claimed.
export const FALLBACK_SETTINGS = {
  store_name: STORE_NAME_LATIN,
  currency_symbol: "₪",
  maintenance_mode: false,
};

export function normalizeSettings(raw) {
  const settings = { ...FALLBACK_SETTINGS, ...(raw || {}) };
  return {
    raw: settings,
    // The storefront is Arabic and RTL, so the Arabic name wins wherever the owner has
    // set one; the latin name stays the fallback.
    // Tara's own identity sits at the *end* of each chain, never in the merge
    // above: a fresh database answers with explicit nulls that the spread would
    // copy straight over a default, and a store that has filled in only its
    // latin name must keep it rather than be renamed تارا. Every one of these
    // stays editable from Admin; clearing a field only restores Tara's value.
    storeName: settings.store_name_ar || settings.store_name || STORE_NAME_AR,
    storeNameLatin: settings.store_name || STORE_NAME_LATIN,
    tagline: settings.store_tagline || STORE_TAGLINE,
    logoUrl: settings.logo_url || LOGO_URL,
    faviconUrl: settings.favicon_url || null,
    phone: settings.phone || "",
    whatsapp: settings.whatsapp || "",
    email: settings.email || "",
    address: settings.address || "",
    locationUrl: settings.location_url || "",
    hours: settings.working_hours || "",
    announcement: settings.announcement || "",
    instagram: settings.instagram_url || "",
    instagramVisible: settings.instagram_visible !== false,
    facebook: settings.facebook_url || "",
    facebookVisible: settings.facebook_visible !== false,
    tiktok: settings.tiktok_url || "",
    tiktokVisible: settings.tiktok_visible !== false,
    youtube: settings.youtube_url || "",
    youtubeVisible: settings.youtube_visible !== false,
    currency: settings.currency_symbol || "₪",
    currencyCode: settings.currency_code || "ILS",
    publicBaseUrl: settings.public_base_url || "",
    seoTitle: settings.seo_title || settings.store_name || STORE_NAME_LATIN,
    seoDescription: settings.seo_description || "",
    maintenanceMode: !!settings.maintenance_mode,
    // Blank until the owner supplies real account details. The checkout shows nothing
    // rather than inventing transfer instructions.
    manualPaymentInstructions: settings.manual_payment_instructions || "",
  };
}

export function normalizeHeroSlide(raw) {
  // What decides whether copy is printed over the artwork: an eyebrow, a
  // paragraph or a button — the fields an owner fills in *in addition to*
  // naming the slide. A slide with an image and nothing but a name is a
  // finished advertisement whose artwork already carries its own typography;
  // its title stays the slide's label in Admin and the image's alt text, and
  // nothing is overprinted on it. A slide with no image has only its copy, so
  // that always shows — otherwise the slide would be a blank gradient.
  return {
    id: raw.id,
    imageUrl: raw.image_url,
    destination: heroDestination(raw),
  };
}

export function normalizePage(raw) {
  const paragraphs = String(raw?.content || "")
    .split(/\n{2,}/)
    .map((text) => text.trim())
    .filter(Boolean);
  return {
    title: raw?.title || "",
    slug: raw?.slug || "",
    lead: raw?.lead || "",
    body: paragraphs.length ? paragraphs : [String(raw?.content || "").trim()].filter(Boolean),
    seoTitle: raw?.seo_title || "",
    seoDescription: raw?.seo_description || "",
  };
}

export function normalizeDeliveryArea(raw) {
  return {
    id: raw.id,
    name: raw.name,
    price: Number(raw.delivery_fee) || 0,
    freeOver: raw.free_delivery_threshold == null ? null : Number(raw.free_delivery_threshold),
    minOrder: raw.min_order_amount == null ? null : Number(raw.min_order_amount),
    eta: raw.estimated_days || "",
  };
}

export function normalizeHomeSections(rows) {
  const sections = (rows || []).map((row) => ({
    id: row.id,
    key: row.section_key,
    type: row.section_type,
    title: row.title || "",
    description: row.description || "",
    sortOrder: row.sort_order,
    config: row.config || {},
  }));
  const byType = {};
  sections.forEach((section) => {
    if (!byType[section.type]) byType[section.type] = section;
  });
  return { sections, byType };
}

export const storefrontService = {
  async settings() {
    return normalizeSettings(await publicApi.settings());
  },
  async heroSlides() {
    const rows = await publicApi.heroSlides();
    return rows.filter((row) => row.image_url).map(normalizeHeroSlide);
  },
  async homeSections() {
    return normalizeHomeSections(await publicApi.homeSections());
  },
  async deliveryAreas() {
    const rows = await publicApi.deliveryAreas();
    return rows.map(normalizeDeliveryArea);
  },
  async page(slug) {
    return normalizePage(await publicApi.page(slug));
  },
};
