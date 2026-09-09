"""Server-authoritative pricing.

Nothing here trusts a number supplied by the client: prices come from the database,
the coupon is re-validated, and the delivery fee is looked up from the area.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import DiscountType, ProductType
from app.db.base import utcnow
from app.models import Coupon, DeliveryArea, Product, ProductOptionValue, ProductVariant
from app.services.errors import DomainError, NotFoundError

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass(slots=True)
class PricedLine:
    product: Product
    variant: ProductVariant | None
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    selected_option_values: list[ProductOptionValue]

    @property
    def variant_description(self) -> str | None:
        if self.selected_option_values:
            selected_values = {value.id: value for value in self.selected_option_values}
            return "، ".join(
                f"{option.name}: {selected_values[value.id].value}"
                for option in self.product.options
                for value in option.values
                if value.id in selected_values
            )
        if not self.variant:
            return None
        selected = {value.id: value.value for value in self.variant.option_values}
        labels = [
            f"{option.name}: {value.value}"
            for option in self.product.options
            for value in option.values
            if value.id in selected
        ]
        return "، ".join(labels) or self.variant.title

    @property
    def sku(self) -> str | None:
        if self.variant and self.variant.sku:
            return self.variant.sku
        return self.product.sku


@dataclass(slots=True)
class PricedCart:
    lines: list[PricedLine]
    subtotal: Decimal
    discount: Decimal
    delivery_fee: Decimal
    total: Decimal
    coupon: Coupon | None
    delivery_area: DeliveryArea | None


def available_stock(product: Product, variant: ProductVariant | None) -> int | None:
    """None means 'not tracked'."""
    if not product.track_inventory:
        return None
    if variant is not None:
        return variant.stock_quantity
    return product.stock_quantity


def price_lines(db: Session, requested: list[tuple]) -> list[PricedLine]:
    """Price `(product_id, variant_id, quantity)` triples against the database."""
    lines: list[PricedLine] = []
    for request in requested:
        product_id, variant_id, quantity = request[:3]
        selected_ids = list(request[3]) if len(request) > 3 else []
        if quantity <= 0:
            raise DomainError("الكمية يجب أن تكون أكبر من صفر.", code="invalid_quantity")

        product = db.get(Product, product_id)
        if product is None:
            raise NotFoundError("المنتج غير موجود.", code="product_not_found")
        if not product.is_active:
            raise DomainError(
                f"المنتج «{product.name}» غير متاح حالياً.", code="product_inactive"
            )
        if product.product_type == ProductType.PACKAGE.value and not product.package_items:
            # A package with no contents would sell nothing; block it rather than
            # silently shipping an empty box.
            raise DomainError(
                f"البكج «{product.name}» لا يحتوي على منتجات.", code="package_empty"
            )

        variant: ProductVariant | None = None
        legacy_variant_product = bool(product.variants)
        if legacy_variant_product and variant_id is None:
            raise DomainError(
                "يجب اختيار خيارات المنتج قبل إضافته إلى الطلب.",
                code="variant_required",
            )
        if variant_id is not None:
            variant = db.get(ProductVariant, variant_id)
            if variant is None or variant.product_id != product.id:
                raise DomainError(
                    "الخيار المحدد لا ينتمي إلى هذا المنتج.", code="variant_mismatch"
                )
            if not variant.is_active:
                raise DomainError("الخيار المحدد غير متاح.", code="variant_inactive")

        selected_values: list[ProductOptionValue] = []
        if product.options and not legacy_variant_product:
            if len(selected_ids) != len(set(selected_ids)):
                raise DomainError("لا يمكن تكرار قيمة الخيار.", code="duplicate_option_value")
            allowed = {value.id: (option, value) for option in product.options for value in option.values}
            if any(value_id not in allowed for value_id in selected_ids):
                raise DomainError("قيمة الخيار لا تنتمي إلى هذا المنتج.", code="option_value_mismatch")
            axes = [allowed[value_id][0].id for value_id in selected_ids]
            if len(selected_ids) != len(product.options) or len(set(axes)) != len(product.options):
                raise DomainError("يجب اختيار قيمة واحدة من كل خيار.", code="options_required")
            selected_values = [allowed[value_id][1] for value_id in selected_ids]
        elif selected_ids:
            raise DomainError("قيم الخيارات المنفصلة غير صالحة لهذا المنتج.", code="option_value_mismatch")

        stock = available_stock(product, variant)
        if stock is not None and stock < quantity:
            raise DomainError(
                f"الكمية المطلوبة من «{product.name}» غير متوفرة.", code="insufficient_stock"
            )

        # compare_at_price is a marketing reference only; it is never charged.
        choice_price = next((value.price_override for value in selected_values if value.option.affects_price and value.price_override is not None), None)
        unit = variant.price_override if variant and variant.price_override is not None else (choice_price if choice_price is not None else product.price)
        unit = money(unit)
        lines.append(
            PricedLine(
                product=product,
                variant=variant,
                quantity=quantity,
                unit_price=unit,
                line_total=money(unit * quantity),
                selected_option_values=selected_values,
            )
        )
    return lines


def find_valid_coupon(db: Session, code: str | None, subtotal: Decimal, *, now: datetime | None = None) -> Coupon | None:
    if not code or not code.strip():
        return None
    now = now or utcnow()
    normalized = code.strip().upper()
    coupon = db.execute(
        select(Coupon).where(func.upper(Coupon.code) == normalized)
    ).scalar_one_or_none()
    if coupon is None or not coupon.is_active:
        raise DomainError("كود الخصم غير صالح.", code="coupon_invalid")
    if coupon.starts_at and now < coupon.starts_at:
        raise DomainError("كود الخصم لم يبدأ بعد.", code="coupon_not_started")
    if coupon.ends_at and now > coupon.ends_at:
        raise DomainError("كود الخصم منتهي الصلاحية.", code="coupon_expired")
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise DomainError("تم استهلاك كود الخصم بالكامل.", code="coupon_exhausted")
    if subtotal < money(coupon.min_order_amount):
        raise DomainError(
            "قيمة الطلب أقل من الحد الأدنى لاستخدام هذا الكود.", code="coupon_min_order"
        )
    return coupon


def compute_discount(coupon: Coupon | None, subtotal: Decimal) -> Decimal:
    if coupon is None:
        return ZERO
    if coupon.discount_type == DiscountType.PERCENTAGE.value:
        discount = money(subtotal * money(coupon.discount_value) / Decimal("100"))
    else:
        discount = money(coupon.discount_value)
    if coupon.max_discount_amount is not None:
        discount = min(discount, money(coupon.max_discount_amount))
    return min(discount, subtotal)


def compute_delivery_fee(area: DeliveryArea | None, subtotal: Decimal) -> Decimal:
    if area is None:
        return ZERO
    if area.free_delivery_threshold is not None and subtotal >= money(area.free_delivery_threshold):
        return ZERO
    return money(area.delivery_fee)


def resolve_delivery_area(db: Session, area_id: int | None) -> DeliveryArea | None:
    if area_id is None:
        return None
    area = db.get(DeliveryArea, area_id)
    if area is None:
        raise NotFoundError("منطقة التوصيل غير موجودة.", code="delivery_area_not_found")
    if not area.is_active:
        raise DomainError("منطقة التوصيل غير متاحة حالياً.", code="delivery_area_inactive")
    return area


def price_cart(
    db: Session,
    requested: list[tuple[int, int | None, int]],
    *,
    coupon_code: str | None = None,
    delivery_area_id: int | None = None,
) -> PricedCart:
    lines = price_lines(db, requested)
    subtotal = money(sum((line.line_total for line in lines), ZERO))

    area = resolve_delivery_area(db, delivery_area_id)
    if area is not None and area.min_order_amount is not None and subtotal < money(area.min_order_amount):
        raise DomainError(
            "قيمة الطلب أقل من الحد الأدنى للتوصيل في هذه المنطقة.",
            code="delivery_min_order",
        )

    coupon = find_valid_coupon(db, coupon_code, subtotal)
    discount = compute_discount(coupon, subtotal)
    delivery_fee = compute_delivery_fee(area, subtotal)
    total = money(max(ZERO, subtotal - discount + delivery_fee))

    return PricedCart(
        lines=lines,
        subtotal=subtotal,
        discount=discount,
        delivery_fee=delivery_fee,
        total=total,
        coupon=coupon,
        delivery_area=area,
    )
