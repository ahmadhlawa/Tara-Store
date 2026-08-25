from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from app.core.enums import ProductType
from app.schemas.common import APIModel, Money, UTCDateTime


# ── Categories ────────────────────────────────────────────────────────────────
class CategoryBase(APIModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    parent_id: int | None = None
    is_active: bool = True
    is_featured: bool = False
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    slug: str | None = Field(default=None, max_length=160)


class CategoryUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    slug: str | None = Field(default=None, max_length=160)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    parent_id: int | None = None
    is_active: bool | None = None
    is_featured: bool | None = None
    sort_order: int | None = None


class CategoryOut(APIModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    parent_id: int | None = None
    is_active: bool
    is_featured: bool
    sort_order: int
    product_count: int = 0


class CategoryAdminOut(CategoryOut):
    created_at: UTCDateTime
    updated_at: UTCDateTime


# ── Product sub-resources ─────────────────────────────────────────────────────
class ProductImageIn(APIModel):
    url: str = Field(min_length=1, max_length=500)
    alt_text: str | None = Field(default=None, max_length=250)
    sort_order: int = 0


class ProductImageOut(ProductImageIn):
    id: int


class ProductImageReorderIn(APIModel):
    """The product's whole image set, in the order it should be stored."""

    image_ids: list[int] = Field(min_length=1)


class ProductSpecificationIn(APIModel):
    name: str = Field(min_length=1, max_length=150)
    value: str = Field(min_length=1, max_length=500)
    sort_order: int = 0


class ProductSpecificationOut(ProductSpecificationIn):
    id: int


class ProductOptionValueIn(APIModel):
    # `id` identifies an existing row so a rename keeps the same value id, and the
    # variants pointing at it survive. Omit it for a brand-new value.
    id: int | None = None
    value: str = Field(min_length=1, max_length=150)
    sort_order: int = 0


class ProductOptionValueOut(ProductOptionValueIn):
    id: int


class ProductOptionIn(APIModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    values: list[ProductOptionValueIn] = Field(default_factory=list)


class ProductOptionOut(APIModel):
    id: int
    name: str
    sort_order: int
    values: list[ProductOptionValueOut] = Field(default_factory=list)


class ProductVariantIn(APIModel):
    title: str = Field(min_length=1, max_length=200)
    sku: str | None = Field(default=None, max_length=64)
    price_override: Money | None = None
    stock_quantity: int = Field(default=0, ge=0)
    is_active: bool = True
    option_value_ids: list[int] = Field(default_factory=list)


class ProductVariantOut(APIModel):
    id: int
    title: str
    sku: str | None = None
    price_override: Money | None = None
    stock_quantity: int
    is_active: bool
    option_value_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _flatten_option_values(cls, data: object) -> object:
        if hasattr(data, "option_values"):
            return {
                "id": data.id,
                "title": data.title,
                "sku": data.sku,
                "price_override": data.price_override,
                "stock_quantity": data.stock_quantity,
                "is_active": data.is_active,
                "option_value_ids": [v.id for v in data.option_values],
            }
        return data


class PackageItemIn(APIModel):
    included_product_id: int
    included_variant_id: int | None = None
    quantity: int = Field(default=1, gt=0)
    display_note: str | None = Field(default=None, max_length=250)
    sort_order: int = 0


class PackageItemOut(APIModel):
    id: int
    included_product_id: int
    included_product_name: str | None = None
    included_product_slug: str | None = None
    included_product_image_url: str | None = None
    included_variant_id: int | None = None
    included_variant_title: str | None = None
    quantity: int
    display_note: str | None = None
    sort_order: int


# ── Products ──────────────────────────────────────────────────────────────────
class ProductBase(APIModel):
    name: str = Field(min_length=1, max_length=250)
    category_id: int | None = None
    short_description: str | None = None
    description: str | None = None
    sku: str | None = Field(default=None, max_length=64)
    product_type: ProductType = ProductType.STANDARD
    price: Money = Field(ge=0)
    compare_at_price: Money | None = None
    cost_price: Money | None = None
    stock_quantity: int = Field(default=0, ge=0)
    track_inventory: bool = True
    low_stock_threshold: int = Field(default=3, ge=0)
    is_active: bool = True
    is_featured: bool = False
    is_new: bool = False
    is_bestseller: bool = False
    sort_order: int = 0
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None

    @model_validator(mode="after")
    def _compare_at_price_above_price(self):
        if self.compare_at_price is not None and self.price is not None:
            if self.compare_at_price <= self.price:
                raise ValueError("compare_at_price must be greater than price")
        return self


class ProductCreate(ProductBase):
    slug: str | None = Field(default=None, max_length=260)
    images: list[ProductImageIn] = Field(default_factory=list)
    specifications: list[ProductSpecificationIn] = Field(default_factory=list)


class ProductUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=250)
    slug: str | None = Field(default=None, max_length=260)
    category_id: int | None = None
    short_description: str | None = None
    description: str | None = None
    sku: str | None = Field(default=None, max_length=64)
    product_type: ProductType | None = None
    price: Money | None = Field(default=None, ge=0)
    compare_at_price: Money | None = None
    cost_price: Money | None = None
    stock_quantity: int | None = Field(default=None, ge=0)
    track_inventory: bool | None = None
    low_stock_threshold: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    is_featured: bool | None = None
    is_new: bool | None = None
    is_bestseller: bool | None = None
    sort_order: int | None = None
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None


class ProductPublicOut(APIModel):
    """Public projection: no cost price, no internal fields."""

    id: int
    name: str
    slug: str
    short_description: str | None = None
    sku: str | None = None
    product_type: ProductType
    category_id: int | None = None
    category_name: str | None = None
    category_slug: str | None = None
    price: Money
    compare_at_price: Money | None = None
    stock_quantity: int
    track_inventory: bool
    in_stock: bool
    is_featured: bool
    is_new: bool
    is_bestseller: bool
    primary_image_url: str | None = None
    # The image a card cross-fades to on hover. It rides along on the list
    # projection precisely so hovering a grid does not fire a detail request per
    # card; None when the product has only one picture.
    secondary_image_url: str | None = None
    # A catalogue card must know whether adding the product is a one-click action
    # or needs an option chosen first. The list projection deliberately omits the
    # option rows themselves, so it carries the flag instead.
    has_options: bool = False
    # A package card states how much is in the package. The list projection omits
    # the item rows, so it carries the count.
    package_item_count: int = 0


class ProductPublicDetail(ProductPublicOut):
    description: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    images: list[ProductImageOut] = Field(default_factory=list)
    specifications: list[ProductSpecificationOut] = Field(default_factory=list)
    options: list[ProductOptionOut] = Field(default_factory=list)
    variants: list[ProductVariantOut] = Field(default_factory=list)
    package_items: list[PackageItemOut] = Field(default_factory=list)


class ProductAdminOut(ProductPublicDetail):
    cost_price: Money | None = None
    is_active: bool
    low_stock_threshold: int
    sort_order: int
    created_at: UTCDateTime
    updated_at: UTCDateTime


class ProductAdminListOut(APIModel):
    id: int
    name: str
    slug: str
    sku: str | None = None
    product_type: ProductType
    category_id: int | None = None
    category_name: str | None = None
    price: Money
    compare_at_price: Money | None = None
    cost_price: Money | None = None
    stock_quantity: int
    track_inventory: bool
    low_stock_threshold: int
    is_active: bool
    is_featured: bool
    is_new: bool
    is_bestseller: bool
    sort_order: int
    primary_image_url: str | None = None
    updated_at: UTCDateTime


PRODUCT_SORTS = {
    "featured",
    "newest",
    "price-asc",
    "price-desc",
    "name",
    "sort_order",
}


def validate_sort(value: str) -> str:
    if value not in PRODUCT_SORTS:
        raise ValueError(f"sort must be one of: {', '.join(sorted(PRODUCT_SORTS))}")
    return value


class CategoryTreeOut(CategoryOut):
    children: list[CategoryOut] = Field(default_factory=list)

    @field_validator("children", mode="before")
    @classmethod
    def _default_children(cls, value: object) -> object:
        return value or []
