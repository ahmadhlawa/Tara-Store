"""Preview batch lifecycle: plan, seed, status, purge.

Three rules govern everything here.

1. **The batch owns what the batch created.** A row is only ever touched if an
   `ImportBatchRecord` says this batch made it. A row that merely happens to share a slug
   with the dataset is owner content and is left alone — it is never adopted.
2. **An owner edit wins.** Every managed row carries a fingerprint of the fields the
   importer wrote. If the fingerprint no longer matches, the owner changed the row
   through Admin: seed stops overwriting it and purge stops deleting it, unless the
   operator passes `--force` and accepts that.
3. **Nothing commercial is destroyed.** A preview product or delivery area that a real
   order references is never deleted, force or not — the order and its invoice are the
   permanent record and must keep their references intact.

`plan` and `seed` share one planner, and `purge`'s dry run is the same computation as its
apply, so neither can drift from what it promises.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import ProductType
from app.db.base import utcnow
from app.models import (
    Banner,
    Category,
    Coupon,
    DeliveryArea,
    HeroSlide,
    HomeSection,
    ImportBatch,
    ImportBatchRecord,
    MediaAsset,
    Order,
    OrderItem,
    PackageItem,
    Product,
    ProductImage,
    ProductOption,
    ProductOptionValue,
    ProductSpecification,
)
from app.preview.dataset import PreviewDataset
from app.preview.media_library import resolve_one
from app.preview.references import (  # noqa: F401  (re-exported: the entity vocabulary)
    BANNER,
    CATEGORY,
    COUPON,
    CREATION_ORDER,
    DELIVERY_AREA,
    HERO_SLIDE,
    HOME_SECTION,
    MEDIA,
    MODEL_FOR_TYPE,
    PRODUCT,
    media_reference_holders,
)
from app.services import catalog as catalog_service
from app.services.placeholder_image import hex_to_rgb, vista_preview_png
from app.storage.base import StorageProvider, validate_image_upload

Outcome = Literal["create", "update", "repair", "skip", "delete", "blocked", "gone"]

IMAGE_SHAPES = {"tile": (640, 800), "wide": (1280, 640), "square": (800, 800)}

MAX_PREVIEW_IMAGE_BYTES = 5 * 1024 * 1024


class PreviewError(RuntimeError):
    """The preview batch cannot be operated on safely."""


@dataclass(frozen=True)
class PreviewAction:
    outcome: Outcome
    target: str
    detail: str = ""

    def render(self) -> str:
        suffix = f" — {self.detail}" if self.detail else ""
        return f"[{self.outcome:8}] {self.target}{suffix}"


@dataclass
class PreviewPlan:
    actions: list[PreviewAction] = field(default_factory=list)

    def add(self, outcome: Outcome, target: str, detail: str = "") -> None:
        self.actions.append(PreviewAction(outcome, target, detail))

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for action in self.actions:
            result[action.outcome] = result.get(action.outcome, 0) + 1
        return result

    @property
    def blocked(self) -> list[PreviewAction]:
        return [action for action in self.actions if action.outcome == "blocked"]


def _fingerprint(values: dict[str, Any]) -> str:
    """Stable hash of the fields the importer manages for one row."""

    def normalise(value: Any) -> Any:
        if isinstance(value, Decimal):
            # Numeric(12, 2) round-trips as a 2-place Decimal; quantize so a value read
            # back from MySQL hashes identically to the one written on SQLite.
            return f"{value.quantize(Decimal('0.01')):f}"
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    payload = {key: normalise(value) for key, value in sorted(values.items())}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def seo_title_for(item: Any) -> str:
    """A product's SEO title: the dataset's, or its name."""
    return (getattr(item, "seo_title", None) or item.name)[:200]


def seo_description_for(item: Any) -> str:
    return (getattr(item, "seo_description", None) or item.short_description or item.name)[:150]


# ── the managed field set, per entity type ───────────────────────────────────
def managed_values(entity_type: str, row: Any) -> dict[str, Any]:
    """Exactly the fields this importer writes. Anything else is the owner's."""
    if entity_type == MEDIA:
        return {
            "original_filename": row.original_filename,
            "stored_key": row.stored_key,
            "content_type": row.content_type,
            "size_bytes": row.size_bytes,
            "url": row.url,
        }
    if entity_type == CATEGORY:
        return {
            "name": row.name,
            "description": row.description,
            "image_url": row.image_url,
            # The parent is hashed by *slug*, never by id: a fingerprint has to mean the
            # same thing in every database the dataset is seeded into.
            "parent": row.parent.slug if row.parent is not None else None,
            "is_active": row.is_active,
            "is_featured": row.is_featured,
            "sort_order": row.sort_order,
        }
    if entity_type == PRODUCT:
        return {
            "name": row.name,
            "sku": row.sku,
            "product_type": row.product_type,
            "price": row.price,
            "compare_at_price": row.compare_at_price,
            "cost_price": row.cost_price,
            "track_inventory": row.track_inventory,
            "low_stock_threshold": row.low_stock_threshold,
            "seo_title": row.seo_title,
            "seo_description": row.seo_description,
            # `stock_quantity` is deliberately absent. It moves on its own every time
            # somebody orders something, and a sale is not an owner edit — including it
            # would make a purchased preview product look edited and stop the purge from
            # cleaning it up.
            "short_description": row.short_description,
            "description": row.description,
            "is_active": row.is_active,
            "is_featured": row.is_featured,
            "is_new": row.is_new,
            "is_bestseller": row.is_bestseller,
            "sort_order": row.sort_order,
            "primary_image_url": row.primary_image_url,
            "secondary_image_url": row.secondary_image_url,
        }
    if entity_type == DELIVERY_AREA:
        return {
            "name": row.name,
            "delivery_fee": row.delivery_fee,
            "min_order_amount": row.min_order_amount,
            "free_delivery_threshold": row.free_delivery_threshold,
            "estimated_days": row.estimated_days,
            "is_active": row.is_active,
            "sort_order": row.sort_order,
        }
    if entity_type == HERO_SLIDE:
        return {
            "title": row.title,
            "subtitle": row.subtitle,
            "description": row.description,
            "image_url": row.image_url,
            "button_label": row.button_label,
            "button_url": row.button_url,
            "is_active": row.is_active,
            "sort_order": row.sort_order,
        }
    if entity_type == BANNER:
        return {
            "placement": row.placement,
            "title": row.title,
            "subtitle": row.subtitle,
            "image_url": row.image_url,
            "link_url": row.link_url,
            "is_active": row.is_active,
            "sort_order": row.sort_order,
        }
    if entity_type == HOME_SECTION:
        return {
            "section_type": row.section_type,
            "title": row.title,
            "description": row.description,
            "is_visible": row.is_visible,
            "sort_order": row.sort_order,
        }
    if entity_type == COUPON:
        return {
            "description": row.description,
            "discount_type": row.discount_type,
            "discount_value": row.discount_value,
            "min_order_amount": row.min_order_amount,
            "max_discount_amount": row.max_discount_amount,
            "usage_limit": row.usage_limit,
            "is_active": row.is_active,
        }
    raise PreviewError(f"unknown entity type {entity_type!r}")


def desired_values(
    entity_type: str,
    item: Any,
    *,
    image_url: str | None = None,
    secondary_image_url: str | None = None,
) -> dict[str, Any]:
    """The same field set as `managed_values`, computed from the dataset instead.

    These two functions must agree exactly: a row written from `item` has to hash to
    the value computed here, or the next run would mistake its own work for an owner
    edit. Keeping the dataset as the source of the hash is what makes a re-seed report
    `skip` rather than a meaningless `update`.
    """
    if entity_type == CATEGORY:
        return {
            "name": item.name,
            "description": item.description,
            "image_url": image_url,
            "parent": item.parent,
            "is_active": item.is_active,
            "is_featured": item.is_featured,
            "sort_order": item.sort_order,
        }
    if entity_type == PRODUCT:
        return {
            "name": item.name,
            "sku": item.sku,
            "product_type": item.product_type,
            "price": item.price,
            "compare_at_price": item.compare_at_price,
            "cost_price": item.cost_price,
            "track_inventory": item.track_inventory,
            "low_stock_threshold": item.low_stock_threshold,
            "seo_title": seo_title_for(item),
            "seo_description": seo_description_for(item),
            # Mirrors `managed_values`: stock is not part of the identity of an import.
            "short_description": item.short_description,
            "description": item.description,
            "is_active": item.is_active,
            "is_featured": item.is_featured,
            "is_new": item.is_new,
            "is_bestseller": item.is_bestseller,
            "sort_order": item.sort_order,
            "primary_image_url": image_url,
            "secondary_image_url": secondary_image_url,
        }
    if entity_type == DELIVERY_AREA:
        return {
            "name": item.name,
            "delivery_fee": item.delivery_fee,
            "min_order_amount": item.min_order_amount,
            "free_delivery_threshold": item.free_delivery_threshold,
            "estimated_days": item.estimated_days,
            "is_active": True,
            "sort_order": item.sort_order,
        }
    if entity_type == HERO_SLIDE:
        return {
            "title": item.title,
            "subtitle": item.subtitle,
            "description": item.description,
            "image_url": image_url,
            "button_label": item.button_label,
            "button_url": item.button_url,
            "is_active": True,
            "sort_order": item.sort_order,
        }
    if entity_type == BANNER:
        return {
            "placement": item.placement,
            "title": item.title,
            "subtitle": item.subtitle,
            "image_url": image_url,
            "link_url": item.link_url,
            "is_active": True,
            "sort_order": item.sort_order,
        }
    if entity_type == HOME_SECTION:
        return {
            "section_type": item.section_type,
            "title": item.title,
            "description": item.description,
            "is_visible": item.is_visible,
            "sort_order": item.sort_order,
        }
    if entity_type == COUPON:
        return {
            "description": item.description,
            "discount_type": item.discount_type,
            "discount_value": item.discount_value,
            "min_order_amount": item.min_order_amount,
            "max_discount_amount": item.max_discount_amount,
            "usage_limit": item.usage_limit,
            "is_active": True,
        }
    raise PreviewError(f"no dataset-side field set for entity type {entity_type!r}")


def row_fingerprint(entity_type: str, row: Any) -> str:
    return _fingerprint(managed_values(entity_type, row))


def item_fingerprint(
    entity_type: str,
    item: Any,
    *,
    image_url: str | None = None,
    secondary_image_url: str | None = None,
) -> str:
    return _fingerprint(
        desired_values(
            entity_type, item, image_url=image_url, secondary_image_url=secondary_image_url
        )
    )


# ── batch access ─────────────────────────────────────────────────────────────
def find_batch(db: Session, batch_key: str) -> ImportBatch | None:
    return db.execute(
        select(ImportBatch).where(ImportBatch.batch_key == batch_key)
    ).scalar_one_or_none()


def _records(db: Session, batch: ImportBatch) -> list[ImportBatchRecord]:
    return list(
        db.execute(
            select(ImportBatchRecord).where(ImportBatchRecord.batch_id == batch.id)
        ).scalars()
    )


def _record_index(
    db: Session, batch: ImportBatch | None
) -> dict[tuple[str, str], ImportBatchRecord]:
    """(entity_type, natural_key) -> record, for the rows this batch owns."""
    if batch is None:
        return {}
    return {(r.entity_type, r.natural_key): r for r in _records(db, batch)}


def _load(db: Session, entity_type: str, entity_id: int) -> Any | None:
    return db.get(MODEL_FOR_TYPE[entity_type], entity_id)


class PreviewImporter:
    """Owns one dataset against one database."""

    def __init__(
        self,
        db: Session,
        dataset: PreviewDataset,
        *,
        storage: StorageProvider | None = None,
    ) -> None:
        self.db = db
        self.dataset = dataset
        self._storage = storage

    @property
    def storage(self) -> StorageProvider:
        if self._storage is None:
            from app.storage import get_storage

            self._storage = get_storage()
        return self._storage

    # ── plan / seed ──────────────────────────────────────────────────────────
    def plan(self) -> PreviewPlan:
        """What a seed would do. Writes nothing."""
        return self._seed(apply=False, force=False)

    def seed(self, *, force: bool = False) -> PreviewPlan:
        plan = self._seed(apply=True, force=force)
        self.db.commit()
        return plan

    def _owned_row(
        self, entity_type: str, natural_key: str, index: dict[tuple[str, str], ImportBatchRecord]
    ) -> tuple[Any | None, ImportBatchRecord | None]:
        """The row this batch owns under `natural_key`, if it still exists."""
        record = index.get((entity_type, natural_key))
        if record is None:
            return None, None
        return _load(self.db, entity_type, record.entity_id), record

    def _decide(
        self,
        entity_type: str,
        natural_key: str,
        index: dict[tuple[str, str], ImportBatchRecord],
        desired_fingerprint: str,
        *,
        model: Any,
        lookup_column: Any,
        force: bool,
    ) -> tuple[str, Any | None, ImportBatchRecord | None]:
        """Decide what to do with one dataset item, without writing anything.

        `create` / `update` / `current` / `owner-edited` / `foreign`. Both `plan` and
        `seed` call this, so a plan cannot promise something the seed will not do.
        """
        row, record = self._owned_row(entity_type, natural_key, index)
        if row is not None:
            if row_fingerprint(entity_type, row) != record.content_fingerprint:
                # The row no longer looks like what this batch wrote.
                return ("update" if force else "owner-edited"), row, record
            if desired_fingerprint == record.content_fingerprint:
                return "current", row, record
            return "update", row, record

        foreign = self.db.execute(
            select(model).where(lookup_column == natural_key)
        ).scalar_one_or_none()
        if foreign is not None:
            return "foreign", foreign, record
        return "create", None, record

    def _seed(self, *, apply: bool, force: bool) -> PreviewPlan:
        plan = PreviewPlan()
        batch = find_batch(self.db, self.dataset.batch_key)
        index = _record_index(self.db, batch)

        if batch is None:
            plan.add("create", f"import_batch:{self.dataset.batch_key}", self.dataset.source_label)
            if apply:
                batch = ImportBatch(
                    batch_key=self.dataset.batch_key,
                    source_label=self.dataset.source_label,
                    dataset_hash=self.dataset.dataset_hash(),
                    media_prefix=self.dataset.media_prefix,
                    seed_count=0,
                )
                self.db.add(batch)
                self.db.flush()
        else:
            plan.add(
                "update",
                f"import_batch:{self.dataset.batch_key}",
                f"seed #{batch.seed_count + 1}",
            )

        media_urls = self._seed_media(plan, batch, index, apply=apply, force=force)
        categories = self._seed_categories(plan, batch, index, media_urls, apply=apply, force=force)
        self._seed_products(plan, batch, index, categories, media_urls, apply=apply, force=force)
        self._seed_delivery_areas(plan, batch, index, apply=apply, force=force)
        self._seed_hero_slides(plan, batch, index, media_urls, apply=apply, force=force)
        self._seed_banners(plan, batch, index, media_urls, apply=apply, force=force)
        self._seed_home_sections(plan, batch, index, apply=apply, force=force)
        self._seed_coupons(plan, batch, index, apply=apply, force=force)

        if apply and batch is not None:
            batch.source_label = self.dataset.source_label
            batch.dataset_hash = self.dataset.dataset_hash()
            batch.media_prefix = self.dataset.media_prefix
            batch.seed_count += 1
            batch.last_seeded_at = utcnow()
            self.db.flush()

        return plan

    def _remember(
        self,
        batch: ImportBatch | None,
        record: ImportBatchRecord | None,
        entity_type: str,
        natural_key: str,
        row: Any,
        *,
        fingerprint: str | None = None,
        storage_key: str | None = None,
    ) -> None:
        if batch is None:
            return
        if fingerprint is None:
            fingerprint = row_fingerprint(entity_type, row)
        if record is None:
            record = ImportBatchRecord(
                batch_id=batch.id,
                entity_type=entity_type,
                entity_id=row.id,
                natural_key=natural_key,
            )
            self.db.add(record)
        record.entity_id = row.id
        record.content_fingerprint = fingerprint
        if storage_key is not None:
            record.storage_key = storage_key
        self.db.flush()

    # ── media ────────────────────────────────────────────────────────────────
    def _seed_media(
        self,
        plan: PreviewPlan,
        batch: ImportBatch | None,
        index: dict[tuple[str, str], ImportBatchRecord],
        *,
        apply: bool,
        force: bool,
    ) -> dict[str, str]:
        urls: dict[str, str] = {}
        for item in self.dataset.media:
            target = f"media:{item.key}"

            # A library file belongs to the owner, not to this batch. It is looked up and
            # used; it is never uploaded, never recorded as owned, and therefore never
            # deleted by a purge.
            if item.is_library:
                asset = resolve_one(self.db, item.library_filename)
                urls[item.key] = asset.url
                plan.add("skip", target, f"existing Media Library file {item.library_filename!r}")
                continue

            row, record = self._owned_row(MEDIA, item.key, index)

            # An owned object is never re-uploaded blindly: the bytes are deterministic
            # and the key is already recorded. Re-running the seed must not litter
            # storage. But the row alone is only a claim — the object it names can have
            # gone missing, so the object is checked too, and repaired in place.
            if row is not None:
                urls[item.key] = row.url
                if row_fingerprint(MEDIA, row) != record.content_fingerprint:
                    plan.add("skip", target, "owner-edited; left as is")
                    continue
                expected_filename = f"{item.key}-{item.artwork_version}.png"
                if row.original_filename != expected_filename:
                    plan.add("update", target, f"refresh {item.artwork_version} artwork")
                    if apply:
                        data = self._placeholder_bytes(item)
                        content_type, _ = validate_image_upload(data, MAX_PREVIEW_IMAGE_BYTES)
                        stored = self.storage.restore(row.stored_key, data, content_type=content_type)
                        row.original_filename = expected_filename
                        row.content_type = stored.content_type
                        row.size_bytes = stored.size_bytes
                        self.db.flush()
                        record.content_fingerprint = row_fingerprint(MEDIA, row)
                        self.db.flush()
                    continue
                self._verify_media_object(plan, target, item, record, row, apply=apply)
                continue

            plan.add("create", target, f"{item.shape} placeholder → {self.dataset.media_prefix}")
            if not apply:
                # A plan must be complete even without an upload: downstream rows need a
                # URL to report. An empty string is never written anywhere.
                urls[item.key] = ""
                continue

            data = self._placeholder_bytes(item)
            content_type, extension = validate_image_upload(data, MAX_PREVIEW_IMAGE_BYTES)
            stored = self.storage.save(
                data,
                content_type=content_type,
                extension=extension,
                prefix=self.dataset.media_prefix,
            )
            asset = MediaAsset(
                original_filename=f"{item.key}-{item.artwork_version}.png",
                stored_key=stored.key,
                content_type=stored.content_type,
                size_bytes=stored.size_bytes,
                url=stored.url,
                storage_provider=self.storage.name,
            )
            self.db.add(asset)
            self.db.flush()
            urls[item.key] = asset.url
            self._remember(batch, record, MEDIA, item.key, asset, storage_key=stored.key)
        return urls

    def _placeholder_bytes(self, item: Any) -> bytes:
        """The item's placeholder image. Deterministic, so a repair reproduces it byte for
        byte and the recorded size stays true."""
        width, height = IMAGE_SHAPES[item.shape]
        return vista_preview_png(
            width, height, hex_to_rgb(item.start_color), hex_to_rgb(item.end_color), item.key
        )

    def _verify_media_object(
        self,
        plan: PreviewPlan,
        target: str,
        item: Any,
        record: ImportBatchRecord,
        row: Any,
        *,
        apply: bool,
    ) -> None:
        """Confirm the object behind an owned, unedited media row — and rebuild it if gone.

        The repair writes back to the **recorded key**, so no second `MediaAsset` row is
        created and no URL already published in a category, product, slide or banner
        changes. Three refusals keep it inside its own namespace:

        * a key outside the batch's media prefix is never even probed;
        * a row uploaded to a different provider than the one now configured is left
          alone, because "absent here" says nothing about the bytes over there;
        * an owner-edited row never reaches this method at all.
        """
        key = record.storage_key or row.stored_key
        prefix = self.dataset.media_prefix
        if not key or (prefix and prefix not in key):
            plan.add("skip", target, f"outside the batch prefix {prefix!r}; not inspected")
            return
        if row.storage_provider != self.storage.name:
            plan.add(
                "skip",
                target,
                f"uploaded to {row.storage_provider!r}, current provider is "
                f"{self.storage.name!r}; not inspected",
            )
            return
        if self.storage.exists(key):
            plan.add("skip", target, "already uploaded")
            return

        plan.add("repair", target, f"object {key} is missing; re-uploaded to the same key")
        if not apply:
            return
        data = self._placeholder_bytes(item)
        content_type, _ = validate_image_upload(data, MAX_PREVIEW_IMAGE_BYTES)
        stored = self.storage.restore(key, data, content_type=content_type)
        # The row is not replaced — only the facts about the bytes are refreshed, and the
        # fingerprint follows so the repair is not mistaken for an owner edit next time.
        row.size_bytes = stored.size_bytes
        row.content_type = stored.content_type
        self.db.flush()
        record.content_fingerprint = row_fingerprint(MEDIA, row)
        self.db.flush()

    # ── categories ───────────────────────────────────────────────────────────
    def _seed_categories(
        self,
        plan: PreviewPlan,
        batch: ImportBatch | None,
        index: dict[tuple[str, str], ImportBatchRecord],
        media_urls: dict[str, str],
        *,
        apply: bool,
        force: bool,
    ) -> dict[str, Category]:
        result: dict[str, Category] = {}
        written: list[Any] = []
        for item in self.dataset.categories:
            target = f"category:{item.slug}"
            image_url = media_urls.get(item.image) if item.image else None
            fingerprint = item_fingerprint(CATEGORY, item, image_url=image_url)
            verdict, row, record = self._decide(
                CATEGORY,
                item.slug,
                index,
                fingerprint,
                model=Category,
                lookup_column=Category.slug,
                force=force,
            )

            if verdict == "foreign":
                plan.add("skip", target, "exists and is not owned by this batch")
                result[item.slug] = row
                continue
            if verdict == "owner-edited":
                plan.add("skip", target, "owner-edited; not overwritten")
                result[item.slug] = row
                continue
            if verdict == "current":
                plan.add("skip", target, "already matches the dataset")
                result[item.slug] = row
                continue

            plan.add(verdict, target, item.name)
            if not apply:
                if row is not None:
                    result[item.slug] = row
                continue
            if row is None:
                row = Category(slug=item.slug)
                self.db.add(row)

            row.name = item.name
            row.description = item.description
            row.image_url = image_url
            row.is_active = item.is_active
            row.is_featured = item.is_featured
            row.sort_order = item.sort_order
            self.db.flush()
            result[item.slug] = row
            written.append(item)
            self._remember(batch, record, CATEGORY, item.slug, row, fingerprint=fingerprint)

        if apply:
            # A second pass, because a child may appear above its parent in the file.
            # Only rows this run actually wrote are re-pointed, so an owner-edited or
            # foreign category keeps whatever parent the owner gave it.
            for item in written:
                row = result[item.slug]
                parent = result.get(item.parent) if item.parent else None
                row.parent_id = parent.id if parent is not None else None
            self.db.flush()
        return result

    # ── products ─────────────────────────────────────────────────────────────
    def _seed_products(
        self,
        plan: PreviewPlan,
        batch: ImportBatch | None,
        index: dict[tuple[str, str], ImportBatchRecord],
        categories: dict[str, Category],
        media_urls: dict[str, str],
        *,
        apply: bool,
        force: bool,
    ) -> None:
        written: dict[str, Product] = {}

        for item in self.dataset.products:
            target = f"product:{item.slug}"
            # The gallery is what the product actually shows, in order. The cover and the
            # hover image are read back off it exactly the way `Product` computes them,
            # so the fingerprint matches what the row will report.
            gallery = [media_urls[key] for key in item.gallery if key in media_urls]
            image_url = gallery[0] if gallery else None
            secondary_url = next((url for url in gallery if url != image_url), None)
            fingerprint = item_fingerprint(
                PRODUCT, item, image_url=image_url, secondary_image_url=secondary_url
            )
            verdict, row, record = self._decide(
                PRODUCT,
                item.slug,
                index,
                fingerprint,
                model=Product,
                lookup_column=Product.slug,
                force=force,
            )

            if verdict == "foreign":
                plan.add("skip", target, "exists and is not owned by this batch")
                continue
            if verdict == "owner-edited":
                plan.add("skip", target, "owner-edited; not overwritten")
                continue
            if verdict == "current":
                plan.add("skip", target, "already matches the dataset")
                continue

            plan.add(verdict, target, f"{item.name} — {item.price}")
            if not apply:
                continue
            if row is None:
                row = Product(slug=item.slug)
                self.db.add(row)

            category = categories.get(item.category)
            row.name = item.name
            row.category_id = category.id if category is not None else None
            row.sku = item.sku
            row.product_type = item.product_type
            row.short_description = item.short_description
            row.description = item.description
            row.price = item.price
            row.compare_at_price = item.compare_at_price
            row.cost_price = item.cost_price
            row.stock_quantity = item.stock_quantity
            row.track_inventory = item.track_inventory
            row.low_stock_threshold = item.low_stock_threshold
            row.is_active = item.is_active
            row.is_featured = item.is_featured
            row.is_new = item.is_new
            row.is_bestseller = item.is_bestseller
            row.sort_order = item.sort_order
            row.seo_title = seo_title_for(item)
            row.seo_description = seo_description_for(item)
            catalog_service.refresh_search_text(row)
            self.db.flush()

            self._sync_product_images(row, gallery, item)
            self._sync_specifications(row, item)
            self._sync_options(row, item)
            self.db.flush()
            written[item.slug] = row
            self._remember(batch, record, PRODUCT, item.slug, row, fingerprint=fingerprint)

        if apply:
            # Re-read the index: products created moments ago now have batch records.
            self._sync_packages(written, _record_index(self.db, batch))

    def _sync_product_images(self, product: Product, wanted: list[str], item: Any) -> None:
        """Make the product's gallery exactly the images the dataset names, in order.

        Position is meaning: `sort_order` 0 is the cover, and there is no primary flag to
        contradict it. Rows are rewritten in place rather than deleted and recreated, so
        re-seeding does not churn image rows. Every row here belongs to the preview batch:
        the product itself is batch-owned, so a purge still removes exactly this and
        nothing else.
        """
        existing = list(product.images)
        if not wanted:
            for image in existing:
                self.db.delete(image)
            return

        for order, image_url in enumerate(wanted):
            if order < len(existing):
                row = existing[order]
                row.url = image_url
            else:
                row = ProductImage(product_id=product.id, url=image_url)
                self.db.add(row)
            row.alt_text = item.name
            row.sort_order = order
            row.is_primary = False

        # Anything the dataset no longer names goes, so dropping an image from the
        # YAML actually removes it.
        for image in existing[len(wanted) :]:
            self.db.delete(image)

    def _sync_specifications(self, product: Product, item: Any) -> None:
        for spec in list(product.specifications):
            self.db.delete(spec)
        self.db.flush()
        for order, spec in enumerate(item.specifications):
            self.db.add(
                ProductSpecification(
                    product_id=product.id, name=spec.name, value=spec.value, sort_order=order
                )
            )

    def _sync_options(self, product: Product, item: Any) -> None:
        """Rebuild the product's choice axes.

        Options only — no variants. A variant carries its own SKU, price override and
        stock, none of which a flat option column can express, so the dataset stops at
        the axes and leaves priced combinations to Admin.
        """
        for option in list(product.options):
            self.db.delete(option)
        self.db.flush()
        for order, option in enumerate(getattr(item, "options", [])):
            row = ProductOption(product_id=product.id, name=option.name, sort_order=order)
            self.db.add(row)
            self.db.flush()
            for value_order, value in enumerate(option.values):
                self.db.add(
                    ProductOptionValue(option_id=row.id, value=value, sort_order=value_order)
                )

    def _sync_packages(self, written: dict[str, Product], index: dict) -> None:
        """Rebuild the contents of any package this run touched.

        Members are resolved from the batch's own records rather than from `written`:
        on a re-seed the members are usually already current and so were not rewritten,
        but the package still has to be able to point at them.
        """

        def member(slug: str) -> Product | None:
            row, _ = self._owned_row(PRODUCT, slug, index)
            return row or written.get(slug)

        for item in self.dataset.products:
            if item.product_type != ProductType.PACKAGE.value:
                continue
            package = written.get(item.slug)
            if package is None:
                continue
            for existing in list(package.package_items):
                self.db.delete(existing)
            self.db.flush()
            for order, entry in enumerate(item.package_items):
                included = member(entry.product)
                if included is None:
                    continue
                self.db.add(
                    PackageItem(
                        package_product_id=package.id,
                        included_product_id=included.id,
                        quantity=entry.quantity,
                        display_note=entry.display_note,
                        sort_order=order,
                    )
                )
            self.db.flush()

    # ── the remaining simple entities ────────────────────────────────────────
    def _seed_simple(
        self,
        plan: PreviewPlan,
        batch: ImportBatch | None,
        index: dict[tuple[str, str], ImportBatchRecord],
        *,
        entity_type: str,
        model: Any,
        lookup_column: Any,
        items: list[Any],
        natural_key: Any,
        label: Any,
        create: Any,
        write: Any,
        image_for: Any = None,
        apply: bool,
        force: bool,
    ) -> None:
        for item in items:
            key = natural_key(item)
            target = f"{entity_type}:{key}"
            image_url = image_for(item) if image_for is not None else None
            fingerprint = item_fingerprint(entity_type, item, image_url=image_url)
            verdict, row, record = self._decide(
                entity_type,
                key,
                index,
                fingerprint,
                model=model,
                lookup_column=lookup_column,
                force=force,
            )

            if verdict == "foreign":
                plan.add("skip", target, "exists and is not owned by this batch")
                continue
            if verdict == "owner-edited":
                plan.add("skip", target, "owner-edited; not overwritten")
                continue
            if verdict == "current":
                plan.add("skip", target, "already matches the dataset")
                continue

            plan.add(verdict, target, label(item))
            if not apply:
                continue
            if row is None:
                row = create(item)
                self.db.add(row)

            write(row, item)
            self.db.flush()
            self._remember(batch, record, entity_type, key, row, fingerprint=fingerprint)

    def _seed_delivery_areas(self, plan, batch, index, *, apply: bool, force: bool) -> None:
        def write(row: DeliveryArea, item: Any) -> None:
            row.name = item.name
            row.delivery_fee = item.delivery_fee
            row.min_order_amount = item.min_order_amount
            row.free_delivery_threshold = item.free_delivery_threshold
            row.estimated_days = item.estimated_days
            row.is_active = True
            row.sort_order = item.sort_order

        # DeliveryArea has no natural key column of its own, so the batch key is matched
        # on the visible name — which is exactly what an operator would look for.
        self._seed_simple(
            plan,
            batch,
            index,
            entity_type=DELIVERY_AREA,
            model=DeliveryArea,
            lookup_column=DeliveryArea.name,
            items=self.dataset.delivery_areas,
            natural_key=lambda item: item.name,
            label=lambda item: f"fee {item.delivery_fee}",
            create=lambda item: DeliveryArea(name=item.name, delivery_fee=item.delivery_fee),
            write=write,
            apply=apply,
            force=force,
        )

    def _seed_hero_slides(self, plan, batch, index, media_urls, *, apply: bool, force: bool) -> None:
        def write(row: HeroSlide, item: Any) -> None:
            row.title = item.title
            row.subtitle = item.subtitle
            row.description = item.description
            row.image_url = item.image_url or (media_urls.get(item.image) if item.image else None)
            row.button_label = item.button_label
            row.button_url = item.button_url
            row.is_active = True
            row.sort_order = item.sort_order

        self._seed_simple(
            plan,
            batch,
            index,
            entity_type=HERO_SLIDE,
            model=HeroSlide,
            lookup_column=HeroSlide.title,
            items=self.dataset.hero_slides,
            natural_key=lambda item: item.title,
            label=lambda item: item.title,
            create=lambda item: HeroSlide(title=item.title),
            write=write,
            image_for=lambda item: item.image_url or (media_urls.get(item.image) if item.image else None),
            apply=apply,
            force=force,
        )

    def _seed_banners(self, plan, batch, index, media_urls, *, apply: bool, force: bool) -> None:
        def write(row: Banner, item: Any) -> None:
            row.placement = item.placement
            row.title = item.title
            row.subtitle = item.subtitle
            row.image_url = media_urls.get(item.image) if item.image else None
            row.link_url = item.link_url
            row.is_active = True
            row.sort_order = item.sort_order

        self._seed_simple(
            plan,
            batch,
            index,
            entity_type=BANNER,
            model=Banner,
            lookup_column=Banner.title,
            items=self.dataset.banners,
            natural_key=lambda item: item.title,
            label=lambda item: f"{item.placement}",
            create=lambda item: Banner(title=item.title, placement=item.placement),
            write=write,
            image_for=lambda item: media_urls.get(item.image) if item.image else None,
            apply=apply,
            force=force,
        )

    def _seed_home_sections(self, plan, batch, index, *, apply: bool, force: bool) -> None:
        def write(row: HomeSection, item: Any) -> None:
            row.section_type = item.section_type
            row.title = item.title
            row.description = item.description
            row.is_visible = item.is_visible
            row.sort_order = item.sort_order

        self._seed_simple(
            plan,
            batch,
            index,
            entity_type=HOME_SECTION,
            model=HomeSection,
            lookup_column=HomeSection.section_key,
            items=self.dataset.home_sections,
            natural_key=lambda item: item.key,
            label=lambda item: item.section_type,
            create=lambda item: HomeSection(
                section_key=item.key, section_type=item.section_type, config={}
            ),
            write=write,
            apply=apply,
            force=force,
        )

    def _seed_coupons(self, plan, batch, index, *, apply: bool, force: bool) -> None:
        def write(row: Coupon, item: Any) -> None:
            row.description = item.description
            row.discount_type = item.discount_type
            row.discount_value = item.discount_value
            row.min_order_amount = item.min_order_amount
            row.max_discount_amount = item.max_discount_amount
            row.usage_limit = item.usage_limit
            row.is_active = True

        self._seed_simple(
            plan,
            batch,
            index,
            entity_type=COUPON,
            model=Coupon,
            lookup_column=Coupon.code,
            items=self.dataset.coupons,
            natural_key=lambda item: item.code,
            label=lambda item: f"{item.discount_value} {item.discount_type}",
            create=lambda item: Coupon(code=item.code, discount_value=item.discount_value),
            write=write,
            apply=apply,
            force=force,
        )

    # ── purge ────────────────────────────────────────────────────────────────
    def purge(self, *, apply: bool = False, force: bool = False) -> PreviewPlan:
        plan = PreviewPlan()
        batch = find_batch(self.db, self.dataset.batch_key)
        if batch is None:
            plan.add("skip", f"import_batch:{self.dataset.batch_key}", "no such batch")
            return plan

        records = _records(self.db, batch)
        by_type: dict[str, list[ImportBatchRecord]] = {}
        for record in records:
            by_type.setdefault(record.entity_type, []).append(record)

        deletable: list[tuple[ImportBatchRecord, Any]] = []
        # What this purge has already decided to remove, by entity type. Media is judged
        # last (it is first in `CREATION_ORDER`), so by the time an asset is considered,
        # every row that could still be displaying it is known.
        deleting: dict[str, set[int]] = {}

        # Reverse creation order: dependents die before the rows they point at.
        for entity_type in reversed(CREATION_ORDER):
            for record in by_type.get(entity_type, []):
                target = f"{entity_type}:{record.natural_key}"
                row = _load(self.db, entity_type, record.entity_id)

                if row is None:
                    plan.add("gone", target, "row already deleted; batch record will be dropped")
                    if apply:
                        self.db.delete(record)
                    continue

                # Checked first, and before `--force` gets a say. These refusals protect
                # orders and invoices, which no flag on a preview tool may override.
                blocked = self._deletion_block(batch, entity_type, row, deleting)
                if blocked is not None:
                    plan.add("blocked", target, blocked)
                    continue

                if row_fingerprint(entity_type, row) != record.content_fingerprint:
                    if not force:
                        plan.add("skip", target, "owner-edited since import; kept")
                        continue
                    plan.add("delete", target, "owner-edited, removed anyway (--force)")
                else:
                    plan.add("delete", target, record.natural_key)

                deletable.append((record, row))
                deleting.setdefault(entity_type, set()).add(row.id)

        if not apply:
            return plan

        for record, row in deletable:
            if record.entity_type == MEDIA:
                self._delete_media_object(plan, batch, record, row)
            self.db.delete(row)
            self.db.delete(record)
        self.db.flush()

        remaining = self.db.execute(
            select(func.count()).select_from(ImportBatchRecord).where(
                ImportBatchRecord.batch_id == batch.id
            )
        ).scalar_one()
        if remaining == 0:
            plan.add("delete", f"import_batch:{batch.batch_key}", "batch is now empty")
            self.db.delete(batch)
        else:
            plan.add(
                "skip",
                f"import_batch:{batch.batch_key}",
                f"{remaining} record(s) still owned; batch kept",
            )
        self.db.commit()
        return plan

    def _owned_ids(self, batch: ImportBatch, entity_type: str) -> list[int]:
        return [
            record.entity_id
            for record in self.db.execute(
                select(ImportBatchRecord).where(
                    ImportBatchRecord.batch_id == batch.id,
                    ImportBatchRecord.entity_type == entity_type,
                )
            ).scalars()
        ] or [0]

    def _deletion_block(
        self,
        batch: ImportBatch,
        entity_type: str,
        row: Any,
        deleting: dict[str, set[int]] | None = None,
    ) -> str | None:
        """A reason this row must never be deleted, or None.

        These are not overridable by `--force`: an order and its invoice are the
        permanent commercial record, and a preview import does not get to damage them —
        and neither does a picture that surviving content is still showing, because
        deleting it would replace a working page with a broken image.
        """
        if entity_type == MEDIA:
            holders = media_reference_holders(self.db, row.url, deleting)
            if holders:
                shown = ", ".join(holders[:3])
                more = f" (+{len(holders) - 3} more)" if len(holders) > 3 else ""
                return f"still displayed by surviving content: {shown}{more}"
        if entity_type == PRODUCT:
            used = self.db.execute(
                select(func.count()).select_from(OrderItem).where(OrderItem.product_id == row.id)
            ).scalar_one()
            if used:
                return f"referenced by {used} order line(s); an order's history is never altered"
            members = self.db.execute(
                select(func.count())
                .select_from(PackageItem)
                .where(PackageItem.included_product_id == row.id)
            ).scalar_one()
            if members:
                foreign = self.db.execute(
                    select(func.count())
                    .select_from(PackageItem)
                    .where(
                        PackageItem.included_product_id == row.id,
                        PackageItem.package_product_id.notin_(self._owned_ids(batch, PRODUCT)),
                    )
                ).scalar_one()
                if foreign:
                    return f"included in {foreign} package(s) this batch does not own"
        if entity_type == DELIVERY_AREA:
            used = self.db.execute(
                select(func.count()).select_from(Order).where(Order.delivery_area_id == row.id)
            ).scalar_one()
            if used:
                return f"used by {used} order(s); the delivery snapshot must stay resolvable"
        if entity_type == CATEGORY:
            foreign = self.db.execute(
                select(func.count())
                .select_from(Product)
                .where(
                    Product.category_id == row.id,
                    Product.id.notin_(self._owned_ids(batch, PRODUCT)),
                )
            ).scalar_one()
            if foreign:
                return f"{foreign} product(s) outside this batch are still in this category"
        return None

    def _delete_media_object(
        self, plan: PreviewPlan, batch: ImportBatch, record: ImportBatchRecord, row: Any
    ) -> None:
        """Delete the stored object — but only inside the prefix this batch owns."""
        key = record.storage_key or row.stored_key
        prefix = batch.media_prefix or self.dataset.media_prefix
        if not key or prefix not in key:
            plan.add(
                "skip",
                f"object:{key or '(none)'}",
                f"outside the batch prefix {prefix!r}; the file was left in place",
            )
            return
        if row.storage_provider != self.storage.name:
            plan.add(
                "skip",
                f"object:{key}",
                f"uploaded to {row.storage_provider!r}, current provider is "
                f"{self.storage.name!r}; the file was left in place",
            )
            return
        self.storage.delete(key)
        plan.add("delete", f"object:{key}", "removed from storage")

    # ── status ───────────────────────────────────────────────────────────────
    def status(self) -> dict[str, Any]:
        batch = find_batch(self.db, self.dataset.batch_key)
        if batch is None:
            return {
                "batch_key": self.dataset.batch_key,
                "exists": False,
                "dataset_hash": self.dataset.dataset_hash(),
            }

        counts: dict[str, int] = {}
        missing = 0
        owner_edited: list[str] = []
        providers: set[str] = set()
        for record in _records(self.db, batch):
            counts[record.entity_type] = counts.get(record.entity_type, 0) + 1
            row = _load(self.db, record.entity_type, record.entity_id)
            if row is None:
                missing += 1
                continue
            if row_fingerprint(record.entity_type, row) != record.content_fingerprint:
                owner_edited.append(f"{record.entity_type}:{record.natural_key}")
            if record.entity_type == MEDIA:
                providers.add(row.storage_provider)

        return {
            "batch_key": batch.batch_key,
            "exists": True,
            "batch_id": batch.id,
            "source_label": batch.source_label,
            "media_prefix": batch.media_prefix,
            "seed_count": batch.seed_count,
            "last_seeded_at": batch.last_seeded_at.isoformat(),
            "dataset_hash": batch.dataset_hash,
            "dataset_hash_matches_file": batch.dataset_hash == self.dataset.dataset_hash(),
            "records": counts,
            "record_total": sum(counts.values()),
            "missing_rows": missing,
            "owner_edited": sorted(owner_edited),
            # Read from the media rows themselves, so status never has to build a
            # storage provider (and never fails because R2 is half-configured).
            "storage_providers": sorted(providers),
        }
