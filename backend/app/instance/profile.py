"""Instance profile: the validated, non-secret description of one store instance.

A profile carries identity and defaults. It never carries credentials — see
`assert_no_secret_like_keys`, and note that every model below forbids extra keys, so a
credential-shaped field fails validation before any of this runs.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError, field_validator

from app.core.enums import HomeSectionType

# Profile schema versions this build understands. Bump when the shape changes.
SUPPORTED_PROFILE_SCHEMA_VERSIONS = frozenset({1})

# Fixed, explicit feature set — every one already implemented. Not a plugin system.
SUPPORTED_FEATURES = ("packages", "silicone_molds", "articles", "coupons")

SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{1,38}[a-z0-9])$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
TIMEZONE_RE = re.compile(r"^[A-Za-z]+(?:/[A-Za-z0-9_+\-]+)+$|^UTC$")
LOCALE_RE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")

# Key fragments that must never appear anywhere in a profile, at any depth.
SECRET_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "credential",
    "private_key",
    "api_key",
    "access_key",
    "database_url",
    "dsn",
    "passwd",
)


class ProfileError(ValueError):
    """A profile is unreadable, malformed or semantically invalid."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DomainProfile(_Strict):
    primary: str | None = Field(default=None, max_length=253)
    aliases: list[str] = Field(default_factory=list)

    @field_validator("primary")
    @classmethod
    def _check_primary(cls, value: str | None) -> str | None:
        if value and ("/" in value or ":" in value):
            raise ValueError("domain must be a bare hostname, without scheme or path")
        return value


class ContactProfile(_Strict):
    phone: str | None = Field(default=None, max_length=40)
    whatsapp: str | None = Field(default=None, max_length=40)
    # The same EmailStr the API's StoreSettings projection uses. Anything looser lets a
    # profile validate and apply cleanly, then write an address that `/store/settings`
    # cannot serialise — a 500 that takes the whole storefront down on first load.
    email: EmailStr | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=300)
    working_hours: str | None = Field(default=None, max_length=200)
    instagram_url: str | None = Field(default=None, max_length=500)
    facebook_url: str | None = Field(default=None, max_length=500)


class ThemeProfile(_Strict):
    primary_color: str = "#7F568F"
    secondary_color: str = "#D19F57"
    accent_color: str = "#4C7C63"

    @field_validator("primary_color", "secondary_color", "accent_color")
    @classmethod
    def _check_color(cls, value: str) -> str:
        if not COLOR_RE.match(value):
            raise ValueError(f"{value!r} is not a #RRGGBB colour")
        return value.upper()


class HomeSectionProfile(_Strict):
    key: str = Field(max_length=64)
    type: str
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    sort_order: int = 0
    is_visible: bool = True
    requires_feature: str | None = None

    @field_validator("type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        allowed = {member.value for member in HomeSectionType}
        if value not in allowed:
            raise ValueError(f"unknown home section type {value!r}; allowed: {sorted(allowed)}")
        return value

    @field_validator("requires_feature")
    @classmethod
    def _check_feature(cls, value: str | None) -> str | None:
        if value is not None and value not in SUPPORTED_FEATURES:
            raise ValueError(
                f"unknown feature {value!r}; supported: {list(SUPPORTED_FEATURES)}"
            )
        return value


class StaticPageProfile(_Strict):
    slug: str = Field(max_length=160)
    title: str = Field(max_length=250)
    lead: str | None = None
    is_published: bool = True

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, value: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", value):
            raise ValueError(f"{value!r} is not a valid page slug")
        return value


class StoreProfile(_Strict):
    name: str = Field(min_length=1, max_length=150)
    # The Arabic display name, when the business writes its name both ways. The
    # storefront and the invoice prefer this one; `name` stays the fallback.
    display_name_ar: str | None = Field(default=None, max_length=150)
    tagline: str | None = Field(default=None, max_length=200)
    locale: str = "ar"
    timezone: str = "UTC"
    currency_code: str = "ILS"
    currency_symbol: str = Field(default="₪", max_length=8)
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None

    @field_validator("currency_code")
    @classmethod
    def _check_currency(cls, value: str) -> str:
        if not CURRENCY_RE.match(value):
            raise ValueError(f"{value!r} is not a 3-letter uppercase currency code")
        return value

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        if not TIMEZONE_RE.match(value):
            raise ValueError(f"{value!r} is not an IANA timezone such as 'Asia/Hebron'")
        return value

    @field_validator("locale")
    @classmethod
    def _check_locale(cls, value: str) -> str:
        if not LOCALE_RE.match(value):
            raise ValueError(f"{value!r} is not a locale such as 'ar' or 'ar-PS'")
        return value


class InstanceProfile(_Strict):
    """The whole profile document."""

    profile_schema_version: int
    template_version: str
    client_slug: str
    store: StoreProfile
    domain: DomainProfile = Field(default_factory=DomainProfile)
    contact: ContactProfile = Field(default_factory=ContactProfile)
    theme: ThemeProfile = Field(default_factory=ThemeProfile)
    features: dict[str, bool] = Field(default_factory=dict)
    home_sections: list[HomeSectionProfile] = Field(default_factory=list)
    static_pages: list[StaticPageProfile] = Field(default_factory=list)

    @field_validator("profile_schema_version")
    @classmethod
    def _check_schema_version(cls, value: int) -> int:
        if value not in SUPPORTED_PROFILE_SCHEMA_VERSIONS:
            raise ValueError(
                f"profile_schema_version {value} is not supported; "
                f"this build understands {sorted(SUPPORTED_PROFILE_SCHEMA_VERSIONS)}"
            )
        return value

    @field_validator("client_slug")
    @classmethod
    def _check_slug(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError(
                f"{value!r} is not a valid client slug: lowercase letters, digits and "
                "hyphens, 3-40 characters, not starting or ending with a hyphen"
            )
        return value

    @field_validator("features")
    @classmethod
    def _check_features(cls, value: dict[str, bool]) -> dict[str, bool]:
        unknown = sorted(set(value) - set(SUPPORTED_FEATURES))
        if unknown:
            raise ValueError(
                f"unknown feature flag(s) {unknown}; supported: {list(SUPPORTED_FEATURES)}"
            )
        return value

    @field_validator("home_sections")
    @classmethod
    def _unique_section_keys(cls, value: list[HomeSectionProfile]) -> list[HomeSectionProfile]:
        keys = [section.key for section in value]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(f"duplicate home section key(s): {duplicates}")
        return value

    @field_validator("static_pages")
    @classmethod
    def _unique_page_slugs(cls, value: list[StaticPageProfile]) -> list[StaticPageProfile]:
        slugs = [page.slug for page in value]
        duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
        if duplicates:
            raise ValueError(f"duplicate static page slug(s): {duplicates}")
        return value

    def enabled_features(self) -> list[str]:
        """Declared flags win; anything not mentioned defaults to enabled."""
        return [name for name in SUPPORTED_FEATURES if self.features.get(name, True)]

    def canonical_document(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def profile_hash(self) -> str:
        return hashlib.sha256(self.canonical_document().encode("utf-8")).hexdigest()


def assert_no_secret_like_keys(data: Any, path: str = "") -> None:
    """Reject credential-shaped keys at any depth, with a message that says why.

    `extra="forbid"` already rejects unknown keys, but this runs first so the operator
    is told the real reason instead of a generic "unexpected field".
    """
    if isinstance(data, dict):
        for key, value in data.items():
            here = f"{path}.{key}" if path else str(key)
            lowered = str(key).lower()
            for fragment in SECRET_KEY_FRAGMENTS:
                if fragment in lowered:
                    raise ProfileError(
                        f"{here!r} looks like a secret. Profiles are non-secret and are "
                        "committed or shared; keep credentials in environment variables."
                    )
            assert_no_secret_like_keys(value, here)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            assert_no_secret_like_keys(item, f"{path}[{index}]")


def parse_profile(data: Any, *, source: str = "<memory>") -> InstanceProfile:
    if not isinstance(data, dict):
        raise ProfileError(f"{source}: profile must be a YAML mapping at the top level.")
    assert_no_secret_like_keys(data)
    try:
        return InstanceProfile.model_validate(data)
    except ValidationError as exc:
        details = "\n".join(
            f"  - {'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
            for err in exc.errors()
        )
        raise ProfileError(f"{source}: invalid instance profile\n{details}") from exc


def load_profile(path: str | Path) -> InstanceProfile:
    file_path = Path(path)
    if not file_path.is_file():
        raise ProfileError(f"Profile not found: {file_path}")
    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileError(f"{file_path}: not valid YAML — {exc}") from exc
    if raw is None:
        raise ProfileError(f"{file_path}: profile is empty.")
    return parse_profile(raw, source=str(file_path))
