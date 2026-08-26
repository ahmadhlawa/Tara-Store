"""The cutover: plan, preserve, purge, verify.

These tests are the safety net for the one irreversible moment in this project's life —
the day the demonstration catalog is deleted to make room for the client's real data.
Each one asserts that something the client cares about survives that moment.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Category,
    Coupon,
    DeliveryArea,
    HeroSlide,
    HomeSection,
    ImportBatchRecord,
    InstanceMetadata,
    MediaAsset,
    Product,
    StaticPage,
    StoreSettings,
)
from app.preview.cutover import (
    CutoverError,
    Selector,
    build_cutover_plan,
    preserve,
    verify_state,
)
from app.preview.dataset import parse_dataset
from app.preview.importer import PreviewImporter
from app.storage.local import LocalStorageProvider
from scripts.client_cutover_cli import _preserve_selectors, build_parser

def test_cutover_plan_requires_an_explicit_dataset() -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["plan"])
    assert exc.value.code == 2


DOCUMENT = {
    "preview_schema_version": 1,
    "batch_key": "cutover-preview",
    "source_label": "cutover test dataset",
    "media_prefix": "test-store/preview/",
    "media": [
        {"key": "tile", "alt_text": "tile", "start_color": "#112233", "end_color": "#445566"},
        {
            "key": "hero-art",
            "alt_text": "hero",
            "shape": "wide",
            "start_color": "#221133", "end_color": "#665544",
        },
    ],
    "categories": [
        {"slug": "cat", "name": "قسم المعاينة", "image": "tile", "origin": "inferred"}
    ],
    "products": [
        {
            "slug": "prod-a",
            "name": "منتج ألف",
            "category": "cat",
            "price": "10.50",
            "stock_quantity": 5,
            "image": "tile",
            "origin": "inferred",
        },
    ],
    "hero_slides": [
        {"key": "hero", "title": "شريحة العميل", "image": "hero-art", "origin": "confirmed"},
        {"key": "demo", "title": "شريحة تجريبية", "image": "tile", "origin": "inferred"},
    ],
    "coupons": [{"code": "CUTOVER10", "discount_value": "10.00", "origin": "placeholder"}],
}

HERO_TARGET = "hero_slide:شريحة العميل"


@pytest.fixture()
def storage(tmp_path: Path) -> LocalStorageProvider:
    return LocalStorageProvider(tmp_path / "media", "/media")


@pytest.fixture()
def importer(db: Session, storage: LocalStorageProvider) -> PreviewImporter:
    return PreviewImporter(db, parse_dataset(DOCUMENT), storage=storage)


@pytest.fixture()
def bootstrapped(db: Session) -> None:
    """The skeleton an instance bootstrap leaves behind, plus one owner-made page."""
    db.add(
        InstanceMetadata(
            instance_slug="test-store",
            template_version="0.0.0",
            profile_schema_version=1,
            profile_hash="x" * 8,
            enabled_features=[],
        )
    )
    db.add(StoreSettings(store_name="متجر الاختبار"))
    db.add(StaticPage(slug="about", title="من نحن", content="..."))
    db.add(HomeSection(section_key="featured", section_type="featured_products", config={}))
    db.commit()


def targets(entries: list[dict]) -> set[str]:
    return {entry["target"] for entry in entries}


# ── plan ─────────────────────────────────────────────────────────────────────
def test_plan_lists_the_preview_owned_records_a_purge_would_delete(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()

    report = build_cutover_plan(importer)

    assert report["exists"] is True
    assert report["would_delete"]["product"] == 1
    assert report["would_delete"]["hero_slide"] == 2
    assert report["would_delete"]["media_asset"] == 2
    assert report["would_delete_total"] == sum(report["would_delete"].values())


def test_plan_shows_enough_identity_to_act_on_a_record(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()

    report = build_cutover_plan(importer)
    hero = next(e for e in report["media_to_delete"] if e["entity_type"] == "media_asset")

    assert hero["entity_id"] > 0
    assert hero["label"]  # the filename, so an operator recognises the picture
    assert hero["url"].startswith("/media/")


def test_plan_separates_owner_edited_records_the_purge_protects(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()
    slide = db.query(HeroSlide).filter_by(title="شريحة العميل").one()
    slide.subtitle = "عدّله المالك"
    db.commit()

    report = build_cutover_plan(importer)

    assert HERO_TARGET in targets(report["protected_owner_edited"])
    assert HERO_TARGET not in targets(report["media_to_delete"])
    assert report["would_delete"].get("hero_slide") == 1


def test_plan_counts_owner_and_system_content_that_stays(
    importer: PreviewImporter, db: Session, bootstrapped: None
) -> None:
    db.add(Category(slug="owner-cat", name="قسم المالك"))
    db.commit()
    importer.seed()

    report = build_cutover_plan(importer)

    assert report["surviving"]["category"] == 1
    assert report["bootstrap"]["store_settings"] == 1
    assert report["bootstrap"]["static_page"] == 1
    assert report["commercial"]["order"] == 0


def test_plan_writes_nothing(importer: PreviewImporter, db: Session) -> None:
    importer.seed()
    before = (
        db.query(ImportBatchRecord).count(),
        db.query(HeroSlide).count(),
        db.query(MediaAsset).count(),
    )

    build_cutover_plan(importer)
    db.rollback()

    assert (
        db.query(ImportBatchRecord).count(),
        db.query(HeroSlide).count(),
        db.query(MediaAsset).count(),
    ) == before


def test_plan_on_a_database_that_was_never_seeded(importer: PreviewImporter) -> None:
    report = build_cutover_plan(importer)

    assert report["exists"] is False
    assert report["would_delete_total"] == 0


# ── preserve ─────────────────────────────────────────────────────────────────
def test_preserve_releases_the_named_record_from_the_batch(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()
    slide = db.query(HeroSlide).filter_by(title="شريحة العميل").one()

    results = preserve(db, "cutover-preview", [HERO_TARGET], apply=True)

    assert [r.outcome for r in results] == ["promote"]
    assert db.query(HeroSlide).filter_by(id=slide.id).one().title == "شريحة العميل"
    assert (
        db.query(ImportBatchRecord)
        .filter_by(entity_type="hero_slide", natural_key="شريحة العميل")
        .count()
        == 0
    )


def test_preserve_is_a_dry_run_without_confirm(importer: PreviewImporter, db: Session) -> None:
    importer.seed()

    results = preserve(db, "cutover-preview", [HERO_TARGET], apply=False)
    db.rollback()

    assert [r.outcome for r in results] == ["promote"]
    assert (
        db.query(ImportBatchRecord)
        .filter_by(entity_type="hero_slide", natural_key="شريحة العميل")
        .count()
        == 1
    )


def test_preserve_is_explicit_and_never_guesses(importer: PreviewImporter, db: Session) -> None:
    importer.seed()

    preserve(db, "cutover-preview", [HERO_TARGET], apply=True)

    # The other slide was not named, so it is still owned and still doomed.
    assert (
        db.query(ImportBatchRecord)
        .filter_by(entity_type="hero_slide", natural_key="شريحة تجريبية")
        .count()
        == 1
    )


def test_preserve_carries_the_media_the_record_displays(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()

    results = preserve(db, "cutover-preview", [HERO_TARGET], apply=True)

    assert results[0].promoted_media == ["hero-art"]
    assert (
        db.query(ImportBatchRecord)
        .filter_by(entity_type="media_asset", natural_key="hero-art")
        .count()
        == 0
    )
    # The asset row itself is untouched — only the claim on it was dropped.
    assert db.query(MediaAsset).filter_by(original_filename="hero-art-v1.png").count() == 1


def test_preserve_can_be_asked_to_leave_the_media_behind(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()

    results = preserve(db, "cutover-preview", [HERO_TARGET], apply=True, include_media=False)

    assert results[0].promoted_media == []
    assert (
        db.query(ImportBatchRecord)
        .filter_by(entity_type="media_asset", natural_key="hero-art")
        .count()
        == 1
    )


def test_preserve_is_idempotent(importer: PreviewImporter, db: Session) -> None:
    importer.seed()
    preserve(db, "cutover-preview", [HERO_TARGET], apply=True)

    results = preserve(db, "cutover-preview", [HERO_TARGET], apply=True)

    assert [r.outcome for r in results] == ["already-unmanaged"]
    assert db.query(HeroSlide).filter_by(title="شريحة العميل").count() == 1


# ── preserve by row id, for a record the owner has renamed ───────────────────
def test_preserve_by_entity_id_releases_the_record(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()
    slide = db.query(HeroSlide).filter_by(title="شريحة العميل").one()
    # The case this selector exists for: the batch's claim still says "شريحة العميل",
    # but the owner has renamed the slide, so the natural key no longer finds it in Admin.
    slide.title = "اسم جديد اختاره المالك"
    db.commit()

    results = preserve(
        db, "cutover-preview", [Selector("hero_slide", entity_id=slide.id)], apply=True
    )

    assert [r.outcome for r in results] == ["promote"]
    assert results[0].target == f"hero_slide#{slide.id}"
    assert (
        db.query(ImportBatchRecord)
        .filter_by(entity_type="hero_slide", natural_key="شريحة العميل")
        .count()
        == 0
    )
    # Untouched: same row, same id, same title, same picture.
    kept = db.query(HeroSlide).filter_by(id=slide.id).one()
    assert kept.title == "اسم جديد اختاره المالك"
    assert kept.image_url is not None


def test_a_record_preserved_by_id_survives_the_purge(
    importer: PreviewImporter, db: Session, storage: LocalStorageProvider
) -> None:
    importer.seed()
    slide = db.query(HeroSlide).filter_by(title="شريحة العميل").one()
    asset = db.query(MediaAsset).filter_by(original_filename="hero-art-v1.png").one()
    preserve(db, "cutover-preview", [Selector("hero_slide", entity_id=slide.id)], apply=True)

    importer.purge(apply=True)

    assert db.query(HeroSlide).filter_by(id=slide.id).count() == 1
    assert db.query(MediaAsset).filter_by(id=asset.id).count() == 1
    assert db.query(HeroSlide).filter_by(id=slide.id).one().image_url == asset.url
    assert storage.exists(asset.stored_key)
    assert db.query(HeroSlide).filter_by(title="شريحة تجريبية").count() == 0


def test_preserve_by_entity_id_carries_the_same_media(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()
    slide = db.query(HeroSlide).filter_by(title="شريحة العميل").one()

    results = preserve(
        db, "cutover-preview", [Selector("hero_slide", entity_id=slide.id)], apply=True
    )

    assert results[0].promoted_media == ["hero-art"]
    assert (
        db.query(ImportBatchRecord)
        .filter_by(entity_type="media_asset", natural_key="hero-art")
        .count()
        == 0
    )


def test_preserve_by_an_id_that_does_not_exist(importer: PreviewImporter, db: Session) -> None:
    importer.seed()

    results = preserve(db, "cutover-preview", [Selector("hero_slide", entity_id=9999)], apply=True)

    assert [r.outcome for r in results] == ["unknown"]


def test_preserve_by_entity_id_is_idempotent(importer: PreviewImporter, db: Session) -> None:
    importer.seed()
    slide = db.query(HeroSlide).filter_by(title="شريحة العميل").one()
    target = Selector("hero_slide", entity_id=slide.id)
    preserve(db, "cutover-preview", [target], apply=True)

    results = preserve(db, "cutover-preview", [target], apply=True)

    assert [r.outcome for r in results] == ["already-unmanaged"]
    assert db.query(HeroSlide).filter_by(id=slide.id).count() == 1


def test_a_selector_refuses_both_a_key_and_an_id() -> None:
    with pytest.raises(CutoverError):
        Selector("hero_slide", natural_key="شريحة العميل", entity_id=1)


def test_a_selector_refuses_neither_a_key_nor_an_id() -> None:
    with pytest.raises(CutoverError):
        Selector("hero_slide")


def test_a_selector_refuses_an_unknown_entity_type() -> None:
    with pytest.raises(CutoverError):
        Selector("invoice", entity_id=1)


def test_the_cli_refuses_mixing_the_two_selectors(importer: PreviewImporter) -> None:
    args = argparse.Namespace(
        target=["hero_slide:شريحة العميل"], entity_type="hero_slide", entity_id=1
    )

    with pytest.raises(CutoverError):
        _preserve_selectors(args)


def test_the_cli_refuses_an_id_without_its_entity_type() -> None:
    args = argparse.Namespace(target=[], entity_type=None, entity_id=7)

    with pytest.raises(CutoverError):
        _preserve_selectors(args)


def test_the_cli_refuses_no_selector_at_all() -> None:
    args = argparse.Namespace(target=[], entity_type=None, entity_id=None)

    with pytest.raises(CutoverError):
        _preserve_selectors(args)


def test_the_cli_builds_an_id_selector(importer: PreviewImporter) -> None:
    args = argparse.Namespace(target=[], entity_type="hero_slide", entity_id=12)

    assert _preserve_selectors(args) == [Selector("hero_slide", entity_id=12)]


def test_preserve_reports_a_target_that_matches_nothing(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()

    results = preserve(db, "cutover-preview", ["hero_slide:not-a-slide"], apply=True)

    assert [r.outcome for r in results] == ["unknown"]


def test_preserve_rejects_a_malformed_target(importer: PreviewImporter, db: Session) -> None:
    importer.seed()

    with pytest.raises(CutoverError):
        preserve(db, "cutover-preview", ["hero_slide"], apply=True)


def test_preserve_records_an_audit_entry(importer: PreviewImporter, db: Session) -> None:
    importer.seed()

    preserve(db, "cutover-preview", [HERO_TARGET], apply=True)

    entry = db.query(AuditLog).filter_by(action="preview.preserve").one()
    assert entry.entity_type == "hero_slide"
    assert entry.meta["natural_key"] == "شريحة العميل"
    assert entry.meta["promoted_media"] == ["hero-art"]


def test_preserve_on_an_unknown_batch_refuses(db: Session) -> None:
    with pytest.raises(CutoverError):
        preserve(db, "no-such-batch", [HERO_TARGET], apply=True)


# ── purge, after the cutover decisions are made ──────────────────────────────
def test_purge_dry_run_matches_the_real_purge_and_mutates_nothing(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()
    before = (db.query(HeroSlide).count(), db.query(MediaAsset).count())

    dry = importer.purge(apply=False)

    assert (db.query(HeroSlide).count(), db.query(MediaAsset).count()) == before

    applied = importer.purge(apply=True)

    def verdicts(plan) -> list[tuple[str, str]]:
        # The applied run additionally reports the storage objects it removed and the
        # fate of the batch row itself; the eligibility decisions are what must match.
        return [
            (action.outcome, action.target)
            for action in plan.actions
            if not action.target.startswith(("object:", "import_batch:"))
        ]

    assert verdicts(dry) == verdicts(applied)


def test_purge_removes_the_preview_records_that_were_not_preserved(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()
    preserve(db, "cutover-preview", [HERO_TARGET], apply=True)

    importer.purge(apply=True)

    assert db.query(HeroSlide).filter_by(title="شريحة تجريبية").count() == 0
    assert db.query(Product).count() == 0
    assert db.query(Category).count() == 0
    assert db.query(Coupon).count() == 0


def test_a_preserved_record_and_its_picture_survive_the_purge(
    importer: PreviewImporter, db: Session, storage: LocalStorageProvider
) -> None:
    importer.seed()
    preserve(db, "cutover-preview", [HERO_TARGET], apply=True)
    slide = db.query(HeroSlide).filter_by(title="شريحة العميل").one()
    asset = db.query(MediaAsset).filter_by(original_filename="hero-art-v1.png").one()

    importer.purge(apply=True)

    assert db.query(HeroSlide).filter_by(id=slide.id).count() == 1
    assert db.query(MediaAsset).filter_by(id=asset.id).count() == 1
    assert db.query(HeroSlide).filter_by(id=slide.id).one().image_url == asset.url
    assert storage.exists(asset.stored_key), "the object behind a preserved slide was deleted"


def test_media_still_shown_by_surviving_content_is_never_deleted(
    importer: PreviewImporter, db: Session, storage: LocalStorageProvider
) -> None:
    """The shared-picture case: one asset, one preserved user and several doomed ones."""
    importer.seed()
    tile = db.query(MediaAsset).filter_by(original_filename="tile-v1.png").one()
    # An owner category happens to use a picture the preview batch owns.
    db.add(Category(slug="owner-image-holder", name="صورة المالك", image_url=tile.url))
    db.commit()

    plan = importer.purge(apply=True)

    assert db.query(MediaAsset).filter_by(id=tile.id).count() == 1
    assert storage.exists(tile.stored_key)
    blocked = [a for a in plan.actions if a.outcome == "blocked"]
    assert any("media_asset:tile" == a.target for a in blocked)


def test_the_plan_reports_that_shared_picture_before_anything_is_deleted(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()
    tile = db.query(MediaAsset).filter_by(original_filename="tile-v1.png").one()
    db.add(Category(slug="owner-image-holder", name="صورة المالك", image_url=tile.url))
    db.commit()

    report = build_cutover_plan(importer)

    assert "media_asset:tile" in targets(report["media_at_risk"])
    assert "media_asset:tile" not in targets(report["media_to_delete"])


def test_owner_and_bootstrap_content_survives_the_purge(
    importer: PreviewImporter, db: Session, bootstrapped: None
) -> None:
    db.add(Category(slug="owner-cat", name="قسم المالك"))
    db.add(DeliveryArea(name="منطقة المالك", delivery_fee=0))
    db.commit()
    importer.seed()

    importer.purge(apply=True)

    assert db.query(Category).filter_by(slug="owner-cat").count() == 1
    assert db.query(DeliveryArea).filter_by(name="منطقة المالك").count() == 1
    assert db.query(StoreSettings).count() == 1
    assert db.query(StaticPage).count() == 1
    assert db.query(InstanceMetadata).count() == 1
    assert db.query(HomeSection).filter_by(section_key="featured").count() == 1


# ── verify ───────────────────────────────────────────────────────────────────
def test_verify_passes_on_a_clean_post_purge_state(
    importer: PreviewImporter, db: Session, bootstrapped: None
) -> None:
    importer.seed()
    preserve(db, "cutover-preview", [HERO_TARGET], apply=True)
    importer.purge(apply=True)

    checks = verify_state(db, media_base_url="/media")

    assert [check.name for check in checks if not check.ok] == []


def test_verify_flags_content_pointing_at_a_deleted_upload(
    importer: PreviewImporter, db: Session, bootstrapped: None
) -> None:
    importer.seed()
    # An owner slide made in Admin, pointing at a preview picture, with no batch record
    # to protect it: exactly the breakage the reference check exists to catch.
    tile = db.query(MediaAsset).filter_by(original_filename="tile-v1.png").one()
    orphan = HeroSlide(title="شريحة يتيمة", image_url=tile.url)
    db.add(orphan)
    db.commit()
    db.delete(tile)
    db.commit()

    checks = verify_state(db, media_base_url="/media")

    failed = [check for check in checks if not check.ok]
    assert any("missing media asset" in check.name for check in failed)


def test_verify_flags_a_batch_record_whose_row_vanished(
    importer: PreviewImporter, db: Session, bootstrapped: None
) -> None:
    importer.seed()
    db.delete(db.query(Coupon).one())
    db.commit()

    checks = verify_state(db, media_base_url="/media")

    failed = [check.name for check in checks if not check.ok]
    assert any("missing row" in name for name in failed)


def test_verify_ignores_a_static_frontend_asset(
    importer: PreviewImporter, db: Session, bootstrapped: None
) -> None:
    db.add(HeroSlide(title="إعلان", image_url="/hero-1-pic.png"))
    db.commit()

    checks = verify_state(db, media_base_url="/media")

    assert [check.name for check in checks if not check.ok] == []


def test_a_second_plan_after_the_purge_reports_a_clean_state(
    importer: PreviewImporter, db: Session, bootstrapped: None
) -> None:
    importer.seed()
    preserve(db, "cutover-preview", [HERO_TARGET], apply=True)
    importer.purge(apply=True)

    report = build_cutover_plan(importer)

    assert report["exists"] is False
    assert report["would_delete_total"] == 0
    assert report["surviving"]["hero_slide"] == 1  # the preserved one, now the owner's
