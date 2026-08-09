from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ProductType
from app.db.base import Base, TimestampMixin


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    parent: Mapped["Category | None"] = relationship(remote_side="Category.id", back_populates="children")
    children: Mapped[list["Category"]] = relationship(
        back_populates="parent", cascade="save-update, merge"
    )
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(250), nullable=False)
    slug: Mapped[str] = mapped_column(String(260), unique=True, index=True, nullable=False)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    product_type: Mapped[str] = mapped_column(
        String(32), default=ProductType.STANDARD.value, nullable=False, index=True
    )

    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_bestseller: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    seo_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Arabic-normalised copy of the searchable text, refreshed on every write so
    # `LIKE` matching is independent of hamza/ta-marbuta spelling.
    search_text: Mapped[str] = mapped_column(String(800), default="", nullable=False)

    category: Mapped[Category | None] = relationship(back_populates="products")
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order, ProductImage.id",
    )
    specifications: Mapped[list["ProductSpecification"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductSpecification.sort_order",
    )
    options: Mapped[list["ProductOption"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductOption.sort_order",
    )
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductVariant.id",
    )
    package_items: Mapped[list["PackageItem"]] = relationship(
        back_populates="package",
        foreign_keys="PackageItem.package_product_id",
        cascade="all, delete-orphan",
        order_by="PackageItem.sort_order",
    )

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_non_negative"),
    )

    @property
    def primary_image_url(self) -> str | None:
        # Image order is the single source of truth: the first ordered image is
        # the cover. There is no separate primary flag to fall out of sync.
        return self.images[0].url if self.images else None

    @property
    def secondary_image_url(self) -> str | None:
        """The next image after the cover, or None.

        A catalogue card swaps to this on hover. Carrying it on the list
        projection is what keeps that swap from costing a product-detail request
        per card. Images that merely repeat the cover URL are skipped, so a
        product with one picture uploaded twice still reports no second image.
        """
        cover = self.primary_image_url
        if cover is None:
            return None
        return next((image.url for image in self.images if image.url != cover), None)


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(250), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Legacy column kept so the ORM still matches the existing table. Nothing
    # reads it any more — `sort_order` alone decides which image is the cover.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    product: Mapped[Product] = relationship(back_populates="images")


class ProductSpecification(Base):
    __tablename__ = "product_specifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    product: Mapped[Product] = relationship(back_populates="specifications")


class ProductOption(Base):
    """A choice axis for a product: colour, size, scent, mold dimensions..."""

    __tablename__ = "product_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    product: Mapped[Product] = relationship(back_populates="options")
    values: Mapped[list["ProductOptionValue"]] = relationship(
        back_populates="option",
        cascade="all, delete-orphan",
        order_by="ProductOptionValue.sort_order",
    )

    __table_args__ = (UniqueConstraint("product_id", "name", name="uq_product_option_name"),)


class ProductOptionValue(Base):
    __tablename__ = "product_option_values"

    id: Mapped[int] = mapped_column(primary_key=True)
    option_id: Mapped[int] = mapped_column(
        ForeignKey("product_options.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(String(150), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    option: Mapped[ProductOption] = relationship(back_populates="values")


class ProductVariantOptionValue(Base):
    """Join row: which option values a variant is made of."""

    __tablename__ = "product_variant_option_values"

    variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), primary_key=True
    )
    option_value_id: Mapped[int] = mapped_column(
        ForeignKey("product_option_values.id", ondelete="CASCADE"), primary_key=True
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    price_override: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product: Mapped[Product] = relationship(back_populates="variants")
    option_values: Mapped[list[ProductOptionValue]] = relationship(
        secondary="product_variant_option_values", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_variants_stock_non_negative"),
    )


class PackageItem(Base):
    """A product included in a package (a Product with product_type='package')."""

    __tablename__ = "package_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    package_product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    included_product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    display_note: Mapped[str | None] = mapped_column(String(250), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    package: Mapped[Product] = relationship(
        back_populates="package_items", foreign_keys=[package_product_id]
    )
    included_product: Mapped[Product] = relationship(foreign_keys=[included_product_id])

    __table_args__ = (
        UniqueConstraint(
            "package_product_id", "included_product_id", name="uq_package_item_product"
        ),
        CheckConstraint(
            "package_product_id <> included_product_id", name="ck_package_item_not_self"
        ),
        CheckConstraint("quantity > 0", name="ck_package_item_quantity_positive"),
    )
