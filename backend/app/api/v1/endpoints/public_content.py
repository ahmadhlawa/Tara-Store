"""Public store identity and editorial content."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Select, or_, select

from app.api.deps import DbSession
from app.core.enums import HomeSectionType
from app.db.base import utcnow
from app.models import DeliveryArea, HeroSlide, HomeSection, StaticPage
from app.schemas.content import (
    HeroSlideOut,
    HomeSectionOut,
    StaticPageOut,
)
from app.schemas.marketing import DeliveryAreaOut
from app.schemas.store import StoreSettingsPublic
from app.services import store_settings as settings_service

router = APIRouter(tags=["public-content"])

# Store identity is served from its own router because it must stay reachable while
# maintenance mode is on — the maintenance screen is rendered from it. `router` is the
# gated one; see `app/api/v1/router.py`.
identity_router = APIRouter(tags=["public-content"])

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "not_found", "message": "العنصر غير موجود."},
)


def _within_window(stmt: Select, model) -> Select:
    now = utcnow()
    return stmt.where(
        model.is_active.is_(True),
        or_(model.starts_at.is_(None), model.starts_at <= now),
        or_(model.ends_at.is_(None), model.ends_at >= now),
    )


@identity_router.get("/store/settings", response_model=StoreSettingsPublic)
def store_settings(db: DbSession):
    return settings_service.public_settings(db)


@router.get("/hero-slides", response_model=list[HeroSlideOut])
def hero_slides(db: DbSession):
    stmt = _within_window(select(HeroSlide), HeroSlide).order_by(
        HeroSlide.sort_order.asc(), HeroSlide.id.asc()
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/home-sections", response_model=list[HomeSectionOut])
def home_sections(db: DbSession):
    stmt = (
        select(HomeSection)
        .where(
            HomeSection.is_visible.is_(True),
            HomeSection.section_type.in_([section.value for section in HomeSectionType]),
        )
        .order_by(HomeSection.sort_order.asc(), HomeSection.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/delivery-areas", response_model=list[DeliveryAreaOut])
def delivery_areas(db: DbSession):
    stmt = (
        select(DeliveryArea)
        .where(DeliveryArea.is_active.is_(True))
        .order_by(DeliveryArea.sort_order.asc(), DeliveryArea.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/pages/{slug}", response_model=StaticPageOut)
def get_page(slug: str, db: DbSession):
    page = db.execute(
        select(StaticPage).where(StaticPage.slug == slug, StaticPage.is_published.is_(True))
    ).scalar_one_or_none()
    if page is None:
        raise _NOT_FOUND
    return page
