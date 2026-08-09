from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.core.enums import BannerPlacement, HomeSectionType
from app.schemas.common import APIModel, UTCDateTime

_MAX_CONFIG_KEYS = 20
_SCRIPTISH = ("<script", "javascript:", "onerror=", "onload=", "<iframe")


def _reject_markup(value: str, field: str) -> str:
    lowered = value.lower()
    if any(token in lowered for token in _SCRIPTISH):
        raise ValueError(f"{field} must not contain markup or scripts")
    return value


# ── Hero slides ───────────────────────────────────────────────────────────────
class HeroSlideBase(APIModel):
    title: str = Field(min_length=1, max_length=250)
    subtitle: str | None = Field(default=None, max_length=250)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    button_label: str | None = Field(default=None, max_length=100)
    button_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    sort_order: int = 0
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def _window_is_ordered(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class HeroSlideCreate(HeroSlideBase):
    pass


class HeroSlideUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    subtitle: str | None = Field(default=None, max_length=250)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    button_label: str | None = Field(default=None, max_length=100)
    button_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    sort_order: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class HeroSlideOut(APIModel):
    id: int
    title: str
    subtitle: str | None = None
    description: str | None = None
    image_url: str | None = None
    button_label: str | None = None
    button_url: str | None = None
    sort_order: int


class HeroSlideAdminOut(HeroSlideOut):
    is_active: bool
    starts_at: UTCDateTime | None = None
    ends_at: UTCDateTime | None = None
    updated_at: UTCDateTime


# ── Banners ───────────────────────────────────────────────────────────────────
class BannerBase(APIModel):
    placement: BannerPlacement = BannerPlacement.HOME_SIDE
    title: str = Field(min_length=1, max_length=250)
    subtitle: str | None = Field(default=None, max_length=250)
    image_url: str | None = Field(default=None, max_length=500)
    link_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    sort_order: int = 0
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def _window_is_ordered(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class BannerCreate(BannerBase):
    pass


class BannerUpdate(APIModel):
    placement: BannerPlacement | None = None
    title: str | None = Field(default=None, min_length=1, max_length=250)
    subtitle: str | None = Field(default=None, max_length=250)
    image_url: str | None = Field(default=None, max_length=500)
    link_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    sort_order: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class BannerOut(APIModel):
    id: int
    placement: BannerPlacement
    title: str
    subtitle: str | None = None
    image_url: str | None = None
    link_url: str | None = None
    sort_order: int


class BannerAdminOut(BannerOut):
    is_active: bool
    starts_at: UTCDateTime | None = None
    ends_at: UTCDateTime | None = None
    updated_at: UTCDateTime


# ── Home sections ─────────────────────────────────────────────────────────────
class HomeSectionBase(APIModel):
    section_type: HomeSectionType
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    is_visible: bool = True
    sort_order: int = 0
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def _config_is_plain_data(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > _MAX_CONFIG_KEYS:
            raise ValueError(f"config supports at most {_MAX_CONFIG_KEYS} keys")
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("config keys must be strings")
            if isinstance(item, str):
                _reject_markup(item, f"config.{key}")
            elif not isinstance(item, (int, float, bool, list, type(None))):
                raise ValueError("config values must be scalars or lists")
        return value

    @field_validator("title", "description")
    @classmethod
    def _plain_text(cls, value: str | None) -> str | None:
        return _reject_markup(value, "text") if value else value


class HomeSectionCreate(HomeSectionBase):
    section_key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")


class HomeSectionUpdate(APIModel):
    section_type: HomeSectionType | None = None
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    is_visible: bool | None = None
    sort_order: int | None = None
    config: dict[str, Any] | None = None


class HomeSectionOut(APIModel):
    id: int
    section_key: str
    section_type: HomeSectionType
    title: str | None = None
    description: str | None = None
    sort_order: int
    config: dict[str, Any] = Field(default_factory=dict)


class HomeSectionAdminOut(HomeSectionOut):
    is_visible: bool
    updated_at: UTCDateTime


# ── Articles ──────────────────────────────────────────────────────────────────
class ArticleBase(APIModel):
    title: str = Field(min_length=1, max_length=250)
    excerpt: str | None = None
    content: str = ""
    featured_image_url: str | None = Field(default=None, max_length=500)
    category_label: str | None = Field(default=None, max_length=100)
    author_name: str | None = Field(default=None, max_length=150)
    is_published: bool = False
    published_at: datetime | None = None
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None


class ArticleCreate(ArticleBase):
    slug: str | None = Field(default=None, max_length=260)


class ArticleUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    slug: str | None = Field(default=None, max_length=260)
    excerpt: str | None = None
    content: str | None = None
    featured_image_url: str | None = Field(default=None, max_length=500)
    category_label: str | None = Field(default=None, max_length=100)
    author_name: str | None = Field(default=None, max_length=150)
    is_published: bool | None = None
    published_at: datetime | None = None
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None


class ArticleListOut(APIModel):
    id: int
    title: str
    slug: str
    excerpt: str | None = None
    featured_image_url: str | None = None
    category_label: str | None = None
    author_name: str | None = None
    published_at: UTCDateTime | None = None


class ArticleOut(ArticleListOut):
    content: str
    seo_title: str | None = None
    seo_description: str | None = None


class ArticleAdminOut(ArticleOut):
    is_published: bool
    created_at: UTCDateTime
    updated_at: UTCDateTime


# ── Static pages ──────────────────────────────────────────────────────────────
class StaticPageBase(APIModel):
    title: str = Field(min_length=1, max_length=250)
    lead: str | None = None
    content: str = ""
    is_published: bool = True
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None


class StaticPageCreate(StaticPageBase):
    slug: str | None = Field(default=None, max_length=160)


class StaticPageUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    slug: str | None = Field(default=None, max_length=160)
    lead: str | None = None
    content: str | None = None
    is_published: bool | None = None
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None


class StaticPageOut(APIModel):
    id: int
    title: str
    slug: str
    lead: str | None = None
    content: str
    seo_title: str | None = None
    seo_description: str | None = None


class StaticPageAdminOut(StaticPageOut):
    is_published: bool
    updated_at: UTCDateTime
