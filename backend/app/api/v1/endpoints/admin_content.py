"""Admin management of store identity, homepage composition and editorial content."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.crud import apply_updates, get_or_404
from app.api.deps import CurrentAdmin, DbSession, PageParams
from app.db.base import utcnow
from app.models import Article, Banner, HeroSlide, HomeSection, StaticPage
from app.schemas.common import MessageResponse, Page
from app.schemas.content import (
    ArticleAdminOut,
    ArticleCreate,
    ArticleUpdate,
    BannerAdminOut,
    BannerCreate,
    BannerUpdate,
    HeroSlideAdminOut,
    HeroSlideCreate,
    HeroSlideUpdate,
    HomeSectionAdminOut,
    HomeSectionCreate,
    HomeSectionUpdate,
    StaticPageAdminOut,
    StaticPageCreate,
    StaticPageUpdate,
)
from app.schemas.store import StoreSettingsAdmin, StoreSettingsUpdate
from app.services import audit as audit_service
from app.services import catalog as catalog_service
from app.services import store_settings as settings_service
from app.services.errors import ConflictError
from app.services.slugs import unique_slug

router = APIRouter(prefix="/admin", tags=["admin-content"])


# ── Store settings ────────────────────────────────────────────────────────────
@router.get("/settings", response_model=StoreSettingsAdmin)
def get_settings(db: DbSession, admin: CurrentAdmin):
    row = settings_service.get_or_create_settings(db)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/settings", response_model=StoreSettingsAdmin)
def update_settings(payload: StoreSettingsUpdate, db: DbSession, admin: CurrentAdmin):
    row = settings_service.get_or_create_settings(db)
    changed = apply_updates(row, payload)
    audit_service.record(
        db,
        admin=admin,
        action="settings.updated",
        entity_type="store_settings",
        entity_id=row.id,
        meta={"fields": changed},
    )
    db.commit()
    db.refresh(row)
    return row


# ── Hero slides ───────────────────────────────────────────────────────────────
@router.get("/hero-slides", response_model=list[HeroSlideAdminOut])
def list_hero_slides(db: DbSession, admin: CurrentAdmin):
    stmt = select(HeroSlide).order_by(HeroSlide.sort_order.asc(), HeroSlide.id.asc())
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/hero-slides", response_model=HeroSlideAdminOut, status_code=status.HTTP_201_CREATED
)
def create_hero_slide(payload: HeroSlideCreate, db: DbSession, admin: CurrentAdmin):
    slide = HeroSlide(**payload.model_dump())
    db.add(slide)
    db.flush()
    audit_service.record(
        db,
        admin=admin,
        action="hero_slide.created",
        entity_type="hero_slide",
        entity_id=slide.id,
        meta={"title": slide.title},
    )
    db.commit()
    db.refresh(slide)
    return slide


@router.patch("/hero-slides/{slide_id}", response_model=HeroSlideAdminOut)
def update_hero_slide(
    slide_id: int, payload: HeroSlideUpdate, db: DbSession, admin: CurrentAdmin
):
    slide = get_or_404(db, HeroSlide, slide_id, "الشريحة غير موجودة.")
    changed = apply_updates(slide, payload)
    audit_service.record(
        db,
        admin=admin,
        action="hero_slide.updated",
        entity_type="hero_slide",
        entity_id=slide.id,
        meta={"fields": changed},
    )
    db.commit()
    db.refresh(slide)
    return slide


@router.delete("/hero-slides/{slide_id}", response_model=MessageResponse)
def delete_hero_slide(slide_id: int, db: DbSession, admin: CurrentAdmin):
    slide = get_or_404(db, HeroSlide, slide_id, "الشريحة غير موجودة.")
    audit_service.record(
        db,
        admin=admin,
        action="hero_slide.deleted",
        entity_type="hero_slide",
        entity_id=slide.id,
        meta={"title": slide.title},
    )
    db.delete(slide)
    db.commit()
    return MessageResponse(message="تم حذف الشريحة.")


# ── Banners ───────────────────────────────────────────────────────────────────
@router.get("/banners", response_model=list[BannerAdminOut])
def list_banners(db: DbSession, admin: CurrentAdmin):
    stmt = select(Banner).order_by(Banner.placement.asc(), Banner.sort_order.asc(), Banner.id.asc())
    return list(db.execute(stmt).scalars().all())


@router.post("/banners", response_model=BannerAdminOut, status_code=status.HTTP_201_CREATED)
def create_banner(payload: BannerCreate, db: DbSession, admin: CurrentAdmin):
    data = payload.model_dump()
    data["placement"] = payload.placement.value
    banner = Banner(**data)
    db.add(banner)
    db.flush()
    audit_service.record(
        db,
        admin=admin,
        action="banner.created",
        entity_type="banner",
        entity_id=banner.id,
        meta={"title": banner.title, "placement": banner.placement},
    )
    db.commit()
    db.refresh(banner)
    return banner


@router.patch("/banners/{banner_id}", response_model=BannerAdminOut)
def update_banner(banner_id: int, payload: BannerUpdate, db: DbSession, admin: CurrentAdmin):
    banner = get_or_404(db, Banner, banner_id, "البانر غير موجود.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("placement") is not None:
        data["placement"] = data["placement"].value
    changed: list[str] = []
    for field, value in data.items():
        if getattr(banner, field, None) != value:
            setattr(banner, field, value)
            changed.append(field)
    audit_service.record(
        db,
        admin=admin,
        action="banner.updated",
        entity_type="banner",
        entity_id=banner.id,
        meta={"fields": changed},
    )
    db.commit()
    db.refresh(banner)
    return banner


@router.delete("/banners/{banner_id}", response_model=MessageResponse)
def delete_banner(banner_id: int, db: DbSession, admin: CurrentAdmin):
    banner = get_or_404(db, Banner, banner_id, "البانر غير موجود.")
    audit_service.record(
        db,
        admin=admin,
        action="banner.deleted",
        entity_type="banner",
        entity_id=banner.id,
        meta={"title": banner.title},
    )
    db.delete(banner)
    db.commit()
    return MessageResponse(message="تم حذف البانر.")


# ── Home sections ─────────────────────────────────────────────────────────────
def list_home_sections(db: DbSession, admin: CurrentAdmin):
    stmt = select(HomeSection).order_by(HomeSection.sort_order.asc(), HomeSection.id.asc())
    return list(db.execute(stmt).scalars().all())


def create_home_section(payload: HomeSectionCreate, db: DbSession, admin: CurrentAdmin):
    exists = db.execute(
        select(HomeSection.id).where(HomeSection.section_key == payload.section_key)
    ).first()
    if exists is not None:
        raise ConflictError("مفتاح القسم مستخدم مسبقاً.", code="section_key_taken")
    data = payload.model_dump()
    data["section_type"] = payload.section_type.value
    section = HomeSection(**data)
    db.add(section)
    db.flush()
    audit_service.record(
        db,
        admin=admin,
        action="home_section.created",
        entity_type="home_section",
        entity_id=section.id,
        meta={"section_key": section.section_key},
    )
    db.commit()
    db.refresh(section)
    return section


def update_home_section(
    section_id: int, payload: HomeSectionUpdate, db: DbSession, admin: CurrentAdmin
):
    section = get_or_404(db, HomeSection, section_id, "قسم الصفحة الرئيسية غير موجود.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("section_type") is not None:
        data["section_type"] = data["section_type"].value
    changed: list[str] = []
    for field, value in data.items():
        if getattr(section, field, None) != value:
            setattr(section, field, value)
            changed.append(field)
    audit_service.record(
        db,
        admin=admin,
        action="home_section.updated",
        entity_type="home_section",
        entity_id=section.id,
        meta={"fields": changed, "section_key": section.section_key},
    )
    db.commit()
    db.refresh(section)
    return section


def delete_home_section(section_id: int, db: DbSession, admin: CurrentAdmin):
    section = get_or_404(db, HomeSection, section_id, "قسم الصفحة الرئيسية غير موجود.")
    audit_service.record(
        db,
        admin=admin,
        action="home_section.deleted",
        entity_type="home_section",
        entity_id=section.id,
        meta={"section_key": section.section_key},
    )
    db.delete(section)
    db.commit()
    return MessageResponse(message="تم حذف القسم.")


# ── Articles ──────────────────────────────────────────────────────────────────
@router.get("/articles", response_model=Page[ArticleAdminOut])
def list_articles(
    db: DbSession,
    admin: CurrentAdmin,
    pagination: PageParams,
    q: Annotated[str | None, Query(max_length=120)] = None,
    is_published: bool | None = None,
) -> Page[ArticleAdminOut]:
    stmt = select(Article)
    if q:
        stmt = stmt.where(Article.title.like(f"%{q}%"))
    if is_published is not None:
        stmt = stmt.where(Article.is_published.is_(is_published))
    stmt = stmt.order_by(Article.id.desc())
    rows, total = catalog_service.paginate(
        db, stmt, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.build(
        [ArticleAdminOut.model_validate(row) for row in rows],
        total,
        pagination.page,
        pagination.page_size,
    )


@router.post("/articles", response_model=ArticleAdminOut, status_code=status.HTTP_201_CREATED)
def create_article(payload: ArticleCreate, db: DbSession, admin: CurrentAdmin):
    data = payload.model_dump(exclude={"slug"})
    article = Article(**data, slug=unique_slug(db, Article, payload.slug or payload.title))
    if article.is_published and article.published_at is None:
        article.published_at = utcnow()
    db.add(article)
    db.flush()
    audit_service.record(
        db,
        admin=admin,
        action="article.created",
        entity_type="article",
        entity_id=article.id,
        meta={"title": article.title, "published": article.is_published},
    )
    db.commit()
    db.refresh(article)
    return article


@router.patch("/articles/{article_id}", response_model=ArticleAdminOut)
def update_article(
    article_id: int, payload: ArticleUpdate, db: DbSession, admin: CurrentAdmin
):
    article = get_or_404(db, Article, article_id, "المقال غير موجود.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("slug"):
        data["slug"] = unique_slug(db, Article, data["slug"], exclude_id=article.id)
    changed: list[str] = []
    for field, value in data.items():
        if getattr(article, field, None) != value:
            setattr(article, field, value)
            changed.append(field)
    if article.is_published and article.published_at is None:
        article.published_at = utcnow()
    audit_service.record(
        db,
        admin=admin,
        action="article.updated",
        entity_type="article",
        entity_id=article.id,
        meta={"fields": changed},
    )
    db.commit()
    db.refresh(article)
    return article


@router.delete("/articles/{article_id}", response_model=MessageResponse)
def delete_article(article_id: int, db: DbSession, admin: CurrentAdmin):
    article = get_or_404(db, Article, article_id, "المقال غير موجود.")
    audit_service.record(
        db,
        admin=admin,
        action="article.deleted",
        entity_type="article",
        entity_id=article.id,
        meta={"title": article.title},
    )
    db.delete(article)
    db.commit()
    return MessageResponse(message="تم حذف المقال.")


# ── Static pages ──────────────────────────────────────────────────────────────
@router.get("/pages", response_model=list[StaticPageAdminOut])
def list_pages(db: DbSession, admin: CurrentAdmin):
    return list(db.execute(select(StaticPage).order_by(StaticPage.id.asc())).scalars().all())


@router.post("/pages", response_model=StaticPageAdminOut, status_code=status.HTTP_201_CREATED)
def create_page(payload: StaticPageCreate, db: DbSession, admin: CurrentAdmin):
    data = payload.model_dump(exclude={"slug"})
    page = StaticPage(**data, slug=unique_slug(db, StaticPage, payload.slug or payload.title))
    db.add(page)
    db.flush()
    audit_service.record(
        db,
        admin=admin,
        action="page.created",
        entity_type="static_page",
        entity_id=page.id,
        meta={"slug": page.slug},
    )
    db.commit()
    db.refresh(page)
    return page


@router.patch("/pages/{page_id}", response_model=StaticPageAdminOut)
def update_page(page_id: int, payload: StaticPageUpdate, db: DbSession, admin: CurrentAdmin):
    page = get_or_404(db, StaticPage, page_id, "الصفحة غير موجودة.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("slug"):
        data["slug"] = unique_slug(db, StaticPage, data["slug"], exclude_id=page.id)
    changed: list[str] = []
    for field, value in data.items():
        if getattr(page, field, None) != value:
            setattr(page, field, value)
            changed.append(field)
    audit_service.record(
        db,
        admin=admin,
        action="page.updated",
        entity_type="static_page",
        entity_id=page.id,
        meta={"fields": changed, "slug": page.slug},
    )
    db.commit()
    db.refresh(page)
    return page


@router.delete("/pages/{page_id}", response_model=MessageResponse)
def delete_page(page_id: int, db: DbSession, admin: CurrentAdmin):
    page = get_or_404(db, StaticPage, page_id, "الصفحة غير موجودة.")
    audit_service.record(
        db,
        admin=admin,
        action="page.deleted",
        entity_type="static_page",
        entity_id=page.id,
        meta={"slug": page.slug},
    )
    db.delete(page)
    db.commit()
    return MessageResponse(message="تم حذف الصفحة.")
