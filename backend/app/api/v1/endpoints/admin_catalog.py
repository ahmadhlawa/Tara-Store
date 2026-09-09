"""Admin catalog management: categories, products and their sub-resources."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.crud import apply_updates, get_or_404
from app.api.deps import CurrentAdmin, DbSession, PageParams
from app.core.enums import ProductType
from app.models import (
    Category,
    PackageItem,
    Product,
    ProductImage,
    ProductOption,
    ProductOptionValue,
    ProductSpecification,
    ProductVariant,
)
from app.schemas.catalog import (
    CategoryAdminOut,
    CategoryCreate,
    CategoryUpdate,
    PackageItemIn,
    PackageItemOut,
    ProductAdminListOut,
    ProductAdminOut,
    ProductCreate,
    ProductImageIn,
    ProductImageOut,
    ProductImageReorderIn,
    ProductOptionIn,
    ProductOptionOut,
    ProductSpecificationIn,
    ProductSpecificationOut,
    ProductUpdate,
    ProductVariantIn,
    ProductVariantOut,
)
from app.schemas.common import MessageResponse, Page
from app.services import audit as audit_service
from app.services import catalog as catalog_service
from app.services.errors import ConflictError, DomainError
from app.services.slugs import unique_slug

router = APIRouter(prefix="/admin", tags=["admin-catalog"])


# ── Categories ────────────────────────────────────────────────────────────────
@router.get("/categories", response_model=Page[CategoryAdminOut])
def list_categories(
    db: DbSession,
    admin: CurrentAdmin,
    pagination: PageParams,
    q: Annotated[str | None, Query(max_length=120)] = None,
    is_active: bool | None = None,
) -> Page[CategoryAdminOut]:
    stmt = select(Category)
    if q:
        stmt = stmt.where(Category.name.like(f"%{q}%"))
    if is_active is not None:
        stmt = stmt.where(Category.is_active.is_(is_active))
    stmt = stmt.order_by(Category.sort_order.asc(), Category.id.asc())
    rows, total = catalog_service.paginate(
        db, stmt, offset=pagination.offset, limit=pagination.page_size
    )
    counts = catalog_service.product_counts_by_category(db, active_only=False)
    items = [
        CategoryAdminOut.model_validate(
            {
                **catalog_service.category_payload(row, counts.get(row.id, 0)),
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )
        for row in rows
    ]
    return Page.build(items, total, pagination.page, pagination.page_size)


@router.post("/categories", response_model=CategoryAdminOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: DbSession, admin: CurrentAdmin):
    category = Category(
        **payload.model_dump(exclude={"slug"}),
        slug=unique_slug(db, Category, payload.slug or payload.name),
    )
    db.add(category)
    db.flush()
    audit_service.record(
        db,
        admin=admin,
        action="category.created",
        entity_type="category",
        entity_id=category.id,
        meta={"name": category.name, "slug": category.slug},
    )
    db.commit()
    db.refresh(category)
    return {**catalog_service.category_payload(category), "created_at": category.created_at, "updated_at": category.updated_at}


@router.patch("/categories/{category_id}", response_model=CategoryAdminOut)
def update_category(category_id: int, payload: CategoryUpdate, db: DbSession, admin: CurrentAdmin):
    category = get_or_404(db, Category, category_id, "القسم غير موجود.")
    if payload.parent_id is not None and payload.parent_id == category.id:
        raise DomainError("لا يمكن أن يكون القسم أباً لنفسه.", code="category_self_parent")
    data = payload.model_dump(exclude_unset=True)
    if data.get("slug"):
        data["slug"] = unique_slug(db, Category, data["slug"], exclude_id=category.id)
    changed: list[str] = []
    for field, value in data.items():
        if getattr(category, field, None) != value:
            setattr(category, field, value)
            changed.append(field)
    audit_service.record(
        db,
        admin=admin,
        action="category.updated",
        entity_type="category",
        entity_id=category.id,
        meta={"fields": changed},
    )
    db.commit()
    db.refresh(category)
    return {**catalog_service.category_payload(category), "created_at": category.created_at, "updated_at": category.updated_at}


@router.delete("/categories/{category_id}", response_model=MessageResponse)
def delete_category(category_id: int, db: DbSession, admin: CurrentAdmin):
    category = get_or_404(db, Category, category_id, "القسم غير موجود.")
    linked = db.execute(
        select(Product.id).where(Product.category_id == category.id).limit(1)
    ).first()
    if linked is not None:
        raise ConflictError(
            "لا يمكن حذف قسم يحتوي على منتجات. انقل المنتجات أولاً.",
            code="category_has_products",
        )
    audit_service.record(
        db,
        admin=admin,
        action="category.deleted",
        entity_type="category",
        entity_id=category.id,
        meta={"name": category.name},
    )
    db.delete(category)
    db.commit()
    return MessageResponse(message="تم حذف القسم.")


# ── Products ──────────────────────────────────────────────────────────────────
def _load_product(db: DbSession, product_id: int) -> Product:
    stmt = catalog_service.product_detail_query(active_only=False).where(Product.id == product_id)
    product = db.execute(stmt).scalars().unique().one_or_none()
    if product is None:
        get_or_404(db, Product, product_id, "المنتج غير موجود.")
    return product


@router.get("/products", response_model=Page[ProductAdminListOut])
def list_products(
    db: DbSession,
    admin: CurrentAdmin,
    pagination: PageParams,
    q: Annotated[str | None, Query(max_length=120)] = None,
    category_id: int | None = None,
    product_type: ProductType | None = None,
    is_active: bool | None = None,
    low_stock: bool = False,
    sort: Annotated[
        str, Query(pattern="^(featured|newest|price-asc|price-desc|name|sort_order)$")
    ] = "newest",
) -> Page[ProductAdminListOut]:
    stmt = catalog_service.apply_product_filters(
        catalog_service.product_list_query(active_only=False, public=False),
        q=q,
        category_id=category_id,
        product_type=product_type.value if product_type else None,
        is_active=is_active,
    )
    if low_stock:
        stmt = stmt.where(
            Product.track_inventory.is_(True),
            Product.stock_quantity <= Product.low_stock_threshold,
        )
    stmt = catalog_service.apply_product_sort(stmt, sort)
    rows, total = catalog_service.paginate(
        db, stmt, offset=pagination.offset, limit=pagination.page_size
    )
    items = [
        ProductAdminListOut.model_validate(catalog_service.admin_product_list_payload(p))
        for p in rows
    ]
    return Page.build(items, total, pagination.page, pagination.page_size)


@router.get("/products/{product_id}", response_model=ProductAdminOut)
def get_product(product_id: int, db: DbSession, admin: CurrentAdmin):
    return catalog_service.admin_product_payload(_load_product(db, product_id))


@router.post("/products", response_model=ProductAdminOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: DbSession, admin: CurrentAdmin):
    data = payload.model_dump(exclude={"slug", "images", "specifications"})
    data["product_type"] = payload.product_type.value
    product = Product(**data, slug=unique_slug(db, Product, payload.slug or payload.name))
    for index, image in enumerate(payload.images):
        product.images.append(ProductImage(**image.model_dump(), ))
        product.images[-1].sort_order = image.sort_order or index
    for index, spec in enumerate(payload.specifications):
        product.specifications.append(ProductSpecification(**spec.model_dump()))
        product.specifications[-1].sort_order = spec.sort_order or index
    catalog_service.refresh_search_text(product)
    db.add(product)
    db.flush()
    audit_service.record(
        db,
        admin=admin,
        action="product.created",
        entity_type="product",
        entity_id=product.id,
        meta={"name": product.name, "slug": product.slug, "price": str(product.price)},
    )
    db.commit()
    return catalog_service.admin_product_payload(_load_product(db, product.id))


@router.patch("/products/{product_id}", response_model=ProductAdminOut)
def update_product(product_id: int, payload: ProductUpdate, db: DbSession, admin: CurrentAdmin):
    product = _load_product(db, product_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("slug"):
        data["slug"] = unique_slug(db, Product, data["slug"], exclude_id=product.id)
    if isinstance(data.get("product_type"), ProductType):
        data["product_type"] = data["product_type"].value

    new_price = data.get("price", product.price)
    new_compare = data.get("compare_at_price", product.compare_at_price)
    if new_compare is not None and new_price is not None and new_compare <= new_price:
        raise DomainError(
            "سعر المقارنة يجب أن يكون أعلى من سعر البيع.", code="invalid_compare_at_price"
        )

    changed: list[str] = []
    for field, value in data.items():
        if getattr(product, field, None) != value:
            setattr(product, field, value)
            changed.append(field)
    catalog_service.refresh_search_text(product)
    audit_service.record(
        db,
        admin=admin,
        action="product.updated",
        entity_type="product",
        entity_id=product.id,
        meta={"fields": changed, "name": product.name},
    )
    db.commit()
    return catalog_service.admin_product_payload(_load_product(db, product.id))


@router.delete("/products/{product_id}", response_model=MessageResponse)
def delete_product(product_id: int, db: DbSession, admin: CurrentAdmin):
    product = get_or_404(db, Product, product_id, "المنتج غير موجود.")
    audit_service.record(
        db,
        admin=admin,
        action="product.deleted",
        entity_type="product",
        entity_id=product.id,
        meta={"name": product.name, "slug": product.slug},
    )
    db.delete(product)
    db.commit()
    return MessageResponse(message="تم حذف المنتج.")


# ── Product images ────────────────────────────────────────────────────────────
def _normalize_image_order(product_id: int, db: DbSession) -> list[ProductImage]:
    """Rewrite the stored positions as 0, 1, 2 … so ordering never goes ambiguous."""
    images = list(
        db.scalars(
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(ProductImage.sort_order, ProductImage.id)
        )
    )
    for position, image in enumerate(images):
        image.sort_order = position
    return images



@router.get("/products/{product_id}/images", response_model=list[ProductImageOut])
def list_images(product_id: int, db: DbSession, admin: CurrentAdmin):
    return _load_product(db, product_id).images


@router.post(
    "/products/{product_id}/images",
    response_model=ProductImageOut,
    status_code=status.HTTP_201_CREATED,
)
def add_image(product_id: int, payload: ProductImageIn, db: DbSession, admin: CurrentAdmin):
    product = _load_product(db, product_id)
    # A new image always appends. Order decides the cover, so an upload never
    # silently takes it over from the image the admin put first.
    image = ProductImage(
        product_id=product.id,
        **payload.model_dump(exclude={"sort_order"}),
        sort_order=len(product.images),
    )
    db.add(image)
    audit_service.record(
        db,
        admin=admin,
        action="product.image_added",
        entity_type="product",
        entity_id=product.id,
        meta={"url": payload.url},
    )
    db.commit()
    db.refresh(image)
    return image


@router.put("/products/{product_id}/images/reorder", response_model=list[ProductImageOut])
def reorder_images(
    product_id: int, payload: ProductImageReorderIn, db: DbSession, admin: CurrentAdmin
):
    """Store a new image order. The submitted list must be the product's whole set."""
    product = _load_product(db, product_id)
    by_id = {image.id: image for image in product.images}
    submitted = payload.image_ids
    if len(set(submitted)) != len(submitted) or set(submitted) != set(by_id):
        raise DomainError(
            "قائمة الترتيب يجب أن تضم صور هذا المنتج كاملة دون تكرار.", code="image_mismatch"
        )

    for position, image_id in enumerate(submitted):
        by_id[image_id].sort_order = position
    audit_service.record(
        db,
        admin=admin,
        action="product.images_reordered",
        entity_type="product",
        entity_id=product.id,
        meta={"image_ids": submitted},
    )
    db.commit()
    return [by_id[image_id] for image_id in submitted]


@router.delete("/products/{product_id}/images/{image_id}", response_model=MessageResponse)
def delete_image(product_id: int, image_id: int, db: DbSession, admin: CurrentAdmin):
    image = get_or_404(db, ProductImage, image_id, "الصورة غير موجودة.")
    if image.product_id != product_id:
        raise DomainError("الصورة لا تنتمي لهذا المنتج.", code="image_mismatch")
    db.delete(image)
    db.flush()
    _normalize_image_order(product_id, db)
    audit_service.record(
        db,
        admin=admin,
        action="product.image_removed",
        entity_type="product",
        entity_id=product_id,
        meta={"image_id": image_id},
    )
    db.commit()
    return MessageResponse(message="تم حذف الصورة.")


# ── Specifications ────────────────────────────────────────────────────────────
@router.put(
    "/products/{product_id}/specifications", response_model=list[ProductSpecificationOut]
)
def replace_specifications(
    product_id: int,
    payload: list[ProductSpecificationIn],
    db: DbSession,
    admin: CurrentAdmin,
):
    product = _load_product(db, product_id)
    product.specifications.clear()
    db.flush()
    for index, spec in enumerate(payload):
        product.specifications.append(
            ProductSpecification(
                name=spec.name, value=spec.value, sort_order=spec.sort_order or index
            )
        )
    audit_service.record(
        db,
        admin=admin,
        action="product.specifications_replaced",
        entity_type="product",
        entity_id=product.id,
        meta={"count": len(payload)},
    )
    db.commit()
    return _load_product(db, product_id).specifications


# ── Options and variants ──────────────────────────────────────────────────────
@router.get("/products/{product_id}/options", response_model=list[ProductOptionOut])
def list_options(product_id: int, db: DbSession, admin: CurrentAdmin):
    return _load_product(db, product_id).options


@router.put("/products/{product_id}/options", response_model=list[ProductOptionOut])
def replace_options(
    product_id: int, payload: list[ProductOptionIn], db: DbSession, admin: CurrentAdmin
):
    """Rewrite the option axes, keeping every variant that is still a valid combination.

    Options and values carry their row id through the payload, so a rename is an
    update — not a delete plus insert — and the variants built on those ids stay.
    Only variants whose `option_value_ids` no longer describe one value per axis
    are dropped; nothing is merged, and no combination is created here.
    """
    product = _load_product(db, product_id)
    # Snapshot before touching the axes: once a value row is deleted the
    # association rows go with it, and the variant would look empty.
    variant_value_ids = {
        variant.id: [value.id for value in variant.option_values]
        for variant in product.variants
    }
    existing_options = {option.id: option for option in product.options}
    existing_values = {
        value.id: value for option in product.options for value in option.values
    }

    try:
        # Decide which variants survive from the incoming shape, before any row is
        # deleted — the join rows would be gone by then.
        axis_of: dict[int, object] = {}
        axis_keys: set[object] = set()
        for index, option in enumerate(payload):
            axis_key = option.id or f"new:{index}"
            axis_keys.add(axis_key)
            for value in option.values:
                if value.id:
                    axis_of[value.id] = axis_key
        removed = [
            variant
            for variant in list(product.variants)
            if _variant_is_incompatible(variant_value_ids.get(variant.id, []), axis_of, axis_keys)
        ]
        for variant in removed:
            product.variants.remove(variant)

        option_rows: list[ProductOption] = []
        for index, option in enumerate(payload):
            row = existing_options.get(option.id) if option.id else None
            if option.id and row is None:
                raise DomainError("خيار غير موجود لهذا المنتج.", code="option_not_found")
            if row is None:
                row = ProductOption(product_id=product.id)
            row.name = option.name
            row.sort_order = option.sort_order or index
            value_rows: list[ProductOptionValue] = []
            for value_index, value in enumerate(option.values):
                value_row = existing_values.get(value.id) if value.id else None
                if value.id and value_row is None:
                    raise DomainError(
                        "قيمة خيار غير موجودة لهذا المنتج.", code="option_value_not_found"
                    )
                if value_row is None:
                    value_row = ProductOptionValue()
                value_row.value = value.value
                value_row.sort_order = value.sort_order or value_index
                value_rows.append(value_row)
            row.values = value_rows
            option_rows.append(row)
        product.options = option_rows

        audit_service.record(
            db,
            admin=admin,
            action="product.options_replaced",
            entity_type="product",
            entity_id=product.id,
            meta={"count": len(payload), "variants_removed": len(removed)},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _load_product(db, product_id).options


def _variant_is_incompatible(
    value_ids: list[int], axis_of: dict[int, object], axis_keys: set[object]
) -> bool:
    """A variant survives only when it still holds exactly one value per axis."""
    if not value_ids:
        # Free-form variant, never built on the options — leave it alone.
        return False
    if any(value_id not in axis_of for value_id in value_ids):
        return True
    # Dropping a whole axis would collapse variants onto the same remaining
    # combination; treat them as incompatible rather than silently merging.
    return {axis_of[value_id] for value_id in value_ids} != axis_keys


@router.get("/products/{product_id}/variants", response_model=list[ProductVariantOut])
def list_variants(product_id: int, db: DbSession, admin: CurrentAdmin):
    return _load_product(db, product_id).variants


@router.post(
    "/products/{product_id}/variants",
    response_model=ProductVariantOut,
    status_code=status.HTTP_201_CREATED,
)
def create_variant(
    product_id: int, payload: ProductVariantIn, db: DbSession, admin: CurrentAdmin
):
    product = _load_product(db, product_id)
    variant = ProductVariant(
        product_id=product.id,
        **payload.model_dump(exclude={"option_value_ids"}),
    )
    _attach_option_values(db, product, variant, payload.option_value_ids)
    db.add(variant)
    audit_service.record(
        db,
        admin=admin,
        action="product.variant_created",
        entity_type="product",
        entity_id=product.id,
        meta={"title": payload.title},
    )
    db.commit()
    db.refresh(variant)
    return variant


@router.patch(
    "/products/{product_id}/variants/{variant_id}", response_model=ProductVariantOut
)
def update_variant(
    product_id: int,
    variant_id: int,
    payload: ProductVariantIn,
    db: DbSession,
    admin: CurrentAdmin,
):
    product = _load_product(db, product_id)
    variant = get_or_404(db, ProductVariant, variant_id, "الخيار غير موجود.")
    if variant.product_id != product.id:
        raise DomainError("الخيار لا ينتمي لهذا المنتج.", code="variant_mismatch")
    apply_updates(variant, payload, exclude={"option_value_ids"})
    _attach_option_values(db, product, variant, payload.option_value_ids)
    audit_service.record(
        db,
        admin=admin,
        action="product.variant_updated",
        entity_type="product",
        entity_id=product.id,
        meta={"variant_id": variant_id},
    )
    db.commit()
    db.refresh(variant)
    return variant


@router.delete(
    "/products/{product_id}/variants/{variant_id}", response_model=MessageResponse
)
def delete_variant(product_id: int, variant_id: int, db: DbSession, admin: CurrentAdmin):
    variant = get_or_404(db, ProductVariant, variant_id, "الخيار غير موجود.")
    if variant.product_id != product_id:
        raise DomainError("الخيار لا ينتمي لهذا المنتج.", code="variant_mismatch")
    db.delete(variant)
    audit_service.record(
        db,
        admin=admin,
        action="product.variant_deleted",
        entity_type="product",
        entity_id=product_id,
        meta={"variant_id": variant_id},
    )
    db.commit()
    return MessageResponse(message="تم حذف الخيار.")


def _attach_option_values(
    db: DbSession, product: Product, variant: ProductVariant, value_ids: list[int]
) -> None:
    if not value_ids:
        variant.option_values = []
        return
    allowed = {value.id for option in product.options for value in option.values}
    unknown = [value_id for value_id in value_ids if value_id not in allowed]
    if unknown:
        raise DomainError(
            "بعض قيم الخيارات لا تنتمي لهذا المنتج.", code="option_value_mismatch"
        )
    # A variant is one combination: at most one value from each option axis, or
    # the storefront could never resolve a choice back to a single row.
    axis_of = {value.id: option.id for option in product.options for value in option.values}
    axes = [axis_of[value_id] for value_id in value_ids]
    if len(set(axes)) != len(axes):
        raise DomainError(
            "لا يمكن اختيار أكثر من قيمة من نفس الخيار للنسخة الواحدة.",
            code="option_axis_conflict",
        )
    variant.option_values = [db.get(ProductOptionValue, value_id) for value_id in value_ids]


# ── Package contents ──────────────────────────────────────────────────────────
def _package_payload(item: PackageItem) -> dict:
    return {
        "id": item.id,
        "included_product_id": item.included_product_id,
        "included_product_name": item.included_product.name if item.included_product else None,
        "included_product_slug": item.included_product.slug if item.included_product else None,
        "included_product_image_url": item.included_product.primary_image_url
        if item.included_product
        else None,
        "included_variant_id": item.included_variant_id,
        "included_variant_title": item.included_variant.title if item.included_variant else None,
        "quantity": item.quantity,
        "display_note": item.display_note,
        "sort_order": item.sort_order,
    }


@router.get("/products/{product_id}/package-items", response_model=list[PackageItemOut])
def list_package_items(product_id: int, db: DbSession, admin: CurrentAdmin):
    return [_package_payload(item) for item in _load_product(db, product_id).package_items]


@router.post(
    "/products/{product_id}/package-items",
    response_model=PackageItemOut,
    status_code=status.HTTP_201_CREATED,
)
def add_package_item(
    product_id: int, payload: PackageItemIn, db: DbSession, admin: CurrentAdmin
):
    package = _load_product(db, product_id)
    catalog_service.assert_package_is_valid(db, package, payload.included_product_id)
    if payload.included_variant_id is not None:
        variant = db.get(ProductVariant, payload.included_variant_id)
        if variant is None or variant.product_id != payload.included_product_id:
            raise DomainError("Ø§Ù„Ù†Ø³Ø®Ø© Ø§Ù„Ù…Ø­Ø¯Ø¯Ø© Ù„Ø§ ØªÙ†ØªÙ…ÙŠ Ù„Ù„Ù…Ù†ØªØ¬.", code="package_component_variant_mismatch")
    if any(i.included_product_id == payload.included_product_id for i in package.package_items):
        raise ConflictError("المنتج مضاف مسبقاً إلى هذا البكج.", code="package_item_duplicate")
    item = PackageItem(package_product_id=package.id, **payload.model_dump())
    db.add(item)
    audit_service.record(
        db,
        admin=admin,
        action="product.package_item_added",
        entity_type="product",
        entity_id=package.id,
        meta={"included_product_id": payload.included_product_id},
    )
    db.commit()
    db.refresh(item)
    return _package_payload(item)


@router.delete(
    "/products/{product_id}/package-items/{item_id}", response_model=MessageResponse
)
def delete_package_item(
    product_id: int, item_id: int, db: DbSession, admin: CurrentAdmin
):
    item = get_or_404(db, PackageItem, item_id, "محتوى البكج غير موجود.")
    if item.package_product_id != product_id:
        raise DomainError("العنصر لا ينتمي لهذا البكج.", code="package_item_mismatch")
    db.delete(item)
    audit_service.record(
        db,
        admin=admin,
        action="product.package_item_removed",
        entity_type="product",
        entity_id=product_id,
        meta={"item_id": item_id},
    )
    db.commit()
    return MessageResponse(message="تم حذف المنتج من البكج.")
