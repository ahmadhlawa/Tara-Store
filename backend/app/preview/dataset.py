"""The preview dataset document: parsing, validation and hashing.

Same shape of contract as `app.instance.profile` — a strict pydantic model over YAML,
extra keys forbidden, credential-shaped keys rejected before validation runs. A preview
dataset is committed to the repository, so it is non-secret by construction.

Every content item carries an `origin`, and that is the point of this file: a reader can
always tell which rows came from something actually visible on the client's own public
pages and which are plausible filler invented to make the storefront look inhabited.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.enums import DiscountType, HomeSectionType, ProductType
from app.instance.profile import ProfileError, assert_no_secret_like_keys

SUPPORTED_PREVIEW_SCHEMA_VERSIONS = frozenset({1})

SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,78}[a-z0-9])?$")
PREFIX_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*/$")

# What an item's provenance is. Nothing else is accepted, so a dataset cannot quietly
# present invented content as observed fact.
Origin = Literal["confirmed", "inferred", "placeholder"]

TONE_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class DatasetError(ValueError):
    """A preview dataset is unreadable, malformed or semantically invalid."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _slug(value: str) -> str:
    if not SLUG_RE.match(value):
        raise ValueError(f"{value!r} is not a valid slug: lowercase letters, digits and hyphens")
    return value


class PreviewMedia(_Strict):
    """One image the dataset can point at.

    Two kinds, and a media entry is exactly one of them:

    * **generated** — a placeholder built from `start_color`/`end_color` and uploaded
      through the storage provider. The batch owns the resulting `MediaAsset` and a
      purge deletes both the row and the stored object.
    * **library** — `library_filename` names a file the owner has *already* uploaded
      to the Media Library. The importer only looks it up; it never uploads, never
      creates a `MediaAsset`, and never takes ownership, so a purge cannot delete the
      owner's own picture. This is what a real client catalog uses.
    """

    key: str
    alt_text: str = Field(default="", max_length=250)
    shape: Literal["tile", "wide", "square"] = "tile"
    start_color: str | None = None
    end_color: str | None = None
    # The `original_filename` of an existing MediaAsset. Never a URL, never a storage
    # key: the spreadsheet contract stays provider-agnostic, and resolution happens
    # against the Media Library at import time.
    library_filename: str | None = Field(default=None, max_length=300)
    artwork_version: str = Field(default="v1", pattern=r"^v[1-9][0-9]*$")
    origin: Origin = "placeholder"
    source_url: str | None = Field(default=None, max_length=500)

    @field_validator("key")
    @classmethod
    def _check_key(cls, value: str) -> str:
        return _slug(value)

    @field_validator("start_color", "end_color")
    @classmethod
    def _check_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not TONE_RE.match(value):
            raise ValueError(f"{value!r} is not a #RRGGBB colour")
        return value.upper()

    @property
    def is_library(self) -> bool:
        return self.library_filename is not None

    def model_post_init(self, _context: Any) -> None:
        if self.library_filename is not None:
            if self.start_color or self.end_color:
                raise ValueError(
                    f"media {self.key!r}: a library_filename names an already uploaded file, "
                    "so it cannot also carry placeholder colours"
                )
            return
        if not (self.start_color and self.end_color):
            raise ValueError(
                f"media {self.key!r}: needs either start_color and end_color (a generated "
                "placeholder) or library_filename (an existing Media Library file)"
            )


class PreviewCategory(_Strict):
    slug: str = Field(max_length=160)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    image: str | None = None
    parent: str | None = Field(default=None, max_length=160)
    is_active: bool = True
    is_featured: bool = False
    sort_order: int = 0
    origin: Origin
    source_note: str | None = Field(default=None, max_length=300)

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, value: str) -> str:
        return _slug(value)

    @field_validator("parent")
    @classmethod
    def _check_parent(cls, value: str | None) -> str | None:
        return None if value is None else _slug(value)


class PreviewSpecification(_Strict):
    name: str = Field(max_length=150)
    value: str = Field(max_length=500)


class PreviewOption(_Strict):
    """A choice axis (colour, size…) and the values offered for it.

    Values only. A priced variant matrix is deliberately not expressible here — see
    `docs/catalog-spreadsheet-preparation.md`.
    """

    name: str = Field(min_length=1, max_length=100)
    values: list[str] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def _check_values(cls, value: list[str]) -> list[str]:
        cleaned = [entry.strip() for entry in value]
        if any(not entry for entry in cleaned):
            raise ValueError("option values must not be blank")
        if any(len(entry) > 150 for entry in cleaned):
            raise ValueError("an option value is longer than 150 characters")
        duplicates = sorted({v for v in cleaned if cleaned.count(v) > 1})
        if duplicates:
            raise ValueError(f"duplicate option value(s): {duplicates}")
        return cleaned


class PreviewPackageItem(_Strict):
    product: str
    quantity: int = Field(default=1, ge=1)
    display_note: str | None = Field(default=None, max_length=250)


class PreviewProduct(_Strict):
    slug: str = Field(max_length=260)
    name: str = Field(min_length=1, max_length=250)
    category: str
    sku: str | None = Field(default=None, max_length=64)
    product_type: str = ProductType.STANDARD.value
    price: Decimal
    compare_at_price: Decimal | None = None
    cost_price: Decimal | None = None
    stock_quantity: int = Field(default=0, ge=0)
    track_inventory: bool = True
    low_stock_threshold: int = Field(default=3, ge=0)
    is_active: bool = True
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None
    short_description: str | None = None
    description: str | None = None
    # The ordered gallery. When present it is the whole truth about this product's
    # pictures: `images[0]` is the cover, and the order here becomes `sort_order`.
    # `image`/`secondary_image` remain for datasets written before galleries existed.
    images: list[str] = Field(default_factory=list)
    image: str | None = None
    # The picture a catalogue card cross-fades to on hover. Optional by design: a
    # product without one keeps its cover and simply reveals its action panel,
    # which is the fallback the cards have to handle anyway.
    secondary_image: str | None = None
    is_featured: bool = False
    is_new: bool = False
    is_bestseller: bool = False
    sort_order: int = 0
    origin: Origin
    source_note: str | None = Field(default=None, max_length=300)
    specifications: list[PreviewSpecification] = Field(default_factory=list)
    options: list[PreviewOption] = Field(default_factory=list)
    package_items: list[PreviewPackageItem] = Field(default_factory=list)

    @property
    def gallery(self) -> list[str]:
        """Every media key this product shows, cover first, without repeats."""
        if self.images:
            ordered = self.images
        else:
            ordered = [key for key in (self.image, self.secondary_image) if key]
        seen: list[str] = []
        for key in ordered:
            if key not in seen:
                seen.append(key)
        return seen

    @field_validator("options")
    @classmethod
    def _check_options(cls, value: list[PreviewOption]) -> list[PreviewOption]:
        names = [option.name for option in value]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"duplicate option name(s): {duplicates}")
        return value

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, value: str) -> str:
        return _slug(value)

    @field_validator("product_type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        allowed = {member.value for member in ProductType}
        if value not in allowed:
            raise ValueError(f"unknown product type {value!r}; allowed: {sorted(allowed)}")
        return value

    @field_validator("price")
    @classmethod
    def _check_price(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("price must be greater than zero")
        return value


class PreviewDeliveryArea(_Strict):
    key: str
    name: str = Field(min_length=1, max_length=150)
    delivery_fee: Decimal = Field(ge=0)
    min_order_amount: Decimal | None = None
    free_delivery_threshold: Decimal | None = None
    estimated_days: str | None = Field(default=None, max_length=100)
    sort_order: int = 0
    origin: Origin

    @field_validator("key")
    @classmethod
    def _check_key(cls, value: str) -> str:
        return _slug(value)


class PreviewHeroSlide(_Strict):
    key: str
    title: str = Field(min_length=1, max_length=250)
    subtitle: str | None = Field(default=None, max_length=250)
    description: str | None = None
    button_label: str | None = Field(default=None, max_length=100)
    button_url: str | None = Field(default=None, max_length=500)
    image: str | None = None
    image_url: str | None = Field(default=None, max_length=500, pattern=r"^/[^\\s]*$")
    sort_order: int = 0
    origin: Origin

    @field_validator("key")
    @classmethod
    def _check_key(cls, value: str) -> str:
        return _slug(value)


class PreviewHomeSection(_Strict):
    key: str = Field(max_length=64)
    section_type: str
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    sort_order: int = 0
    is_visible: bool = True

    @field_validator("section_type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        allowed = {member.value for member in HomeSectionType}
        if value not in allowed:
            raise ValueError(f"unknown home section type {value!r}; allowed: {sorted(allowed)}")
        return value


class PreviewCoupon(_Strict):
    code: str = Field(min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=250)
    discount_type: str = DiscountType.PERCENTAGE.value
    discount_value: Decimal = Field(gt=0)
    min_order_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    max_discount_amount: Decimal | None = None
    usage_limit: int | None = None
    origin: Origin = "placeholder"

    @field_validator("discount_type")
    @classmethod
    def _check_discount_type(cls, value: str) -> str:
        allowed = {member.value for member in DiscountType}
        if value not in allowed:
            raise ValueError(f"unknown discount type {value!r}; allowed: {sorted(allowed)}")
        return value


class PreviewDataset(_Strict):
    """The whole preview document."""

    preview_schema_version: int
    batch_key: str = Field(max_length=64)
    source_label: str = Field(max_length=250)
    media_prefix: str = Field(max_length=200)
    notice: str | None = Field(default=None, max_length=300)

    media: list[PreviewMedia] = Field(default_factory=list)
    categories: list[PreviewCategory] = Field(default_factory=list)
    products: list[PreviewProduct] = Field(default_factory=list)
    delivery_areas: list[PreviewDeliveryArea] = Field(default_factory=list)
    hero_slides: list[PreviewHeroSlide] = Field(default_factory=list)
    home_sections: list[PreviewHomeSection] = Field(default_factory=list)
    coupons: list[PreviewCoupon] = Field(default_factory=list)

    @field_validator("preview_schema_version")
    @classmethod
    def _check_schema_version(cls, value: int) -> int:
        if value not in SUPPORTED_PREVIEW_SCHEMA_VERSIONS:
            raise ValueError(
                f"preview_schema_version {value} is not supported; this build understands "
                f"{sorted(SUPPORTED_PREVIEW_SCHEMA_VERSIONS)}"
            )
        return value

    @field_validator("batch_key")
    @classmethod
    def _check_batch_key(cls, value: str) -> str:
        return _slug(value)

    @field_validator("media_prefix")
    @classmethod
    def _check_prefix(cls, value: str) -> str:
        """A prefix must be relative, trailing-slashed, and free of traversal.

        The purge path refuses to touch any object outside this prefix, so a prefix that
        could escape it would defeat the only containment the batch has.
        """
        if not PREFIX_RE.match(value):
            raise ValueError(
                f"{value!r} is not a valid object prefix: lowercase, relative, and ending in '/'"
            )
        if ".." in value or "//" in value:
            raise ValueError(f"{value!r} must not contain '..' or an empty path segment")
        return value

    def model_post_init(self, _context: Any) -> None:
        self._check_unique()
        self._check_references()

    def _check_unique(self) -> None:
        for label, keys in (
            ("media key", [item.key for item in self.media]),
            ("category slug", [item.slug for item in self.categories]),
            ("product slug", [item.slug for item in self.products]),
            ("delivery area key", [item.key for item in self.delivery_areas]),
            ("hero slide key", [item.key for item in self.hero_slides]),
            ("home section key", [item.key for item in self.home_sections]),
            ("coupon code", [item.code for item in self.coupons]),
        ):
            duplicates = sorted({key for key in keys if keys.count(key) > 1})
            if duplicates:
                raise ValueError(f"duplicate {label}(s): {duplicates}")

        # `products.sku` is unique in the database, so a dataset carrying the same SKU
        # twice would fail on insert halfway through a seed.
        skus = [item.sku for item in self.products if item.sku]
        repeated = sorted({sku for sku in skus if skus.count(sku) > 1})
        if repeated:
            raise ValueError(f"duplicate product sku(s): {repeated}")

        library = [item.library_filename for item in self.media if item.library_filename]
        shared = sorted({name for name in library if library.count(name) > 1})
        if shared:
            raise ValueError(f"duplicate media library_filename(s): {shared}")

    def _check_references(self) -> None:
        media_keys = {item.key for item in self.media}
        category_slugs = {item.slug for item in self.categories}
        product_slugs = {item.slug for item in self.products}

        def check_image(owner: str, image: str | None) -> None:
            if image is not None and image not in media_keys:
                raise ValueError(f"{owner} references unknown media key {image!r}")

        for category in self.categories:
            check_image(f"category {category.slug!r}", category.image)
            if category.parent is not None:
                if category.parent == category.slug:
                    raise ValueError(f"category {category.slug!r} cannot be its own parent")
                if category.parent not in category_slugs:
                    raise ValueError(
                        f"category {category.slug!r} references unknown parent "
                        f"{category.parent!r}"
                    )
        for slide in self.hero_slides:
            check_image(f"hero slide {slide.key!r}", slide.image)

        self._check_category_cycles()

        for product in self.products:
            check_image(f"product {product.slug!r}", product.image)
            check_image(f"product {product.slug!r} (secondary)", product.secondary_image)
            for position, key in enumerate(product.images, start=1):
                check_image(f"product {product.slug!r} image {position}", key)
            if product.images and (product.image or product.secondary_image):
                raise ValueError(
                    f"product {product.slug!r} sets both `images` and `image`/`secondary_image`; "
                    "a product has one gallery, so use `images` alone"
                )
            if len(set(product.images)) != len(product.images):
                raise ValueError(f"product {product.slug!r} lists the same image twice")
            if product.secondary_image is not None and product.image is None:
                raise ValueError(
                    f"product {product.slug!r} has a secondary_image but no image; "
                    "the second picture is what a card swaps to, so there must be a cover"
                )
            if product.category not in category_slugs:
                raise ValueError(
                    f"product {product.slug!r} references unknown category {product.category!r}"
                )
            if product.compare_at_price is not None and product.compare_at_price <= product.price:
                raise ValueError(
                    f"product {product.slug!r}: compare_at_price must be above price, "
                    "otherwise the storefront would advertise a discount that is not one"
                )
            if product.package_items and product.product_type != ProductType.PACKAGE.value:
                raise ValueError(
                    f"product {product.slug!r} has package items but is not a package"
                )
            if product.product_type == ProductType.PACKAGE.value and not product.package_items:
                raise ValueError(f"package {product.slug!r} has no package items")
            for item in product.package_items:
                if item.product not in product_slugs:
                    raise ValueError(
                        f"package {product.slug!r} includes unknown product {item.product!r}"
                    )
                if item.product == product.slug:
                    raise ValueError(f"package {product.slug!r} cannot include itself")

    def _check_category_cycles(self) -> None:
        """No category may be its own ancestor: the seed walks parents to write them."""
        parent_of = {item.slug: item.parent for item in self.categories}
        for slug in parent_of:
            seen = {slug}
            current = parent_of[slug]
            while current is not None:
                if current in seen:
                    raise ValueError(f"category parent cycle involving {slug!r}")
                seen.add(current)
                current = parent_of.get(current)

    def canonical_document(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def dataset_hash(self) -> str:
        return hashlib.sha256(self.canonical_document().encode("utf-8")).hexdigest()

    def counts(self) -> dict[str, int]:
        return {
            "media": len(self.media),
            "categories": len(self.categories),
            "products": len(self.products),
            "delivery_areas": len(self.delivery_areas),
            "hero_slides": len(self.hero_slides),
            "home_sections": len(self.home_sections),
            "coupons": len(self.coupons),
        }

    def origin_counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for group in (
            self.media,
            self.categories,
            self.products,
            self.delivery_areas,
            self.hero_slides,
            self.coupons,
        ):
            for item in group:
                origin = getattr(item, "origin")
                result[origin] = result.get(origin, 0) + 1
        return result


def parse_dataset(data: Any, *, source: str = "<memory>") -> PreviewDataset:
    if not isinstance(data, dict):
        raise DatasetError(f"{source}: preview dataset must be a YAML mapping at the top level.")
    try:
        # Same rule as an instance profile: this file is committed, so a
        # credential-shaped key is rejected before anything else is even looked at.
        assert_no_secret_like_keys(data)
    except ProfileError as exc:
        raise DatasetError(f"{source}: {exc}") from exc
    try:
        return PreviewDataset.model_validate(data)
    except ValidationError as exc:
        details = "\n".join(
            f"  - {'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
            for err in exc.errors()
        )
        raise DatasetError(f"{source}: invalid preview dataset\n{details}") from exc


def load_dataset(path: str | Path) -> PreviewDataset:
    file_path = Path(path)
    if not file_path.is_file():
        raise DatasetError(f"Preview dataset not found: {file_path}")
    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DatasetError(f"{file_path}: not valid YAML — {exc}") from exc
    if raw is None:
        raise DatasetError(f"{file_path}: preview dataset is empty.")
    return parse_dataset(raw, source=str(file_path))
