"""Client bootstrap: apply an instance profile to an empty database.

`plan` and `apply` share the planner below, so a plan is an honest preview rather than a
separate re-derivation.

What this does **not** do: create products, orders, coupons or admin accounts. Demo
content is the separate `scripts.seed` workflow, and admin creation is the separate
`app.initial_data` command.

The central safety rule is that bootstrap never overwrites owner-edited content. Rows are
created when missing and skipped when present; settings fields are filled only when empty
or still at their shipped default, and a static page is refreshed only while its body is
still blank — the state a bootstrap-created placeholder is in, and the only one where
there is no owner text to lose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.template_version import template_version
from app.db.base import utcnow
from app.instance.profile import InstanceProfile, StaticPageProfile
from app.models import DeliveryArea, HomeSection, InstanceMetadata, StaticPage, StoreSettings
from app.models.store import STORE_SETTINGS_DEFAULTS
from app.services import store_settings as settings_service

Outcome = Literal["create", "update", "skip", "conflict"]

# The exact body shipped in Tara's original production profile. This one-time
# compatibility marker lets bootstrap replace only that known, unedited policy.
LEGACY_TARA_RETURN_POLICY_SHA256 = "49ca4cc312a648777443861b7c6258a31a973fb5118058b6e1e533bc0f758670"


class InstanceConflictError(RuntimeError):
    """The database already belongs to a different instance."""


@dataclass(frozen=True)
class PlannedAction:
    outcome: Outcome
    target: str
    detail: str = ""

    def render(self) -> str:
        suffix = f" — {self.detail}" if self.detail else ""
        return f"[{self.outcome:8}] {self.target}{suffix}"


@dataclass
class Plan:
    actions: list[PlannedAction] = field(default_factory=list)

    @property
    def has_conflict(self) -> bool:
        return any(action.outcome == "conflict" for action in self.actions)

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for action in self.actions:
            result[action.outcome] = result.get(action.outcome, 0) + 1
        return result


def _existing_metadata(db: Session) -> InstanceMetadata | None:
    return db.execute(select(InstanceMetadata).limit(1)).scalar_one_or_none()


def _settings_field_is_untouched(row: StoreSettings, attribute: str) -> bool:
    """True when the owner has not set this field through Admin.

    A field counts as untouched if it is empty, or still equal to the shipped default.
    """
    current = getattr(row, attribute, None)
    if current in (None, ""):
        return True
    return attribute in STORE_SETTINGS_DEFAULTS and current == STORE_SETTINGS_DEFAULTS[attribute]


def _settings_updates(row: StoreSettings, profile: InstanceProfile) -> dict[str, object]:
    """The settings fields bootstrap would fill, skipping anything owner-edited."""
    desired: dict[str, object | None] = {
        "store_name": profile.store.name,
        "store_name_ar": profile.store.display_name_ar,
        "store_tagline": profile.store.tagline,
        "currency_code": profile.store.currency_code,
        "currency_symbol": profile.store.currency_symbol,
        "seo_title": profile.store.seo_title,
        "seo_description": profile.store.seo_description,
        "primary_color": profile.theme.primary_color,
        "secondary_color": profile.theme.secondary_color,
        "accent_color": profile.theme.accent_color,
        "phone": profile.contact.phone,
        "whatsapp": profile.contact.whatsapp,
        "email": profile.contact.email,
        "address": profile.contact.address,
        "location_url": profile.contact.location_url,
        "working_hours": profile.contact.working_hours,
        "instagram_url": profile.contact.instagram_url,
        "facebook_url": profile.contact.facebook_url,
        "tiktok_url": profile.contact.tiktok_url,
        "youtube_url": profile.contact.youtube_url,
        "instagram_visible": profile.contact.instagram_visible,
        "facebook_visible": profile.contact.facebook_visible,
        "tiktok_visible": profile.contact.tiktok_visible,
        "youtube_visible": profile.contact.youtube_visible,
    }
    return {
        attribute: value
        for attribute, value in desired.items()
        # Skip anything the owner has edited, and anything already at the wanted value —
        # so a repeated bootstrap reports "skip" rather than a no-op "update".
        if value not in (None, "")
        and _settings_field_is_untouched(row, attribute)
        and getattr(row, attribute, None) != value
    }


def _page_updates(row: StaticPage, page: StaticPageProfile) -> dict[str, object]:
    """The page fields bootstrap would fill on a page that already exists.

    A page is only ever refreshed while its body is still blank — that is what a
    bootstrap-created placeholder looks like, and it is the one state in which no
    owner text can be lost. The moment a body exists, whoever wrote it owns the
    page and bootstrap skips it entirely.
    """
    content = (row.content or "").strip()
    is_legacy_tara_policy = (
        page.slug == "return-policy"
        and sha256(content.encode("utf-8")).hexdigest() == LEGACY_TARA_RETURN_POLICY_SHA256
    )
    if content and not is_legacy_tara_policy:
        return {}
    desired: dict[str, object | None] = {
        "title": page.title,
        "lead": page.lead,
        "content": page.content,
        "seo_title": page.title,
        "seo_description": (page.lead or "")[:150] or None,
    }
    return {
        attribute: value
        for attribute, value in desired.items()
        if value not in (None, "") and getattr(row, attribute, None) != value
    }


def _wanted_sections(profile: InstanceProfile) -> list:
    enabled = set(profile.enabled_features())
    return [
        section
        for section in sorted(profile.home_sections, key=lambda s: (s.sort_order, s.key))
        if section.requires_feature is None or section.requires_feature in enabled
    ]


def build_plan(db: Session, profile: InstanceProfile) -> Plan:
    """Compute the intended actions. Deterministic, and writes nothing."""
    plan = Plan()

    metadata = _existing_metadata(db)
    if metadata is None:
        plan.actions.append(
            PlannedAction("create", "instance_metadata", f"slug={profile.client_slug}")
        )
    elif metadata.instance_slug != profile.client_slug:
        plan.actions.append(
            PlannedAction(
                "conflict",
                "instance_metadata",
                f"database belongs to {metadata.instance_slug!r}, "
                f"profile declares {profile.client_slug!r}",
            )
        )
    else:
        plan.actions.append(
            PlannedAction("update", "instance_metadata", "refresh last_bootstrap_at")
        )

    settings_row = db.execute(select(StoreSettings).limit(1)).scalar_one_or_none()
    if settings_row is None:
        plan.actions.append(
            PlannedAction("create", "store_settings", f"name={profile.store.name!r}")
        )
    else:
        updates = _settings_updates(settings_row, profile)
        if updates:
            plan.actions.append(
                PlannedAction(
                    "update", "store_settings", f"fill {', '.join(sorted(updates))}"
                )
            )
        else:
            plan.actions.append(
                PlannedAction("skip", "store_settings", "already configured by the owner")
            )

    existing_sections = {
        key for (key,) in db.execute(select(HomeSection.section_key)).all()
    }
    for section in _wanted_sections(profile):
        target = f"home_section:{section.key}"
        if section.key in existing_sections:
            plan.actions.append(PlannedAction("skip", target, "exists; owner content preserved"))
        else:
            plan.actions.append(PlannedAction("create", target, section.type))

    existing_pages = {row.slug: row for row in db.execute(select(StaticPage)).scalars()}
    for page in sorted(profile.static_pages, key=lambda p: p.slug):
        target = f"static_page:{page.slug}"
        existing = existing_pages.get(page.slug)
        if existing is None:
            plan.actions.append(PlannedAction("create", target, page.title))
            continue
        updates = _page_updates(existing, page)
        if updates:
            plan.actions.append(
                PlannedAction("update", target, f"fill {', '.join(sorted(updates))}")
            )
        else:
            plan.actions.append(PlannedAction("skip", target, "exists; owner content preserved"))

    existing_areas = {name for (name,) in db.execute(select(DeliveryArea.name)).all()}
    for area in profile.delivery_areas:
        target = f"delivery_area:{area.name}"
        if area.name in existing_areas:
            plan.actions.append(PlannedAction("skip", target, "exists; owner values preserved"))
        else:
            plan.actions.append(PlannedAction("create", target, f"fee={area.delivery_fee}"))

    return plan


def apply_profile(db: Session, profile: InstanceProfile) -> Plan:
    """Execute the plan. Idempotent, and never overwrites owner-edited content."""
    plan = build_plan(db, profile)
    if plan.has_conflict:
        conflict = next(a for a in plan.actions if a.outcome == "conflict")
        raise InstanceConflictError(conflict.detail)

    now = utcnow()
    version = template_version()

    settings_row = settings_service.get_or_create_settings(db)
    for attribute, value in _settings_updates(settings_row, profile).items():
        setattr(settings_row, attribute, value)

    existing_sections = {
        key for (key,) in db.execute(select(HomeSection.section_key)).all()
    }
    for section in _wanted_sections(profile):
        if section.key in existing_sections:
            continue
        db.add(
            HomeSection(
                section_key=section.key,
                section_type=section.type,
                title=section.title,
                description=section.description,
                sort_order=section.sort_order,
                is_visible=section.is_visible,
                config={},
            )
        )

    existing_pages = {row.slug: row for row in db.execute(select(StaticPage)).scalars()}
    for page in sorted(profile.static_pages, key=lambda p: p.slug):
        existing = existing_pages.get(page.slug)
        if existing is not None:
            for attribute, value in _page_updates(existing, page).items():
                setattr(existing, attribute, value)
            continue
        db.add(
            StaticPage(
                slug=page.slug,
                title=page.title,
                lead=page.lead,
                content=page.content or "",
                is_published=page.is_published,
                seo_title=page.title,
                seo_description=(page.lead or "")[:150] or None,
            )
        )

    existing_areas = {name for (name,) in db.execute(select(DeliveryArea.name)).all()}
    for area in profile.delivery_areas:
        if area.name in existing_areas:
            continue
        db.add(
            DeliveryArea(
                name=area.name,
                delivery_fee=area.delivery_fee,
                min_order_amount=area.min_order_amount,
                free_delivery_threshold=area.free_delivery_threshold,
                estimated_days=area.estimated_days,
                is_active=area.is_active,
                sort_order=area.sort_order,
            )
        )

    metadata = _existing_metadata(db)
    if metadata is None:
        metadata = InstanceMetadata(
            instance_slug=profile.client_slug,
            template_version=version,
            profile_schema_version=profile.profile_schema_version,
            profile_hash=profile.profile_hash(),
            enabled_features=profile.enabled_features(),
            initialized_at=now,
            last_bootstrap_at=now,
        )
        db.add(metadata)
    else:
        metadata.template_version = version
        metadata.profile_schema_version = profile.profile_schema_version
        metadata.profile_hash = profile.profile_hash()
        metadata.enabled_features = profile.enabled_features()
        metadata.last_bootstrap_at = now

    db.commit()
    return plan
