"""Where a media URL is actually shown, and what a batch calls the rows it owns.

Split out of `importer` because three things need the same answer and one of them is the
importer itself: the purge (which must never delete a picture that surviving content
still displays), the cutover plan (which reports that risk before anything is deleted),
and the preservation step (which promotes a row's media along with the row).

Media is referenced by **URL string**, not by foreign key — `MediaAsset` is metadata for
an uploaded object, and content rows store the public URL the object is served at. So
"is this asset still needed?" is a question about URL columns, and this module is the one
place that knows which columns those are.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Article,
    Banner,
    Category,
    Coupon,
    DeliveryArea,
    HeroSlide,
    HomeSection,
    MediaAsset,
    Product,
    ProductImage,
    StoreSettings,
)

# Entity types, in creation order. A purge walks this list backwards, so a row is never
# deleted before the rows that point at it — which is also why media comes first here and
# is therefore judged last, once the fate of everything that could display it is known.
MEDIA = "media_asset"
CATEGORY = "category"
PRODUCT = "product"
DELIVERY_AREA = "delivery_area"
HERO_SLIDE = "hero_slide"
BANNER = "banner"
HOME_SECTION = "home_section"
COUPON = "coupon"

CREATION_ORDER = (
    MEDIA,
    CATEGORY,
    PRODUCT,
    DELIVERY_AREA,
    HERO_SLIDE,
    BANNER,
    HOME_SECTION,
    COUPON,
)

MODEL_FOR_TYPE: dict[str, Any] = {
    MEDIA: MediaAsset,
    CATEGORY: Category,
    PRODUCT: Product,
    DELIVERY_AREA: DeliveryArea,
    HERO_SLIDE: HeroSlide,
    BANNER: Banner,
    HOME_SECTION: HomeSection,
    COUPON: Coupon,
}

# The field that identifies a row to a human reading a plan.
LABEL_FIELD_FOR_TYPE: dict[str, str] = {
    MEDIA: "original_filename",
    CATEGORY: "name",
    PRODUCT: "name",
    DELIVERY_AREA: "name",
    HERO_SLIDE: "title",
    BANNER: "title",
    HOME_SECTION: "title",
    COUPON: "code",
}


def label_for(entity_type: str, row: Any) -> str:
    """A human-readable name for one row, so an operator can recognise it."""
    if row is None:
        return ""
    field = LABEL_FIELD_FOR_TYPE.get(entity_type)
    value = getattr(row, field, None) if field else None
    return str(value) if value else f"#{getattr(row, 'id', '?')}"


def media_urls_of(entity_type: str, row: Any) -> list[str]:
    """Every media URL this row displays.

    Used to carry a row's pictures with it when the row is preserved: promoting a hero
    slide out of a batch without promoting the image it shows would leave the slide
    pointing at a file the purge is about to delete.
    """
    if row is None:
        return []
    if entity_type == PRODUCT:
        return [image.url for image in row.images if image.url]
    if entity_type in (CATEGORY, HERO_SLIDE, BANNER):
        return [row.image_url] if row.image_url else []
    return []


# (model, column, entity type this row belongs to for deletion purposes)
_REFERENCE_COLUMNS: tuple[tuple[Any, str, str | None], ...] = (
    (Category, "image_url", CATEGORY),
    (HeroSlide, "image_url", HERO_SLIDE),
    (Banner, "image_url", BANNER),
    # Articles, static pages and the store's own logo are owner/system content. Nothing
    # in a preview batch owns them, so they can only ever keep a picture alive.
    (Article, "featured_image_url", None),
    (StoreSettings, "logo_url", None),
    (StoreSettings, "favicon_url", None),
)


def _is_being_deleted(
    entity_type: str | None, row_id: int, deleting: Mapping[str, set[int]] | None
) -> bool:
    if entity_type is None or not deleting:
        return False
    return row_id in deleting.get(entity_type, set())


def media_reference_holders(
    db: Session, url: str | None, deleting: Mapping[str, set[int]] | None = None
) -> list[str]:
    """Identities of the rows that would still display `url` after `deleting` is applied.

    `deleting` maps an entity type to the ids about to be removed; rows in it do not
    count as holders, because they will not be there to display anything. An empty
    result means the URL is genuinely unreferenced and its asset can go.
    """
    if not url:
        return []

    holders: list[str] = []
    for model, column, entity_type in _REFERENCE_COLUMNS:
        for row in db.execute(select(model).where(getattr(model, column) == url)).scalars():
            if _is_being_deleted(entity_type, row.id, deleting):
                continue
            name = label_for(entity_type, row) if entity_type else _fallback_label(model, row)
            holders.append(f"{model.__tablename__}:{name}")

    # A product's gallery lives in its own table, so the surviving row is the *product*.
    for image in db.execute(select(ProductImage).where(ProductImage.url == url)).scalars():
        if _is_being_deleted(PRODUCT, image.product_id, deleting):
            continue
        product = db.get(Product, image.product_id)
        if product is None:
            continue
        holders.append(f"products:{product.name}")

    return sorted(set(holders))


def _fallback_label(model: Any, row: Any) -> str:
    for field in ("title", "name", "store_name"):
        value = getattr(row, field, None)
        if value:
            return str(value)
    return f"#{row.id}"
