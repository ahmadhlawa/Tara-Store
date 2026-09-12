"""Public catalog reads. Only active content, never cost price."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbSession, PageParams
from app.core.enums import ProductType
from app.models import Category, Product
from app.schemas.catalog import (
    CategoryOut,
    CategoryTreeOut,
    ProductPublicDetail,
    ProductPublicOut,
)
from app.schemas.common import Page
from app.services import catalog as catalog_service

router = APIRouter(tags=["public-catalog"])

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "not_found", "message": "العنصر غير موجود."},
)


@router.get("/categories", response_model=list[CategoryTreeOut])
def list_categories(db: DbSession, featured_only: bool = False) -> list[dict]:
    stmt = select(Category).where(Category.is_active.is_(True))
    if featured_only:
        stmt = stmt.where(Category.is_featured.is_(True))
    stmt = stmt.order_by(Category.sort_order.asc(), Category.id.asc())
    categories = list(db.execute(stmt).scalars().all())
    counts = catalog_service.product_counts_by_category(db, active_only=True)

    by_parent: dict[int | None, list[Category]] = {}
    for category in categories:
        by_parent.setdefault(category.parent_id, []).append(category)

    def tree(category: Category) -> dict:
        return {
            **catalog_service.category_payload(category, counts.get(category.id, 0)),
            "children": [tree(child) for child in by_parent.get(category.id, [])],
        }

    return [tree(category) for category in by_parent.get(None, [])]


@router.get("/categories/{slug}", response_model=CategoryOut)
def get_category(slug: str, db: DbSession) -> dict:
    category = db.execute(
        select(Category).where(Category.slug == slug, Category.is_active.is_(True))
    ).scalar_one_or_none()
    if category is None:
        raise _NOT_FOUND
    counts = catalog_service.product_counts_by_category(db, active_only=True)
    return catalog_service.category_payload(category, counts.get(category.id, 0))


def _product_page(
    db: DbSession,
    pagination,
    *,
    sort: str = "featured",
    **filters,
) -> Page[ProductPublicOut]:
    filters["in_stock"] = True
    stmt = catalog_service.apply_product_filters(
        catalog_service.product_list_query(active_only=True), **filters
    )
    stmt = catalog_service.apply_product_sort(stmt, sort)
    rows, total = catalog_service.paginate(
        db, stmt, offset=pagination.offset, limit=pagination.page_size
    )
    items = [
        ProductPublicOut.model_validate(
            catalog_service.product_payload(p, include_relations=False)
        )
        for p in rows
    ]
    return Page.build(items, total, pagination.page, pagination.page_size)


@router.get("/products/featured", response_model=Page[ProductPublicOut])
def featured_products(db: DbSession, pagination: PageParams) -> Page[ProductPublicOut]:
    return _product_page(db, pagination, is_featured=True)


@router.get("/products/new", response_model=Page[ProductPublicOut])
def new_products(db: DbSession, pagination: PageParams) -> Page[ProductPublicOut]:
    return _product_page(db, pagination, sort="newest", is_new=True)


@router.get("/products/bestsellers", response_model=Page[ProductPublicOut])
def bestselling_products(db: DbSession, pagination: PageParams) -> Page[ProductPublicOut]:
    return _product_page(db, pagination, is_bestseller=True)


@router.get("/products/packages", response_model=Page[ProductPublicOut])
def package_products(db: DbSession, pagination: PageParams) -> Page[ProductPublicOut]:
    return _product_page(db, pagination, product_type=ProductType.PACKAGE.value)


@router.get("/products", response_model=Page[ProductPublicOut])
def list_products(
    db: DbSession,
    pagination: PageParams,
    q: Annotated[str | None, Query(max_length=120)] = None,
    category: Annotated[str | None, Query(max_length=160)] = None,
    product_type: ProductType | None = None,
    is_featured: bool | None = None,
    is_new: bool | None = None,
    is_bestseller: bool | None = None,
    on_sale: bool | None = None,
    in_stock: bool | None = None,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    sort: Annotated[str, Query(pattern="^(featured|newest|price-asc|price-desc|name)$")] = "featured",
) -> Page[ProductPublicOut]:
    return _product_page(
        db,
        pagination,
        sort=sort,
        q=q,
        category_slug=category,
        product_type=product_type.value if product_type else None,
        is_featured=is_featured,
        is_new=is_new,
        is_bestseller=is_bestseller,
        on_sale=on_sale,
        in_stock=in_stock,
        min_price=min_price,
        max_price=max_price,
    )


@router.get("/products/{slug}", response_model=ProductPublicDetail)
def get_product(slug: str, db: DbSession) -> dict:
    stmt = catalog_service.product_detail_query(active_only=True).where(
        Product.slug == slug, catalog_service.publicly_available_condition()
    )
    product = db.execute(stmt).scalars().unique().one_or_none()
    if product is None:
        raise _NOT_FOUND
    return catalog_service.product_payload(product, include_relations=True)


@router.get("/products/{slug}/related", response_model=list[ProductPublicOut])
def related_products(
    slug: str, db: DbSession, limit: Annotated[int, Query(ge=1, le=12)] = 4
) -> list[dict]:
    product = db.execute(
        select(Product).where(Product.slug == slug, Product.is_active.is_(True))
    ).scalar_one_or_none()
    if product is None:
        raise _NOT_FOUND
    stmt = (
        catalog_service.product_list_query(active_only=True)
        .where(Product.id != product.id, Product.category_id == product.category_id,
               catalog_service.publicly_available_condition())
        .order_by(Product.is_featured.desc(), Product.sort_order.asc(), Product.id.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().unique().all()
    return [catalog_service.product_payload(p, include_relations=False) for p in rows]
