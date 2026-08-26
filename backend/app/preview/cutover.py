"""Client-data cutover: look before you purge, and keep what turned out to be real.

A preview batch is a loan of demonstration content. The moment real client data arrives
it has to be handed back — but by then the owner has usually been working inside the
instance, and something genuinely theirs may have arrived *through* the batch: a hero
slide they asked us to load, or an image
they now depend on. A blind `purge --confirm` would take those with it.

Three capabilities, deliberately separate operator actions:

* **plan** — read-only. What the purge would delete, what it would refuse to delete, and
  which pictures are at risk. It calls the purge's own dry run, so it cannot promise
  something the purge would not do.
* **preserve** — an explicit, targeted promotion. The row stays exactly where it is; only
  the batch's *claim* on it is dropped, so no later purge considers it. The media the row
  displays is promoted with it, because a slide without its picture is not preserved.
* **verify** — read-only. Does the database still look like a working, bootstrapped
  store once the demo content is gone?

Nothing here imports client data, and nothing here deletes anything. Purging stays with
`preview_cli purge --confirm`, importing stays with `preview_cli seed`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AdminUser,
    Category,
    Coupon,
    DeliveryArea,
    HeroSlide,
    HomeSection,
    ImportBatch,
    ImportBatchRecord,
    InstanceMetadata,
    Invoice,
    MediaAsset,
    Order,
    OrderItem,
    Product,
    ProductImage,
    StaticPage,
    StoreSettings,
)
from app.preview.importer import PreviewImporter, _load, _records, find_batch
from app.preview.references import (
    LABEL_FIELD_FOR_TYPE,
    MEDIA,
    MODEL_FOR_TYPE,
    label_for,
    media_urls_of,
)
from app.services import audit as audit_service

PRESERVE_ACTION = "preview.preserve"


class CutoverError(RuntimeError):
    """The requested cutover operation cannot be carried out as asked."""


# ── plan ─────────────────────────────────────────────────────────────────────
def _identity(entity_type: str, record: ImportBatchRecord, row: Any) -> dict[str, Any]:
    """Enough to recognise and act on one record: type, key, id, human name."""
    return {
        "entity_type": entity_type,
        "target": f"{entity_type}:{record.natural_key}",
        "natural_key": record.natural_key,
        "entity_id": record.entity_id,
        "label": label_for(entity_type, row),
    }


def build_cutover_plan(importer: PreviewImporter, *, force: bool = False) -> dict[str, Any]:
    """Read-only report of what a purge of this batch would do.

    The verdicts come from `PreviewImporter.purge(apply=False)` — the same computation
    the real purge runs — and are only enriched here with identities, media risk and the
    counts of what would be left behind.
    """
    db = importer.db
    batch_key = importer.dataset.batch_key
    batch = find_batch(db, batch_key)

    report: dict[str, Any] = {
        "batch_key": batch_key,
        "exists": batch is not None,
        "force": force,
        "would_delete": {},
        "would_delete_total": 0,
        "protected_owner_edited": [],
        "blocked": [],
        "already_gone": [],
        "media_to_delete": [],
        "media_at_risk": [],
        "surviving": _surviving_counts(db, batch),
        "bootstrap": _bootstrap_counts(db),
        "commercial": _commercial_counts(db),
    }
    if batch is None:
        return report

    plan = importer.purge(apply=False, force=force)
    verdicts = {action.target: action for action in plan.actions}

    for record in _records(db, batch):
        entity_type = record.entity_type
        target = f"{entity_type}:{record.natural_key}"
        action = verdicts.get(target)
        if action is None:
            continue
        row = _load(db, entity_type, record.entity_id)
        identity = _identity(entity_type, record, row)

        if action.outcome == "gone":
            report["already_gone"].append(identity)
        elif action.outcome == "blocked":
            report["blocked"].append({**identity, "reason": action.detail})
            if entity_type == MEDIA:
                report["media_at_risk"].append({**identity, "reason": action.detail})
        elif action.outcome == "skip":
            report["protected_owner_edited"].append({**identity, "reason": action.detail})
        elif action.outcome == "delete":
            report["would_delete"][entity_type] = report["would_delete"].get(entity_type, 0) + 1
            report["would_delete_total"] += 1
            if entity_type == MEDIA and row is not None:
                report["media_to_delete"].append({**identity, "url": row.url})

    return report


def _surviving_counts(db: Session, batch: ImportBatch | None) -> dict[str, int]:
    """Rows this batch does not own — the owner's and the system's content."""
    owned: dict[str, set[int]] = {}
    if batch is not None:
        for record in _records(db, batch):
            owned.setdefault(record.entity_type, set()).add(record.entity_id)

    result: dict[str, int] = {}
    for entity_type, model in (
        ("category", Category),
        ("product", Product),
        ("delivery_area", DeliveryArea),
        ("hero_slide", HeroSlide),
        ("home_section", HomeSection),
        ("coupon", Coupon),
        ("media_asset", MediaAsset),
    ):
        total = db.execute(select(func.count()).select_from(model)).scalar_one()
        result[entity_type] = total - len(owned.get(entity_type, set()))
    return result


def _bootstrap_counts(db: Session) -> dict[str, int]:
    return {
        "instance_metadata": db.execute(
            select(func.count()).select_from(InstanceMetadata)
        ).scalar_one(),
        "store_settings": db.execute(
            select(func.count()).select_from(StoreSettings)
        ).scalar_one(),
        "static_page": db.execute(select(func.count()).select_from(StaticPage)).scalar_one(),
        "admin_user": db.execute(select(func.count()).select_from(AdminUser)).scalar_one(),
    }


def _commercial_counts(db: Session) -> dict[str, int]:
    return {
        "order": db.execute(select(func.count()).select_from(Order)).scalar_one(),
        "order_item": db.execute(select(func.count()).select_from(OrderItem)).scalar_one(),
        "invoice": db.execute(select(func.count()).select_from(Invoice)).scalar_one(),
    }


# ── preserve ─────────────────────────────────────────────────────────────────
@dataclass
class PreserveResult:
    target: str
    outcome: str  # promote | already-unmanaged | unknown | missing-row
    detail: str = ""
    promoted_media: list[str] = field(default_factory=list)

    def render(self) -> str:
        media = f" (+{len(self.promoted_media)} media)" if self.promoted_media else ""
        suffix = f" — {self.detail}" if self.detail else ""
        return f"[{self.outcome:18}] {self.target}{media}{suffix}"


@dataclass(frozen=True)
class Selector:
    """One record an operator has chosen, named either way the plan prints it.

    A natural key is the readable choice and stays the default. But the key is the
    record's *title* — the owner can rename a slide in Admin, and then the only stable
    handle left is the row id, which the plan prints beside it. Both are just two ways
    of finding the same `ImportBatchRecord`; everything after resolution is identical.
    """

    entity_type: str
    natural_key: str | None = None
    entity_id: int | None = None

    def __post_init__(self) -> None:
        if self.entity_type not in MODEL_FOR_TYPE:
            raise CutoverError(
                f"{self.entity_type!r} is not a preservable entity type. "
                f"Known types: {', '.join(sorted(MODEL_FOR_TYPE))}."
            )
        if (self.natural_key is None) == (self.entity_id is None):
            raise CutoverError(
                "Name a record by its natural key or by its entity id, not both and "
                "not neither."
            )

    def render(self) -> str:
        if self.entity_id is not None:
            return f"{self.entity_type}#{self.entity_id}"
        return f"{self.entity_type}:{self.natural_key}"


def parse_selector(target: str) -> Selector:
    """`entity_type:natural_key`, exactly as the plan prints it."""
    entity_type, separator, natural_key = target.partition(":")
    if not separator or not natural_key:
        raise CutoverError(
            f"{target!r} is not a valid target. Use 'entity_type:natural_key', "
            "exactly as the plan prints it — for example 'hero_slide:عنوان'."
        )
    return Selector(entity_type, natural_key=natural_key)


def _as_selector(target: str | Selector) -> Selector:
    return target if isinstance(target, Selector) else parse_selector(target)


def preserve(
    db: Session,
    batch_key: str,
    targets: list[str | Selector],
    *,
    apply: bool = False,
    include_media: bool = True,
    admin: AdminUser | None = None,
) -> list[PreserveResult]:
    """Promote named batch-owned rows to owner-owned, so no purge ever removes them.

    Promotion is the deletion of the `ImportBatchRecord` — the batch's claim — and
    nothing else. The row, its id, its images and every reference to it are untouched,
    which is what makes this safe to run on live content and idempotent: a second run
    finds no claim and reports `already-unmanaged`.

    Selection is always explicit. Nothing is promoted because of what it is called or
    what it looks like; the operator names each target from the plan, either by natural
    key or by row id. A target may be given as a `Selector` or as the
    `entity_type:natural_key` string the plan prints.
    """
    batch = find_batch(db, batch_key)
    if batch is None:
        raise CutoverError(f"No import batch {batch_key!r} exists in this database.")
    if not targets:
        raise CutoverError("Nothing to preserve: name at least one target from the plan.")

    index = {(r.entity_type, r.natural_key): r for r in _records(db, batch)}
    by_entity = {(r.entity_type, r.entity_id): r for r in index.values()}
    results: list[PreserveResult] = []

    for target in targets:
        selector = _as_selector(target)
        entity_type = selector.entity_type
        label = selector.render()

        # The two selectors differ only here, in which index finds the claim. An id is
        # looked up under its own entity type, so a numeric id belonging to some other
        # table can never promote the wrong row.
        if selector.entity_id is not None:
            record = by_entity.get((entity_type, selector.entity_id))
            still_there = _load(db, entity_type, selector.entity_id) is not None
        else:
            record = index.get((entity_type, selector.natural_key))
            still_there = _row_exists_outside_batch(db, entity_type, selector.natural_key)

        if record is None:
            results.append(
                PreserveResult(
                    label,
                    "already-unmanaged" if still_there else "unknown",
                    "this batch holds no claim on that record",
                )
            )
            continue

        natural_key = record.natural_key
        row = _load(db, entity_type, record.entity_id)
        if row is None:
            results.append(
                PreserveResult(label, "missing-row", "the row is already gone; nothing to keep")
            )
            continue

        promoted_media = (
            _media_records_for(db, by_entity, entity_type, row) if include_media else []
        )
        results.append(
            PreserveResult(
                label,
                "promote",
                f"{label_for(entity_type, row)} — released from batch {batch_key!r}",
                [r.natural_key for r in promoted_media],
            )
        )
        if not apply:
            continue

        for media_record in promoted_media:
            db.delete(media_record)
            index.pop((media_record.entity_type, media_record.natural_key), None)
            by_entity.pop((media_record.entity_type, media_record.entity_id), None)
        db.delete(record)
        index.pop((entity_type, natural_key), None)
        by_entity.pop((entity_type, record.entity_id), None)

        audit_service.record(
            db,
            admin=admin,
            action=PRESERVE_ACTION,
            entity_type=entity_type,
            entity_id=record.entity_id,
            meta={
                "batch_key": batch_key,
                "natural_key": natural_key,
                "label": label_for(entity_type, row),
                "promoted_media": [r.natural_key for r in promoted_media],
            },
        )

    if apply:
        db.flush()
        _drop_batch_if_empty(db, batch)
        db.commit()
    return results


def _row_exists_outside_batch(db: Session, entity_type: str, natural_key: str) -> bool:
    """Distinguish 'already promoted' from 'never existed', so re-runs read honestly."""
    model = MODEL_FOR_TYPE.get(entity_type)
    if model is None:
        return False
    for column in ("slug", "code", "section_key", LABEL_FIELD_FOR_TYPE.get(entity_type, "name")):
        attribute = getattr(model, column, None)
        if attribute is None:
            continue
        found = db.execute(select(func.count()).select_from(model).where(
            attribute == natural_key
        )).scalar_one()
        if found:
            return True
    return False


def _media_records_for(
    db: Session,
    by_entity: dict[tuple[str, int], ImportBatchRecord],
    entity_type: str,
    row: Any,
) -> list[ImportBatchRecord]:
    """The batch's claims on the media this row displays.

    Transitive by a single, stated rule: a preserved row keeps the assets whose URL it
    actually shows. Nothing is promoted on the strength of a filename.
    """
    claims: list[ImportBatchRecord] = []
    for url in media_urls_of(entity_type, row):
        for asset in db.execute(select(MediaAsset).where(MediaAsset.url == url)).scalars():
            claim = by_entity.get((MEDIA, asset.id))
            if claim is not None and claim not in claims:
                claims.append(claim)
    return claims


def _drop_batch_if_empty(db: Session, batch: ImportBatch) -> None:
    remaining = db.execute(
        select(func.count())
        .select_from(ImportBatchRecord)
        .where(ImportBatchRecord.batch_id == batch.id)
    ).scalar_one()
    if remaining == 0:
        db.delete(batch)


# ── verify ───────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""

    def render(self) -> str:
        mark = "ok  " if self.ok else "FAIL"
        suffix = f" — {self.detail}" if self.detail else ""
        return f"[{mark}] {self.name}{suffix}"


def verify_state(db: Session, *, media_base_url: str | None = None) -> list[Check]:
    """Structural sanity of the database after a purge. Read-only.

    This is a "did the cutover leave a coherent store behind?" check, not a release
    certification: bootstrap rows present, no batch record pointing at a deleted row, no
    content pointing at an uploaded file that no longer exists, orders still resolvable.
    """
    if media_base_url is None:
        from app.core.config import settings

        media_base_url = settings.LOCAL_MEDIA_BASE_URL
    base = (media_base_url or "").rstrip("/")

    checks: list[Check] = []
    counts = _bootstrap_counts(db)
    checks.append(
        Check("instance metadata present", counts["instance_metadata"] >= 1,
              f"{counts['instance_metadata']} row(s)")
    )
    checks.append(
        Check("store settings present", counts["store_settings"] >= 1,
              f"{counts['store_settings']} row(s)")
    )
    checks.append(
        Check("static pages present", counts["static_page"] >= 1,
              f"{counts['static_page']} page(s)")
    )
    sections = db.execute(select(func.count()).select_from(HomeSection)).scalar_one()
    checks.append(Check("home sections present", sections >= 1, f"{sections} section(s)"))

    dangling = [
        f"{record.entity_type}:{record.natural_key}"
        for record in db.execute(select(ImportBatchRecord)).scalars()
        if _load(db, record.entity_type, record.entity_id) is None
    ]
    checks.append(
        Check(
            "no import batch record points at a missing row",
            not dangling,
            ", ".join(dangling[:5]) if dangling else "",
        )
    )

    broken = _broken_media_references(db, base)
    checks.append(
        Check(
            "no content points at a missing media asset",
            not broken,
            ", ".join(broken[:5]) if broken else "",
        )
    )

    orphan_lines = db.execute(
        select(func.count())
        .select_from(OrderItem)
        .where(
            OrderItem.product_id.isnot(None),
            OrderItem.product_id.notin_(select(Product.id)),
        )
    ).scalar_one()
    checks.append(
        Check("every order line still resolves to a product", orphan_lines == 0,
              f"{orphan_lines} orphaned line(s)")
    )

    orphan_orders = db.execute(
        select(func.count())
        .select_from(Order)
        .where(
            Order.delivery_area_id.isnot(None),
            Order.delivery_area_id.notin_(select(DeliveryArea.id)),
        )
    ).scalar_one()
    checks.append(
        Check("every order still resolves to its delivery area", orphan_orders == 0,
              f"{orphan_orders} orphaned order(s)")
    )

    return checks


def _broken_media_references(db: Session, base: str) -> list[str]:
    """Content URLs that claim to be uploaded files but have no `MediaAsset` behind them.

    Restricted to URLs under the media base: a hero slide may legitimately point at a
    static asset shipped with the frontend, and that is not a broken upload.
    """
    known = {url for (url,) in db.execute(select(MediaAsset.url)).all()}

    def is_upload(url: str | None) -> bool:
        return bool(url) and (not base or url.startswith(base))

    broken: list[str] = []
    for model, column in (
        (Category, "image_url"),
        (HeroSlide, "image_url"),
        (StoreSettings, "logo_url"),
        (StoreSettings, "favicon_url"),
    ):
        for row in db.execute(select(model)).scalars():
            url = getattr(row, column)
            if is_upload(url) and url not in known:
                broken.append(f"{model.__tablename__}.{column}={url}")

    for image in db.execute(select(ProductImage)).scalars():
        if is_upload(image.url) and image.url not in known:
            broken.append(f"product_images.url={image.url}")

    return sorted(set(broken))
