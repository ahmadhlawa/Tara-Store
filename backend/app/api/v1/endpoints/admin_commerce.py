"""Admin dashboard, coupons, delivery areas and order management."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import selectinload

from app.api.crud import apply_updates, get_or_404
from app.api.deps import CurrentAdmin, DbSession, PageParams, SuperAdmin
from app.core.enums import OrderSource, OrderStatus, PaymentStatus
from app.models import Coupon, DeliveryArea, Invoice, Order, OrderItem
from app.schemas.common import MessageResponse, Page
from app.schemas.marketing import (
    CouponAdminOut,
    CouponCreate,
    CouponUpdate,
    DeliveryAreaAdminOut,
    DeliveryAreaCreate,
    DeliveryAreaUpdate,
)
from app.schemas.orders import (
    AdminCatalogOrderItemInput,
    DashboardSummary,
    ManualCatalogOrderItemInput,
    ManualOrderCreate,
    ManualOrderItemInput,
    OrderAdminUpdate,
    OrderAdminListOut,
    OrderAdminOut,
    OrderCompletionRequest,
    OrderReopenRequest,
    OrderNotesUpdate,
    OrderStatusUpdate,
)
from app.services import audit as audit_service
from app.services import catalog as catalog_service
from app.services import orders as orders_service
from app.services.errors import ConflictError

router = APIRouter(prefix="/admin", tags=["admin-commerce"])


# ── Dashboard ─────────────────────────────────────────────────────────────────
@router.get("/dashboard", response_model=DashboardSummary)
def dashboard(db: DbSession, admin: CurrentAdmin):
    summary = orders_service.dashboard_summary(db)
    summary["recent_orders"] = [_order_list_payload(db, order) for order in summary["recent_orders"]]
    return summary


# ── Coupons ───────────────────────────────────────────────────────────────────
@router.get("/coupons", response_model=Page[CouponAdminOut])
def list_coupons(
    db: DbSession,
    admin: CurrentAdmin,
    pagination: PageParams,
    q: Annotated[str | None, Query(max_length=64)] = None,
    is_active: bool | None = None,
) -> Page[CouponAdminOut]:
    stmt = select(Coupon)
    if q:
        stmt = stmt.where(Coupon.code.like(f"%{q.upper()}%"))
    if is_active is not None:
        stmt = stmt.where(Coupon.is_active.is_(is_active))
    stmt = stmt.order_by(Coupon.id.desc())
    rows, total = catalog_service.paginate(
        db, stmt, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.build(
        [CouponAdminOut.model_validate(row) for row in rows],
        total,
        pagination.page,
        pagination.page_size,
    )


@router.post("/coupons", response_model=CouponAdminOut, status_code=status.HTTP_201_CREATED)
def create_coupon(payload: CouponCreate, db: DbSession, admin: CurrentAdmin):
    code = payload.code.strip().upper()
    exists = db.execute(select(Coupon.id).where(func.upper(Coupon.code) == code)).first()
    if exists is not None:
        raise ConflictError("كود الخصم مستخدم مسبقاً.", code="coupon_code_taken")
    data = payload.model_dump()
    data["code"] = code
    data["discount_type"] = payload.discount_type.value
    coupon = Coupon(**data)
    db.add(coupon)
    db.flush()
    audit_service.record(
        db,
        admin=admin,
        action="coupon.created",
        entity_type="coupon",
        entity_id=coupon.id,
        meta={"code": coupon.code, "type": coupon.discount_type},
    )
    db.commit()
    db.refresh(coupon)
    return coupon


@router.patch("/coupons/{coupon_id}", response_model=CouponAdminOut)
def update_coupon(coupon_id: int, payload: CouponUpdate, db: DbSession, admin: CurrentAdmin):
    coupon = get_or_404(db, Coupon, coupon_id, "كود الخصم غير موجود.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("discount_type") is not None:
        data["discount_type"] = data["discount_type"].value
    changed: list[str] = []
    for field, value in data.items():
        if getattr(coupon, field, None) != value:
            setattr(coupon, field, value)
            changed.append(field)
    audit_service.record(
        db,
        admin=admin,
        action="coupon.updated",
        entity_type="coupon",
        entity_id=coupon.id,
        meta={"fields": changed, "code": coupon.code},
    )
    db.commit()
    db.refresh(coupon)
    return coupon


@router.delete("/coupons/{coupon_id}", response_model=MessageResponse)
def delete_coupon(coupon_id: int, db: DbSession, admin: CurrentAdmin):
    coupon = get_or_404(db, Coupon, coupon_id, "كود الخصم غير موجود.")
    audit_service.record(
        db,
        admin=admin,
        action="coupon.deleted",
        entity_type="coupon",
        entity_id=coupon.id,
        meta={"code": coupon.code},
    )
    db.delete(coupon)
    db.commit()
    return MessageResponse(message="تم حذف كود الخصم.")


# ── Delivery areas ────────────────────────────────────────────────────────────
@router.get("/delivery-areas", response_model=list[DeliveryAreaAdminOut])
def list_delivery_areas(db: DbSession, admin: CurrentAdmin):
    stmt = select(DeliveryArea).order_by(DeliveryArea.sort_order.asc(), DeliveryArea.id.asc())
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/delivery-areas", response_model=DeliveryAreaAdminOut, status_code=status.HTTP_201_CREATED
)
def create_delivery_area(payload: DeliveryAreaCreate, db: DbSession, admin: CurrentAdmin):
    area = DeliveryArea(**payload.model_dump())
    db.add(area)
    db.flush()
    audit_service.record(
        db,
        admin=admin,
        action="delivery_area.created",
        entity_type="delivery_area",
        entity_id=area.id,
        meta={"name": area.name, "fee": str(area.delivery_fee)},
    )
    db.commit()
    db.refresh(area)
    return area


@router.patch("/delivery-areas/{area_id}", response_model=DeliveryAreaAdminOut)
def update_delivery_area(
    area_id: int, payload: DeliveryAreaUpdate, db: DbSession, admin: CurrentAdmin
):
    area = get_or_404(db, DeliveryArea, area_id, "منطقة التوصيل غير موجودة.")
    changed = apply_updates(area, payload)
    audit_service.record(
        db,
        admin=admin,
        action="delivery_area.updated",
        entity_type="delivery_area",
        entity_id=area.id,
        meta={"fields": changed, "name": area.name},
    )
    db.commit()
    db.refresh(area)
    return area


@router.delete("/delivery-areas/{area_id}", response_model=MessageResponse)
def delete_delivery_area(area_id: int, db: DbSession, admin: CurrentAdmin):
    area = get_or_404(db, DeliveryArea, area_id, "منطقة التوصيل غير موجودة.")
    audit_service.record(
        db,
        admin=admin,
        action="delivery_area.deleted",
        entity_type="delivery_area",
        entity_id=area.id,
        meta={"name": area.name},
    )
    db.delete(area)
    db.commit()
    return MessageResponse(message="تم حذف منطقة التوصيل.")


# ── Orders ────────────────────────────────────────────────────────────────────
def _order_list_payload(db: DbSession, order: Order) -> dict:
    items_count = int(
        db.execute(
            select(func.count()).select_from(OrderItem).where(OrderItem.order_id == order.id)
        ).scalar_one()
    )
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "source": order.source,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "delivery_area_name": order.delivery_area_name,
        "total": order.total,
        "payment_method": order.payment_method,
        "payment_status": db.execute(
            select(Invoice.payment_status).where(
                Invoice.order_id == order.id, Invoice.status == "active"
            )
        ).scalar_one_or_none()
        or PaymentStatus.UNPAID.value,
        "items_count": items_count,
        "created_at": order.created_at,
    }


@router.get("/orders", response_model=Page[OrderAdminListOut])
def list_orders(
    db: DbSession,
    admin: CurrentAdmin,
    pagination: PageParams,
    q: Annotated[str | None, Query(max_length=120)] = None,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
    source: OrderSource | None = None,
    payment_status: PaymentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Page[OrderAdminListOut]:
    stmt = select(Order)
    if order_status is not None:
        stmt = stmt.where(Order.status == order_status.value)
    if q:
        needle = f"%{q}%"
        stmt = stmt.where(
            (Order.order_number.like(needle.upper()))
            | (Order.customer_name.like(needle))
            | (Order.customer_phone.like(needle))
        )
    if source is not None:
        stmt = stmt.where(Order.source == source.value)
    active_invoice_exists = exists(
        select(Invoice.id).where(Invoice.order_id == Order.id, Invoice.status == "active")
    )
    active_payment_status = (
        select(Invoice.payment_status)
        .where(Invoice.order_id == Order.id, Invoice.status == "active")
        .scalar_subquery()
    )
    if payment_status is not None:
        if payment_status == PaymentStatus.UNPAID:
            stmt = stmt.where(
                or_(active_payment_status == payment_status.value, ~active_invoice_exists)
            )
        else:
            stmt = stmt.where(active_payment_status == payment_status.value)
    if date_from is not None:
        stmt = stmt.where(Order.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Order.created_at < date_to + timedelta(days=1))
    stmt = stmt.order_by(Order.id.desc())
    rows, total = catalog_service.paginate(
        db, stmt, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.build(
        [OrderAdminListOut.model_validate(_order_list_payload(db, row)) for row in rows],
        total,
        pagination.page,
        pagination.page_size,
    )


def _load_order(db: DbSession, order_id: int) -> Order:
    stmt = (
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.status_history),
            selectinload(Order.invoices),
            selectinload(Order.activities),
        )
        .where(Order.id == order_id)
    )
    order = db.execute(stmt).scalars().unique().one_or_none()
    if order is None:
        get_or_404(db, Order, order_id, "الطلب غير موجود.")
    return order


@router.get("/orders/{order_id}", response_model=OrderAdminOut)
def get_order(order_id: int, db: DbSession, admin: CurrentAdmin):
    order = _load_order(db, order_id)
    active_invoice = next((invoice for invoice in order.invoices if invoice.status == "active"), None)
    final_review = None
    if not order.is_locked and order.status != OrderStatus.CANCELLED.value:
        final_review = {
            "payment_method": order.payment_method,
            "items": order.items,
            "subtotal": order.subtotal,
            "discount": order.discount,
            "delivery_fee": order.delivery_fee,
            "total": order.total,
        }
    return {
        **{column.name: getattr(order, column.name) for column in Order.__table__.columns},
        "items": order.items,
        "status_history": order.status_history,
        "activities": order.activities,
        "final_review": final_review,
        "active_invoice": active_invoice,
        "invoices": order.invoices,
        "invoice": active_invoice,
        "payment_status": (
            active_invoice.payment_status if active_invoice else PaymentStatus.UNPAID.value
        ),
    }


@router.post("/orders/manual", response_model=OrderAdminOut, status_code=status.HTTP_201_CREATED)
def create_manual_order(payload: ManualOrderCreate, db: DbSession, admin: SuperAdmin):
    items: list[orders_service.ManualOrderItemDraft] = []
    for item in payload.items:
        if isinstance(item, ManualCatalogOrderItemInput):
            items.append(
                orders_service.ManualCatalogOrderItemDraft(
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                )
            )
        elif isinstance(item, ManualOrderItemInput):
            items.append(
                orders_service.ManualFreeformOrderItemDraft(
                    name=item.name,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                )
            )
    draft = orders_service.ManualOrderDraft(
        source=payload.source,
        source_note=payload.source_note,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=str(payload.customer_email) if payload.customer_email else None,
        address=payload.address,
        payment_method=payload.payment_method.value,
        customer_notes=payload.customer_notes,
        admin_notes=payload.admin_notes,
        discount=payload.discount,
        delivery_fee=payload.delivery_fee,
        items=tuple(items),
    )
    order = orders_service.create_manual_order(db, draft=draft, admin=admin)
    if payload.completion is not None:
        orders_service.complete_order(
            db,
            order_id=order.id,
            payment_method=payload.completion.payment_method.value,
            paid_amount=payload.completion.paid_amount,
            payment_details=payload.completion.payment_details,
            invoice_notes=payload.completion.invoice_notes,
            admin=admin,
        )
    db.commit()
    return get_order(order.id, db, admin)


@router.patch("/orders/{order_id}", response_model=OrderAdminOut)
def edit_order(
    order_id: int, payload: OrderAdminUpdate, db: DbSession, admin: CurrentAdmin
):
    draft = orders_service.AdminOrderEditDraft(
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=str(payload.customer_email) if payload.customer_email else None,
        address=payload.address,
        payment_method=payload.payment_method.value,
        customer_notes=payload.customer_notes,
        admin_notes=payload.admin_notes,
        discount=payload.discount,
        delivery_fee=payload.delivery_fee,
        status=payload.status.value,
        reason=payload.reason,
        items=tuple(
            orders_service.AdminOrderItemDraft(
                kind="catalog",
                order_item_id=None,
                product_id=item.product_id,
                variant_id=item.variant_id,
                name=None,
                description=None,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            if isinstance(item, AdminCatalogOrderItemInput)
            else orders_service.AdminOrderItemDraft(
                kind="manual",
                order_item_id=item.order_item_id,
                product_id=None,
                variant_id=None,
                name=item.name,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in payload.items
        ),
    )
    orders_service.edit_incomplete_order(
        db, order_id=order_id, draft=draft, admin=admin
    )
    db.commit()
    return get_order(order_id, db, admin)


@router.post("/orders/{order_id}/status", response_model=OrderAdminOut)
def update_order_status(
    order_id: int, payload: OrderStatusUpdate, db: DbSession, admin: CurrentAdmin
):
    order = _load_order(db, order_id)
    orders_service.change_status(
        db, order, payload.status.value, admin=admin, note=payload.note
    )
    db.commit()
    return get_order(order_id, db, admin)


@router.post("/orders/{order_id}/complete", response_model=OrderAdminOut)
def complete_order(
    order_id: int, payload: OrderCompletionRequest, db: DbSession, admin: CurrentAdmin
):
    orders_service.complete_order(
        db,
        order_id=order_id,
        payment_method=payload.payment_method.value,
        paid_amount=payload.paid_amount,
        payment_details=payload.payment_details,
        invoice_notes=payload.invoice_notes,
        admin=admin,
    )
    db.commit()
    return get_order(order_id, db, admin)


@router.post("/orders/{order_id}/reopen", response_model=OrderAdminOut)
def reopen_order(
    order_id: int, payload: OrderReopenRequest, db: DbSession, admin: SuperAdmin
):
    orders_service.reopen_completed_order(
        db, order_id=order_id, reason=payload.reason, admin=admin
    )
    db.commit()
    return get_order(order_id, db, admin)


@router.patch("/orders/{order_id}/notes", response_model=OrderAdminOut)
def update_order_notes(
    order_id: int, payload: OrderNotesUpdate, db: DbSession, admin: CurrentAdmin
):
    order = _load_order(db, order_id)
    orders_service.update_order_notes(
        db,
        order,
        admin_notes=payload.admin_notes,
        reason=payload.reason,
        admin=admin,
    )
    db.commit()
    return get_order(order_id, db, admin)
