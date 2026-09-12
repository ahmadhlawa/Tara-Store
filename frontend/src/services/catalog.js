// Translates API payloads into the shape the storefront components expect.
// The design speaks of `price` (struck through) and `sale`; the API speaks of
// `price` (what is charged) and `compare_at_price` (the reference price).
import { publicApi } from "../api/publicApi.js";
import { backgroundFor, galleryFor } from "../utils/placeholder.js";

export function normalizeProduct(raw) {
  if (!raw) return null;
  const hasCompare = raw.compare_at_price != null && raw.compare_at_price > raw.price;
  const seed = raw.category_slug || raw.slug;
  return {
    id: raw.id,
    slug: raw.slug,
    name: raw.name,
    productType: raw.product_type,
    categoryId: raw.category_id ?? null,
    categoryName: raw.category_name || "",
    categorySlug: raw.category_slug || "",
    // list price (struck through) and the discounted price actually charged
    price: hasCompare ? Number(raw.compare_at_price) : Number(raw.price),
    sale: hasCompare ? Number(raw.price) : null,
    sku: raw.sku || "",
    stock: raw.stock_quantity ?? 0,
    trackInventory: raw.track_inventory !== false,
    inStock: raw.in_stock !== false,
    isNew: !!raw.is_new,
    featured: !!raw.is_featured,
    bestSeller: !!raw.is_bestseller,
    short: raw.short_description || "",
    description: raw.description || "",
    seoTitle: raw.seo_title || "",
    seoDescription: raw.seo_description || "",
    imageUrl: raw.primary_image_url || null,
    // Present on the list projection too, so a card can cross-fade to it on
    // hover without fetching the product's detail payload.
    secondaryImageUrl: raw.secondary_image_url || null,
    bg: backgroundFor(raw.primary_image_url, seed),
    gallery: galleryFor(raw.images, seed),
    images: raw.images || [],
    specs: (raw.specifications || []).map((spec) => [spec.name, spec.value]),
    options: raw.options || [],
    variants: raw.variants || [],
    // Present on both projections: the list payload omits the option rows, so a
    // card relies on the flag alone to decide direct-add vs. choose-an-option.
    hasOptions: !!raw.has_options || (raw.options || []).length > 0,
    packageItemCount: raw.package_item_count ?? (raw.package_items || []).length,
    packageItems: (raw.package_items || []).map((item) => ({
      id: item.id,
      productId: item.included_product_id,
      label: item.display_note || item.included_product_name || "",
      slug: item.included_product_slug || "",
      quantity: item.quantity,
      bg: backgroundFor(item.included_product_image_url, item.included_product_slug || item.id),
    })),
  };
}

export function normalizeCategory(raw) {
  if (!raw) return null;
  return {
    id: raw.id,
    slug: raw.slug,
    name: raw.name,
    description: raw.description || "",
    imageUrl: raw.image_url || null,
    bg: backgroundFor(raw.image_url, raw.slug),
    featured: !!raw.is_featured,
    showOnHome: !!raw.show_on_home,
    count: raw.product_count ?? 0,
    children: (raw.children || []).map(normalizeCategory),
  };
}

const page = (response) => ({
  items: (response?.items || []).map(normalizeProduct),
  total: response?.total ?? 0,
  pages: response?.pages ?? 0,
  page: response?.page ?? 1,
});

export const catalogService = {
  async list(params) {
    return page(await publicApi.products(params));
  },
  async bySlug(slug) {
    return normalizeProduct(await publicApi.product(slug));
  },
  async related(slug, limit = 4) {
    const rows = await publicApi.relatedProducts(slug, limit);
    return rows.map(normalizeProduct);
  },
  async categories() {
    const rows = await publicApi.categories();
    return rows.filter((row) => row.is_active !== false).map(normalizeCategory);
  },
  async category(slug) {
    return normalizeCategory(await publicApi.category(slug));
  },
  async featured(limit = 8) {
    return page(await publicApi.featuredProducts({ page_size: limit }));
  },
  async newest(limit = 8) {
    return page(await publicApi.newProducts({ page_size: limit }));
  },
  async bestsellers(limit = 8) {
    return page(await publicApi.bestsellers({ page_size: limit }));
  },
  async packages(params) {
    return page(await publicApi.packages(params));
  },
  async molds(params) {
    return page(await publicApi.molds(params));
  },
};
