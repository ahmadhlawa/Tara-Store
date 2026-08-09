from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.core.enums import DiscountType
from app.schemas.common import APIModel, Money, UTCDateTime


class CouponBase(APIModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=250)
    discount_type: DiscountType = DiscountType.PERCENTAGE
    discount_value: Money = Field(gt=0)
    min_order_amount: Money = Field(default=Decimal("0.00"), ge=0)
    max_discount_amount: Money | None = Field(default=None, gt=0)
    usage_limit: int | None = Field(default=None, gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _check_rules(self):
        if self.discount_type == DiscountType.PERCENTAGE and self.discount_value > 100:
            raise ValueError("a percentage discount cannot exceed 100")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class CouponCreate(CouponBase):
    pass


class CouponUpdate(APIModel):
    description: str | None = Field(default=None, max_length=250)
    discount_type: DiscountType | None = None
    discount_value: Money | None = Field(default=None, gt=0)
    min_order_amount: Money | None = Field(default=None, ge=0)
    max_discount_amount: Money | None = Field(default=None, gt=0)
    usage_limit: int | None = Field(default=None, gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None


class CouponAdminOut(APIModel):
    id: int
    code: str
    description: str | None = None
    discount_type: DiscountType
    discount_value: Money
    min_order_amount: Money
    max_discount_amount: Money | None = None
    usage_limit: int | None = None
    used_count: int
    starts_at: UTCDateTime | None = None
    ends_at: UTCDateTime | None = None
    is_active: bool
    created_at: UTCDateTime


class CouponValidateRequest(APIModel):
    code: str = Field(min_length=1, max_length=64)
    subtotal: Money = Field(ge=0)


class CouponValidateResponse(APIModel):
    valid: bool
    code: str
    label: str
    discount_type: DiscountType
    discount: Money


class DeliveryAreaBase(APIModel):
    name: str = Field(min_length=1, max_length=150)
    delivery_fee: Money = Field(ge=0)
    min_order_amount: Money | None = Field(default=None, ge=0)
    free_delivery_threshold: Money | None = Field(default=None, ge=0)
    estimated_days: str | None = Field(default=None, max_length=100)
    is_active: bool = True
    sort_order: int = 0


class DeliveryAreaCreate(DeliveryAreaBase):
    pass


class DeliveryAreaUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    delivery_fee: Money | None = Field(default=None, ge=0)
    min_order_amount: Money | None = Field(default=None, ge=0)
    free_delivery_threshold: Money | None = Field(default=None, ge=0)
    estimated_days: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None
    sort_order: int | None = None


class DeliveryAreaOut(APIModel):
    id: int
    name: str
    delivery_fee: Money
    min_order_amount: Money | None = None
    free_delivery_threshold: Money | None = None
    estimated_days: str | None = None
    sort_order: int


class DeliveryAreaAdminOut(DeliveryAreaOut):
    is_active: bool
    updated_at: UTCDateTime
