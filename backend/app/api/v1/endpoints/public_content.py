"""Public store identity and editorial content."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Select, or_, select

from app.api.deps import DbSession, PageParams
from app.db.base import utcnow
from app.models import Article, Banner, DeliveryArea, HeroSlide, HomeSection, StaticPage
from app.schemas.common import Page
from app.schemas.content import (
    ArticleListOut,
    ArticleOut,
    BannerOut,
    HeroSlideOut,
    HomeSectionOut,
    StaticPageOut,
)
from app.schemas.marketing import DeliveryAreaOut
from app.schemas.store import StoreSettingsPublic
from app.services import catalog as catalog_service
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


@router.get("/banners", response_model=list[BannerOut])
def banners(db: DbSession, placement: Annotated[str | None, Query(max_length=32)] = None):
    stmt = _within_window(select(Banner), Banner)
    if placement:
        stmt = stmt.where(Banner.placement == placement)
    stmt = stmt.order_by(Banner.sort_order.asc(), Banner.id.asc())
    return list(db.execute(stmt).scalars().all())


@router.get("/home-sections", response_model=list[HomeSectionOut])
def home_sections(db: DbSession):
    stmt = (
        select(HomeSection)
        .where(HomeSection.is_visible.is_(True))
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


@router.get("/articles", response_model=Page[ArticleListOut])
def list_articles(db: DbSession, pagination: PageParams) -> Page[ArticleListOut]:
    stmt = (
        select(Article)
        .where(Article.is_published.is_(True))
        .order_by(Article.published_at.desc().nulls_last(), Article.id.desc())
    )
    rows, total = catalog_service.paginate(
        db, stmt, offset=pagination.offset, limit=pagination.page_size
    )
    items = [ArticleListOut.model_validate(row) for row in rows]
    return Page.build(items, total, pagination.page, pagination.page_size)


@router.get("/articles/{slug}", response_model=ArticleOut)
def get_article(slug: str, db: DbSession):
    article = db.execute(
        select(Article).where(Article.slug == slug, Article.is_published.is_(True))
    ).scalar_one_or_none()
    if article is None:
        raise _NOT_FOUND
    return article


@router.get("/pages/{slug}", response_model=StaticPageOut)
def get_page(slug: str, db: DbSession):
    page = db.execute(
        select(StaticPage).where(StaticPage.slug == slug, StaticPage.is_published.is_(True))
    ).scalar_one_or_none()
    if page is None:
        raise _NOT_FOUND
    return page
