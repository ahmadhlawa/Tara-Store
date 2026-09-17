"""Guest checkout: coupon validation, cart re-pricing, order creation and lookup."""

from __future__ import annotations

import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app.models import DeliveryArea
from app.services import catalog as catalog_service
from app.services.translations import localize, localized_checkout

Locale = Literal["ar", "en"]

from app.api.deps import DbSession
from app.core.enums import DiscountType
from app.core.rate_limit import order_create_rate_limit, order_lookup_rate_limit
from app.schemas.marketing import CouponValidateRequest, CouponValidateResponse
from app.schemas.orders import (
    CartPricingLine,
    CartPricingRequest,
    CartPricingResponse,
    OrderCreate,
    OrderCreatedOut,
    OrderPublicOut,
)
from app.services import orders as orders_service
from app.services import pricing

router = APIRouter(tags=["public-checkout"])


@router.post("/coupons/validate", response_model=CouponValidateResponse)
def validate_coupon(payload: CouponValidateRequest, db: DbSession, locale: Locale = "ar") -> CouponValidateResponse:
    """Preview only. The real discount is recomputed when the order is placed."""
    subtotal = pricing.money(payload.subtotal)
    coupon = pricing.find_valid_coupon(db, payload.code, subtotal)
    assert coupon is not None  # find_valid_coupon raises for anything invalid
    discount = pricing.compute_discount(coupon, subtotal)
    description = localize(db, {"id": coupon.id, "description": coupon.description}, [coupon], locale, "coupons")["description"]
    label = description or (
        f"خصم {int(coupon.discount_value)}٪"
        if coupon.discount_type == DiscountType.PERCENTAGE.value
        else f"خصم {pricing.money(coupon.discount_value)}"
    )
    if locale == "en" and not description:
        label = f"Discount {int(coupon.discount_value)}%" if coupon.discount_type == "percentage" else f"Discount {pricing.money(coupon.discount_value)}"
    return CouponValidateResponse(
        valid=True,
        code=coupon.code,
        label=label,
        discount_type=DiscountType(coupon.discount_type),
        discount=discount,
    )


@router.post("/cart/price", response_model=CartPricingResponse)
def price_cart(payload: CartPricingRequest, db: DbSession, locale: Locale = "ar") -> CartPricingResponse:
    priced = pricing.price_cart(
        db,
        [(item.product_id, item.variant_id, item.quantity, item.selected_option_value_ids) for item in payload.items],
        coupon_code=payload.coupon_code,
        delivery_area_id=payload.delivery_area_id,
    )
    response = CartPricingResponse(
        lines=[
            CartPricingLine(
                product_id=line.product.id,
                variant_id=line.variant.id if line.variant else None,
                product_name=line.product.name,
                slug=line.product.slug,
                variant_description=line.variant_description,
                unit_price=line.unit_price,
                quantity=line.quantity,
                line_total=line.line_total,
                primary_image_url=line.product.primary_image_url,
            )
            for line in priced.lines
        ],
        subtotal=priced.subtotal,
        discount=priced.discount,
        delivery_fee=priced.delivery_fee,
        total=priced.total,
        coupon_code=priced.coupon.code if priced.coupon else None,
        delivery_area_name=priced.delivery_area.name if priced.delivery_area else None,
    )
    # Multiple cart lines can select different scents from the same product.
    data = response.model_dump()
    for copy, line in zip(data["lines"], priced.lines):
        copy["selected_option_value_ids"] = [value.id for value in line.selected_option_values]
    products = [line.product for line in priced.lines]
    if locale == "en":
        from app.models import Product
        products = list(db.scalars(catalog_service.product_detail_query(active_only=False).where(
            Product.id.in_([product.id for product in products]))).unique())
    return CartPricingResponse.model_validate(localized_checkout(db, data,
        products, locale, area=priced.delivery_area))



@router.post("/orders", response_model=OrderCreatedOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(order_create_rate_limit)])
def create_order(payload: OrderCreate, db: DbSession, response: Response, locale: Locale = "ar") -> OrderCreatedOut:
    draft = orders_service.OrderDraft(
        client_reference=payload.client_reference,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=payload.customer_email,
        address=payload.address,
        delivery_area_id=payload.delivery_area_id,
        coupon_code=payload.coupon_code,
        payment_method=payload.payment_method.value,
        customer_notes=payload.customer_notes,
        items=[(item.product_id, item.variant_id, item.quantity, item.selected_option_value_ids) for item in payload.items],
    )
    try:
        order = orders_service.create_order(db, draft)
        db.commit()
    except IntegrityError:
        db.rollback()
        order = orders_service.get_by_client_reference(db, payload.client_reference)
        if order is None:
            raise
    db.refresh(order)
    response.headers["Cache-Control"] = "no-store"
    return _public_order(db, order, OrderCreatedOut, locale)


@router.get("/orders/{order_number}", response_model=OrderPublicOut, dependencies=[Depends(order_lookup_rate_limit)])
def get_order(
    order_number: str,
    db: DbSession,
    response: Response,
    token: Annotated[str, Header(alias="X-Order-Token", min_length=8, max_length=64)],
    locale: Locale = "ar",
) -> OrderPublicOut:
    """Confirmation lookup. The order number alone is never enough."""
    order = orders_service.get_by_number(db, order_number)
    if not order.public_token or not secrets.compare_digest(token, order.public_token):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "order_not_found", "message": "الطلب غير موجود."},
        )
    response.headers["Cache-Control"] = "no-store"
    return _public_order(db, order, OrderPublicOut, locale)


def _public_order(db, order, schema, locale):
    data = schema.model_validate(order).model_dump()
    if locale == "ar":
        return schema.model_validate(data)
    from app.models import Product
    ids = [item.product_id for item in order.items if item.product_id]
    products = list(db.scalars(catalog_service.product_detail_query(active_only=False).where(Product.id.in_(ids))).unique())
    area = db.get(DeliveryArea, order.delivery_area_id) if order.delivery_area_id else None
    return schema.model_validate(localized_checkout(db, data, products, locale, area=area))
