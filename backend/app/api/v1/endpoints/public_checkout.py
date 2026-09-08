"""Guest checkout: coupon validation, cart re-pricing, order creation and lookup."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError

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
def validate_coupon(payload: CouponValidateRequest, db: DbSession) -> CouponValidateResponse:
    """Preview only. The real discount is recomputed when the order is placed."""
    subtotal = pricing.money(payload.subtotal)
    coupon = pricing.find_valid_coupon(db, payload.code, subtotal)
    assert coupon is not None  # find_valid_coupon raises for anything invalid
    discount = pricing.compute_discount(coupon, subtotal)
    label = coupon.description or (
        f"خصم {int(coupon.discount_value)}٪"
        if coupon.discount_type == DiscountType.PERCENTAGE.value
        else f"خصم {pricing.money(coupon.discount_value)}"
    )
    return CouponValidateResponse(
        valid=True,
        code=coupon.code,
        label=label,
        discount_type=DiscountType(coupon.discount_type),
        discount=discount,
    )


@router.post("/cart/price", response_model=CartPricingResponse)
def price_cart(payload: CartPricingRequest, db: DbSession) -> CartPricingResponse:
    priced = pricing.price_cart(
        db,
        [(item.product_id, item.variant_id, item.quantity) for item in payload.items],
        coupon_code=payload.coupon_code,
        delivery_area_id=payload.delivery_area_id,
    )
    return CartPricingResponse(
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


@router.post("/orders", response_model=OrderCreatedOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(order_create_rate_limit)])
def create_order(payload: OrderCreate, db: DbSession, response: Response) -> OrderCreatedOut:
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
        items=[(item.product_id, item.variant_id, item.quantity) for item in payload.items],
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
    return OrderCreatedOut.model_validate(order)


@router.get("/orders/{order_number}", response_model=OrderPublicOut, dependencies=[Depends(order_lookup_rate_limit)])
def get_order(
    order_number: str,
    db: DbSession,
    response: Response,
    token: Annotated[str, Header(alias="X-Order-Token", min_length=8, max_length=64)],
) -> OrderPublicOut:
    """Confirmation lookup. The order number alone is never enough."""
    order = orders_service.get_by_number(db, order_number)
    if not order.public_token or not secrets.compare_digest(token, order.public_token):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "order_not_found", "message": "الطلب غير موجود."},
        )
    response.headers["Cache-Control"] = "no-store"
    return OrderPublicOut.model_validate(order)
