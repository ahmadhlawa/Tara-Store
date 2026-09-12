"""Catalog querying and product serialisation shared by the public and admin APIs."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.orm import Session, load_only, selectinload

from app.core.enums import ProductType
from app.models import Category, PackageItem, Product, ProductImage, ProductOption, ProductVariant

_TASHKEEL = re.compile(r"[ً-ْـ]")
_ALEF = re.compile(r"[أإآ]")


def normalize_arabic(text: str) -> str:
    """Fold Arabic orthographic variants so search matches how people actually type."""
    value = unicodedata.normalize("NFKC", text or "").strip().lower()
    value = _TASHKEEL.sub("", value)
    value = _ALEF.sub("ا", value)
    value = value.replace("ى", "ي").replace("ؤ", "و")
    value = value.replace("ئ", "ي").replace("ة", "ه")
    return re.sub(r"\s+", " ", value)


def refresh_search_text(product: Product) -> None:
    """Keep `Product.search_text` in step with the fields users search by."""
    parts = [product.name or "", product.sku or "", product.short_description or ""]
    product.search_text = normalize_arabic(" ".join(parts))[:800]


def product_detail_loaders():
    return (
        selectinload(Product.images),
        selectinload(Product.specifications),
        selectinload(Product.options),
        selectinload(Product.variants),
        selectinload(Product.package_items).selectinload(PackageItem.included_product),
        selectinload(Product.category),
    )


def product_detail_query(*, active_only: bool) -> Select:
    stmt = select(Product).options(*product_detail_loaders())
    if active_only:
        stmt = stmt.where(Product.is_active.is_(True))
    return stmt


def product_list_query(*, active_only: bool, public: bool = True) -> Select:
    """Load only relationships required by compact list serializers.

    Select-in loaders keep query count constant as the page grows. Public cards need
    two image URLs plus option/package presence; Admin rows need only their cover.
    """
    loaders = [
        selectinload(Product.images).load_only(ProductImage.url, ProductImage.sort_order),
        selectinload(Product.category).load_only(Category.name, Category.slug),
    ]
    if public:
        loaders.extend(
            [
                selectinload(Product.options).load_only(ProductOption.id),
                selectinload(Product.variants),
                selectinload(Product.package_items).load_only(PackageItem.id),
            ]
        )
    stmt = select(Product).options(*loaders)
    if active_only:
        stmt = stmt.where(Product.is_active.is_(True))
    return stmt


def apply_product_filters(
    stmt: Select,
    *,
    q: str | None = None,
    category_slug: str | None = None,
    category_id: int | None = None,
    product_type: str | None = None,
    is_featured: bool | None = None,
    is_new: bool | None = None,
    is_bestseller: bool | None = None,
    on_sale: bool | None = None,
    in_stock: bool | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    is_active: bool | None = None,
) -> Select:
    if q:
        needle = f"%{normalize_arabic(q)}%"
        stmt = stmt.where(Product.search_text.like(needle))
    if category_slug:
        hierarchy = select(Category.id).where(
            Category.slug == category_slug, Category.is_active.is_(True)
        ).cte(name="category_hierarchy", recursive=True)
        child = Category.__table__.alias("category_child")
        hierarchy = hierarchy.union(
            select(child.c.id).where(
                child.c.parent_id == hierarchy.c.id,
                child.c.is_active.is_(True),
            )
        )
        stmt = stmt.where(Product.category_id.in_(select(hierarchy.c.id)))
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if product_type:
        stmt = stmt.where(Product.product_type == product_type)
    if is_featured is not None:
        stmt = stmt.where(Product.is_featured.is_(is_featured))
    if is_new is not None:
        stmt = stmt.where(Product.is_new.is_(is_new))
    if is_bestseller is not None:
        stmt = stmt.where(Product.is_bestseller.is_(is_bestseller))
    if on_sale:
        stmt = stmt.where(
            Product.compare_at_price.is_not(None), Product.compare_at_price > Product.price
        )
    if in_stock:
        stmt = stmt.where(publicly_available_condition())
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if is_active is not None:
        stmt = stmt.where(Product.is_active.is_(is_active))
    return stmt


_SORTS = {
    "featured": (Product.is_featured.desc(), Product.sort_order.asc(), Product.id.desc()),
    "newest": (Product.is_new.desc(), Product.created_at.desc(), Product.id.desc()),
    "price-asc": (Product.price.asc(), Product.id.asc()),
    "price-desc": (Product.price.desc(), Product.id.asc()),
    "name": (Product.name.asc(),),
    "sort_order": (Product.sort_order.asc(), Product.id.asc()),
}


def apply_product_sort(stmt: Select, sort: str) -> Select:
    return stmt.order_by(*_SORTS.get(sort, _SORTS["featured"]))


def count_query(stmt: Select) -> Select:
    return select(func.count()).select_from(stmt.order_by(None).subquery())


def paginate(db: Session, stmt: Select, *, offset: int, limit: int) -> tuple[list[Any], int]:
    total = int(db.execute(count_query(stmt)).scalar_one())
    rows = db.execute(stmt.offset(offset).limit(limit)).scalars().unique().all()
    return list(rows), total


def publicly_available_condition():
    active_variant = exists(select(ProductVariant.id).where(
        ProductVariant.product_id == Product.id, ProductVariant.is_active.is_(True)
    ))
    stocked_variant = exists(select(ProductVariant.id).where(
        ProductVariant.product_id == Product.id,
        ProductVariant.is_active.is_(True),
        ProductVariant.stock_quantity > 0,
    ))
    return or_(
        Product.track_inventory.is_(False),
        stocked_variant,
        and_(~active_variant, Product.stock_quantity > 0),
    )


def in_stock(product: Product) -> bool:
    if not product.track_inventory:
        return True
    active_variants = [variant for variant in product.variants if variant.is_active]
    return any(variant.stock_quantity > 0 for variant in active_variants) if active_variants else product.stock_quantity > 0


def product_payload(product: Product, *, include_relations: bool) -> dict[str, Any]:
    """Flatten a Product into the shape the API schemas expect."""
    payload: dict[str, Any] = {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "short_description": product.short_description,
        "sku": product.sku,
        "product_type": product.product_type,
        "category_id": product.category_id,
        "category_name": product.category.name if product.category else None,
        "category_slug": product.category.slug if product.category else None,
        "price": product.price,
        "compare_at_price": product.compare_at_price,
        "stock_quantity": product.stock_quantity,
        "track_inventory": product.track_inventory,
        "in_stock": in_stock(product),
        "is_featured": product.is_featured,
        "is_new": product.is_new,
        "is_bestseller": product.is_bestseller,
        "primary_image_url": product.primary_image_url,
        "secondary_image_url": product.secondary_image_url,
        "has_options": bool(product.options),
        "package_item_count": len(product.package_items),
    }
    if not include_relations:
        return payload

    payload.update(
        {
            "description": product.description,
            "seo_title": product.seo_title,
            "seo_description": product.seo_description,
            "images": product.images,
            "specifications": product.specifications,
            "options": product.options,
            "variants": product.variants,
            "package_items": [
                {
                    "id": item.id,
                    "included_product_id": item.included_product_id,
                    "included_product_name": item.included_product.name
                    if item.included_product
                    else None,
                    "included_product_slug": item.included_product.slug
                    if item.included_product
                    else None,
                    "included_product_image_url": item.included_product.primary_image_url
                    if item.included_product
                    else None,
                    "quantity": item.quantity,
                    "display_note": item.display_note,
                    "sort_order": item.sort_order,
                }
                for item in product.package_items
            ],
        }
    )
    return payload


def admin_product_payload(product: Product) -> dict[str, Any]:
    payload = product_payload(product, include_relations=True)
    payload.update(
        {
            "cost_price": product.cost_price,
            "is_active": product.is_active,
            "low_stock_threshold": product.low_stock_threshold,
            "sort_order": product.sort_order,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
        }
    )
    return payload


def admin_product_list_payload(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "sku": product.sku,
        "product_type": product.product_type,
        "category_id": product.category_id,
        "category_name": product.category.name if product.category else None,
        "price": product.price,
        "compare_at_price": product.compare_at_price,
        "cost_price": product.cost_price,
        "stock_quantity": product.stock_quantity,
        "track_inventory": product.track_inventory,
        "low_stock_threshold": product.low_stock_threshold,
        "is_active": product.is_active,
        "is_featured": product.is_featured,
        "is_new": product.is_new,
        "is_bestseller": product.is_bestseller,
        "sort_order": product.sort_order,
        "primary_image_url": product.primary_image_url,
        "updated_at": product.updated_at,
    }


def category_payload(category: Category, product_count: int = 0) -> dict[str, Any]:
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "image_url": category.image_url,
        "parent_id": category.parent_id,
        "is_active": category.is_active,
        "is_featured": category.is_featured,
        "show_on_home": category.show_on_home,
        "sort_order": category.sort_order,
        "product_count": product_count,
    }


def product_counts_by_category(db: Session, *, active_only: bool) -> dict[int, int]:
    stmt = select(Product.category_id, func.count(Product.id)).group_by(Product.category_id)
    if active_only:
        stmt = stmt.join(Category, Product.category_id == Category.id).where(
            Product.is_active.is_(True), Category.is_active.is_(True),
            publicly_available_condition(),
        )
    direct = {row[0]: row[1] for row in db.execute(stmt) if row[0] is not None}
    category_stmt = select(Category.id, Category.parent_id)
    if active_only:
        category_stmt = category_stmt.where(Category.is_active.is_(True))
    parents = dict(db.execute(category_stmt).all())
    totals = dict(direct)
    for category_id, count in direct.items():
        parent_id = parents.get(category_id)
        visited = {category_id}
        while parent_id is not None and parent_id not in visited:
            visited.add(parent_id)
            totals[parent_id] = totals.get(parent_id, 0) + count
            parent_id = parents.get(parent_id)
    return totals


def assert_package_is_valid(db: Session, package: Product, included_product_id: int) -> Product:
    """A package cannot contain itself, and cannot contain another package."""
    from app.services.errors import DomainError, NotFoundError

    if package.product_type != ProductType.PACKAGE.value:
        raise DomainError(
            "يمكن إضافة محتويات للبكجات فقط.", code="not_a_package"
        )
    if included_product_id == package.id:
        raise DomainError("لا يمكن أن يحتوي البكج على نفسه.", code="package_self_reference")
    included = db.get(Product, included_product_id)
    if included is None:
        raise NotFoundError("المنتج المضاف غير موجود.", code="product_not_found")
    if included.product_type == ProductType.PACKAGE.value:
        raise DomainError(
            "لا يمكن أن يحتوي البكج على بكج آخر.", code="package_nested"
        )
    return included
