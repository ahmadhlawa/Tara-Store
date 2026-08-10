"""Spreadsheet → canonical dataset → existing importer.

The last test in this file is the one that matters most: a workbook prepared here is fed
to `PreviewImporter` unchanged, so the converter cannot drift away from the importer that
consumes its output.

Workbooks are built in-process. No client file, no real catalog and no binary fixture is
committed anywhere near this suite.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.catalog_prep import PreparationError, prepare_catalog, read_sheets, render_yaml
from app.catalog_prep.workbook import WorkbookError
from app.models import Category, MediaAsset, Product, ProductImage
from app.preview.importer import PreviewImporter
from app.storage.local import LocalStorageProvider

PREPARE_KWARGS: dict[str, Any] = {
    "batch_key": "client-catalog",
    "source_label": "Client workbook",
    "media_prefix": "tara-store/client/",
}

CATEGORY_HEADERS = [
    "name",
    "slug",
    "parent_name",
    "description",
    "image_filename",
    "sort_order",
    "is_featured",
    "is_active",
]


def write_workbook(path: Path, *, products: list[dict], categories: list[dict]) -> Path:
    """A workbook with exactly the columns the given rows mention, in a stable order."""
    book = Workbook()
    book.remove(book.active)

    def sheet(name: str, rows: list[dict], preferred: list[str]) -> None:
        headers = [column for column in preferred if any(column in row for row in rows)]
        headers += sorted({key for row in rows for key in row} - set(headers))
        worksheet = book.create_sheet(name)
        worksheet.append(headers)
        for row in rows:
            worksheet.append([row.get(column) for column in headers])

    sheet("categories", categories, CATEGORY_HEADERS)
    sheet("products", products, ["name", "sku", "category_slug", "price"])
    book.save(path)
    return path


def media(db: Session, *filenames: str, duplicate: str | None = None) -> None:
    """Put files in the Media Library the way an upload would have.

    `duplicate` is only reachable on a library that predates the uniqueness rule, so
    the index is dropped first: current databases cannot hold two rows under one name,
    but preparation still has to refuse an old or hand-edited one rather than guess.
    """
    if duplicate:
        db.execute(text("DROP INDEX ix_media_assets_original_filename"))
    for position, filename in enumerate(filenames + ((duplicate,) if duplicate else ()), start=1):
        db.add(
            MediaAsset(
                original_filename=filename,
                stored_key=f"tara-store/media/{position}-{filename}",
                content_type="image/jpeg",
                size_bytes=1024,
                url=f"/media/tara-store/media/{position}-{filename}",
                storage_provider="local",
            )
        )
    db.flush()


def prepare(db: Session, path: Path, **overrides: Any):
    return prepare_catalog(db, read_sheets(path), **{**PREPARE_KWARGS, **overrides})


@pytest.fixture()
def minimal(tmp_path: Path, db: Session) -> Path:
    media(db, "VST-1001-01.jpg")
    return write_workbook(
        tmp_path / "catalog.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[
            {
                "name": "Printed mug",
                "sku": "VST-1001",
                "category_slug": "gifts",
                "price": "35.00",
                "image_1": "VST-1001-01.jpg",
            }
        ],
    )


# ── the happy paths ──────────────────────────────────────────────────────────
def test_a_minimal_workbook_becomes_a_valid_dataset(db: Session, minimal: Path) -> None:
    prepared = prepare(db, minimal)

    assert prepared.counts["products"] == 1
    assert prepared.counts["categories"] == 1
    assert prepared.counts["media_resolved"] == 1

    product = prepared.dataset.products[0]
    assert product.slug == "printed-mug"
    assert product.sku == "VST-1001"
    assert product.price == Decimal("35.00")
    assert product.category == "gifts"
    # System-generated: the client never supplies a slug, a search text or an id.
    assert prepared.dataset.categories[0].slug == "gifts"


def test_many_rows_keep_their_spreadsheet_order(tmp_path: Path, db: Session) -> None:
    media(db, "a.jpg", "b.jpg")
    workbook = write_workbook(
        tmp_path / "many.xlsx",
        categories=[
            {"name": "Gifts", "slug": "gifts"},
            {"name": "Mugs", "slug": "mugs", "parent_name": "Gifts"},
            {"name": "Cards", "slug": "cards"},
        ],
        products=[
            {"name": "Beta", "category_slug": "mugs", "price": 20, "image_1": "a.jpg"},
            {"name": "Alpha", "category_slug": "gifts", "price": 10},
            {"name": "Gamma", "category_slug": "cards", "price": 30, "image_1": "b.jpg"},
        ],
    )

    prepared = prepare(db, workbook)

    assert [item.slug for item in prepared.dataset.products] == ["beta", "alpha", "gamma"]
    assert [item.slug for item in prepared.dataset.categories] == ["gifts", "mugs", "cards"]
    assert prepared.dataset.categories[1].parent == "gifts"
    assert [item.sort_order for item in prepared.dataset.products] == [0, 1, 2]


def test_image_columns_are_dynamic_and_ordered(tmp_path: Path, db: Session) -> None:
    """`image_1 … image_n` with no fixed ceiling, and `image_1` is the cover."""
    filenames = [f"VST-1001-{position:02d}.jpg" for position in range(1, 13)]
    media(db, *filenames)
    columns = {f"image_{position}": name for position, name in enumerate(filenames, start=1)}
    workbook = write_workbook(
        tmp_path / "gallery.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[{"name": "Mug", "category_slug": "gifts", "price": 10, **columns}],
    )

    prepared = prepare(db, workbook)
    product = prepared.dataset.products[0]
    keys_to_files = {item.key: item.library_filename for item in prepared.dataset.media}

    assert len(product.images) == 12
    assert [keys_to_files[key] for key in product.images] == filenames
    assert keys_to_files[product.gallery[0]] == "VST-1001-01.jpg"


def test_a_blank_image_column_is_skipped_not_padded(tmp_path: Path, db: Session) -> None:
    media(db, "one.jpg", "three.jpg")
    workbook = write_workbook(
        tmp_path / "gaps.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[
            {
                "name": "Mug",
                "category_slug": "gifts",
                "price": 10,
                "image_1": "one.jpg",
                "image_2": "   ",
                "image_3": "three.jpg",
            }
        ],
    )

    prepared = prepare(db, workbook)
    keys_to_files = {item.key: item.library_filename for item in prepared.dataset.media}

    assert [keys_to_files[key] for key in prepared.dataset.products[0].images] == [
        "one.jpg",
        "three.jpg",
    ]


def test_a_filename_resolves_to_that_exact_media_asset(tmp_path: Path, db: Session) -> None:
    media(db, "wanted.jpg", "other.jpg")
    workbook = write_workbook(
        tmp_path / "resolve.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts", "image_filename": "other.jpg"}],
        products=[
            {"name": "Mug", "category_slug": "gifts", "price": 10, "image_1": "wanted.jpg"}
        ],
    )

    prepared = prepare(db, workbook)
    by_key = {item.key: item.library_filename for item in prepared.dataset.media}

    assert by_key[prepared.dataset.products[0].images[0]] == "wanted.jpg"
    assert by_key[prepared.dataset.categories[0].image] == "other.jpg"
    # Storage detail never reaches the dataset: no URL, no key, no provider.
    document = render_yaml(prepared.document)
    assert "/media/" not in document
    assert "stored_key" not in document


def test_renamed_media_resolves_only_by_its_new_filename(tmp_path: Path, db: Session) -> None:
    media(db, "OLD.jpg")
    asset = db.query(MediaAsset).filter_by(original_filename="OLD.jpg").one()
    asset.original_filename = "NEW.jpg"
    db.commit()

    old = write_workbook(
        tmp_path / "old.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[{"name": "Mug", "category_slug": "gifts", "price": 10, "image_1": "OLD.jpg"}],
    )
    with pytest.raises(PreparationError):
        prepare(db, old)

    new = write_workbook(
        tmp_path / "new.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[{"name": "Mug", "category_slug": "gifts", "price": 10, "image_1": "NEW.jpg"}],
    )
    prepared = prepare(db, new)
    assert len(prepared.dataset.media) == 1
    assert prepared.dataset.media[0].library_filename == "NEW.jpg"


def test_values_are_normalised(tmp_path: Path, db: Session) -> None:
    """Booleans, prices and whole numbers, in the spellings a client actually types."""
    workbook = write_workbook(
        tmp_path / "values.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts", "is_featured": "YES"}],
        products=[
            {
                "name": "  Spaced mug  ",
                "category_slug": "gifts",
                "price": "1,250.5",
                "compare_at_price": 1400,
                "cost_price": "٩٩٠",
                "stock_quantity": "12",
                "track_inventory": "no",
                "is_featured": 1,
                "is_new": "true",
                "is_bestseller": "0",
                "is_active": "Yes",
                "low_stock_threshold": 5.0,
            }
        ],
    )

    prepared = prepare(db, workbook)
    product = prepared.dataset.products[0]

    assert product.name == "Spaced mug"
    assert product.price == Decimal("1250.50")
    assert product.compare_at_price == Decimal("1400.00")
    assert product.cost_price == Decimal("990.00")
    assert product.stock_quantity == 12
    assert product.low_stock_threshold == 5
    assert (product.track_inventory, product.is_featured) == (False, True)
    assert (product.is_new, product.is_bestseller, product.is_active) == (True, False, True)
    assert prepared.dataset.categories[0].is_featured is True


def test_specifications_and_options_are_parsed(tmp_path: Path, db: Session) -> None:
    workbook = write_workbook(
        tmp_path / "details.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[
            {
                "name": "Mug",
                "category_slug": "gifts",
                "price": 10,
                "spec_1_name": "Material",
                "spec_1_value": "Ceramic",
                "spec_2_name": "Capacity",
                "spec_2_value": "330ml",
                "option_1_name": "Colour",
                "option_1_values": "Red, White , Black",
                "option_2_name": "Size",
                "option_2_values": "S|M|L",
            }
        ],
    )

    product = prepare(db, workbook).dataset.products[0]

    assert [(spec.name, spec.value) for spec in product.specifications] == [
        ("Material", "Ceramic"),
        ("Capacity", "330ml"),
    ]
    assert [(option.name, option.values) for option in product.options] == [
        ("Colour", ["Red", "White", "Black"]),
        ("Size", ["S", "M", "L"]),
    ]


def test_package_items_reference_products_by_sku(tmp_path: Path, db: Session) -> None:
    workbook = write_workbook(
        tmp_path / "package.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[
            {"name": "Mug", "sku": "VST-1001", "category_slug": "gifts", "price": 10},
            {"name": "Card", "sku": "VST-1005", "category_slug": "gifts", "price": 5},
            {
                "name": "Gift set",
                "sku": "VST-2000",
                "category_slug": "gifts",
                "price": 20,
                "product_type": "package",
                "package_items": "VST-1001 x2; VST-1005",
            },
        ],
    )

    package = prepare(db, workbook).dataset.products[2]

    assert [(item.product, item.quantity) for item in package.package_items] == [
        ("mug", 2),
        ("card", 1),
    ]


# ── the refusals ─────────────────────────────────────────────────────────────
def issues(exc: PreparationError) -> list[str]:
    return [issue.render() for issue in exc.issues]


def test_a_missing_media_file_is_an_error(tmp_path: Path, db: Session) -> None:
    workbook = write_workbook(
        tmp_path / "missing.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[
            {"name": "Mug", "category_slug": "gifts", "price": 10, "image_1": "VST-1012-02.jpg"}
        ],
    )

    with pytest.raises(PreparationError) as caught:
        prepare(db, workbook)

    assert any("VST-1012-02.jpg" in message and "not found" in message for message in issues(caught.value))


def test_an_ambiguous_media_filename_is_an_error(tmp_path: Path, db: Session) -> None:
    """Two uploads under one name: the tool refuses rather than picking one."""
    media(db, "twice.jpg", duplicate="twice.jpg")
    workbook = write_workbook(
        tmp_path / "ambiguous.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[{"name": "Mug", "category_slug": "gifts", "price": 10, "image_1": "twice.jpg"}],
    )

    with pytest.raises(PreparationError) as caught:
        prepare(db, workbook)

    assert any("matches 2 Media Library files" in message for message in issues(caught.value))


def test_media_matching_is_case_sensitive(tmp_path: Path, db: Session) -> None:
    media(db, "VST-1001-01.jpg")
    workbook = write_workbook(
        tmp_path / "case.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[
            {"name": "Mug", "category_slug": "gifts", "price": 10, "image_1": "vst-1001-01.jpg"}
        ],
    )

    with pytest.raises(PreparationError):
        prepare(db, workbook)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"name": None, "category_slug": "gifts", "price": 10}, "name"),
        ({"name": "Mug", "category_slug": "gifts", "price": None}, "price"),
        ({"name": "Mug", "category_slug": "gifts", "price": "free"}, "price"),
        ({"name": "Mug", "category_slug": "nope", "price": 10}, "category_slug"),
        ({"name": "Mug", "category_slug": "gifts", "price": 10, "product_type": "widget"}, "product_type"),
        ({"name": "Mug", "category_slug": "gifts", "price": 10, "is_featured": "maybe"}, "is_featured"),
        ({"name": "Mug", "category_slug": "gifts", "price": 10, "stock_quantity": "1.5"}, "stock_quantity"),
        ({"name": "Mug", "category_slug": "gifts", "price": 10, "product_type": "package"}, "package_items"),
    ],
)
def test_an_invalid_field_is_reported_with_its_sheet_row_and_column(
    tmp_path: Path, db: Session, row: dict, expected: str
) -> None:
    workbook = write_workbook(
        tmp_path / "invalid.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[row],
    )

    with pytest.raises(PreparationError) as caught:
        prepare(db, workbook)

    reported = issues(caught.value)
    assert any(message.startswith("products row 2: ") and expected in message for message in reported), reported


def test_a_duplicate_sku_is_refused(tmp_path: Path, db: Session) -> None:
    workbook = write_workbook(
        tmp_path / "dupe.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[
            {"name": "Mug", "sku": "VST-1001", "category_slug": "gifts", "price": 10},
            {"name": "Other mug", "sku": "VST-1001", "category_slug": "gifts", "price": 12},
        ],
    )

    with pytest.raises(PreparationError) as caught:
        prepare(db, workbook)

    assert any("sku 'VST-1001' is already used by row 2" in message for message in issues(caught.value))


def test_a_package_referencing_an_unknown_product_is_refused(tmp_path: Path, db: Session) -> None:
    workbook = write_workbook(
        tmp_path / "badpackage.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[
            {
                "name": "Gift set",
                "category_slug": "gifts",
                "price": 20,
                "product_type": "package",
                "package_items": "VST-9999 x2",
            }
        ],
    )

    with pytest.raises(PreparationError) as caught:
        prepare(db, workbook)

    assert any("VST-9999" in message for message in issues(caught.value))


def test_every_bad_row_is_reported_not_just_the_first(tmp_path: Path, db: Session) -> None:
    workbook = write_workbook(
        tmp_path / "several.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[
            {"name": "Mug", "category_slug": "gifts", "price": "free"},
            {"name": "Card", "category_slug": "gifts", "price": "also free"},
        ],
    )

    with pytest.raises(PreparationError) as caught:
        prepare(db, workbook)

    assert {issue.row for issue in caught.value.issues} == {2, 3}


def test_a_single_csv_names_the_supported_layouts(tmp_path: Path, db: Session) -> None:
    lonely = tmp_path / "products.csv"
    lonely.write_text("name\n", encoding="utf-8")

    with pytest.raises(WorkbookError, match="directory"):
        read_sheets(lonely)


def test_a_directory_of_csvs_is_read(tmp_path: Path, db: Session) -> None:
    folder = tmp_path / "csvs"
    folder.mkdir()
    (folder / "categories.csv").write_text("name,slug\nGifts,gifts\n", encoding="utf-8-sig")
    (folder / "products.csv").write_text(
        "name,category_slug,price\nMug,gifts,10.00\n", encoding="utf-8-sig"
    )

    prepared = prepare(db, folder)

    assert prepared.counts == {
        "categories": 1,
        "products": 1,
        "images_referenced": 0,
        "media_resolved": 0,
        "packages": 0,
        "specifications": 0,
        "options": 0,
    }


# ── output ───────────────────────────────────────────────────────────────────
def test_generated_yaml_is_deterministic(db: Session, minimal: Path) -> None:
    first = render_yaml(prepare(db, minimal).document)
    second = render_yaml(prepare(db, minimal).document)

    assert first == second
    assert "generated_at" not in first
    assert str(minimal.parent) not in first  # no absolute path from this machine


def test_preparation_writes_nothing_to_the_database(db: Session, minimal: Path) -> None:
    before = (db.query(Product).count(), db.query(Category).count(), db.query(MediaAsset).count())

    prepare(db, minimal)

    assert (
        db.query(Product).count(),
        db.query(Category).count(),
        db.query(MediaAsset).count(),
    ) == before
    assert not db.new and not db.dirty and not db.deleted


# ── the whole pipeline ───────────────────────────────────────────────────────
def test_the_generated_dataset_imports_through_the_existing_importer(
    tmp_path: Path, db: Session
) -> None:
    """Prepare a workbook, then seed the result with `PreviewImporter` untouched.

    This is the contract test between the two halves: if the converter emitted anything
    the importer does not understand, or lost the image order, it fails here.
    """
    media(db, "mug-01.jpg", "mug-02.jpg", "mug-03.jpg", "cat.jpg")
    workbook = write_workbook(
        tmp_path / "full.xlsx",
        categories=[
            {"name": "Gifts", "slug": "gifts", "image_filename": "cat.jpg", "is_featured": "yes"},
            {"name": "Mugs", "slug": "mugs", "parent_name": "Gifts"},
        ],
        products=[
            {
                "name": "Printed mug",
                "sku": "VST-1001",
                "category_slug": "mugs",
                "price": "35.00",
                "compare_at_price": "45.00",
                "stock_quantity": 8,
                "short_description": "A mug",
                "image_1": "mug-01.jpg",
                "image_2": "mug-02.jpg",
                "image_3": "mug-03.jpg",
                "spec_1_name": "Material",
                "spec_1_value": "Ceramic",
                "option_1_name": "Colour",
                "option_1_values": "Red, White",
            },
            {"name": "Greeting card", "sku": "VST-1005", "category_slug": "gifts", "price": "5.00"},
            {
                "name": "Gift set",
                "sku": "VST-2000",
                "category_slug": "gifts",
                "price": "38.00",
                "product_type": "package",
                "package_items": "VST-1001 x1; VST-1005 x2",
            },
        ],
    )

    prepared = prepare(db, workbook)

    # Round-trip through the file the operator would actually hand to the importer.
    dataset_file = tmp_path / "generated.yaml"
    dataset_file.write_text(render_yaml(prepared.document), encoding="utf-8")

    from app.preview.dataset import load_dataset

    dataset = load_dataset(dataset_file)
    storage = LocalStorageProvider(tmp_path / "media", "/media")
    plan = PreviewImporter(db, dataset, storage=storage).seed()

    assert not plan.blocked

    mug = db.query(Product).filter_by(slug="printed-mug").one()
    assert mug.sku == "VST-1001"
    assert mug.price == Decimal("35.00")
    assert [image.sort_order for image in mug.images] == [0, 1, 2]
    assert mug.primary_image_url == mug.images[0].url
    # image_1 is the cover, and it is the asset the spreadsheet named first.
    cover = db.query(MediaAsset).filter_by(original_filename="mug-01.jpg").one()
    assert mug.primary_image_url == cover.url
    assert [spec.name for spec in mug.specifications] == ["Material"]
    assert [value.value for value in mug.options[0].values] == ["Red", "White"]

    mugs = db.query(Category).filter_by(slug="mugs").one()
    assert mugs.parent.slug == "gifts"
    assert db.query(Category).filter_by(slug="gifts").one().image_url == (
        db.query(MediaAsset).filter_by(original_filename="cat.jpg").one().url
    )

    package = db.query(Product).filter_by(slug="gift-set").one()
    assert [(item.included_product.sku, item.quantity) for item in package.package_items] == [
        ("VST-1001", 1),
        ("VST-1005", 2),
    ]

    # The library assets stay the owner's: the batch created no media row of its own,
    # and every product image points at a file that was already there.
    assert db.query(MediaAsset).count() == 4
    library_urls = {asset.url for asset in db.query(MediaAsset)}
    assert {image.url for image in db.query(ProductImage)} <= library_urls


def test_re_seeding_a_prepared_dataset_changes_nothing(tmp_path: Path, db: Session) -> None:
    """Idempotency survives the round trip: the second seed reports no work to do."""
    media(db, "mug-01.jpg")
    workbook = write_workbook(
        tmp_path / "idem.xlsx",
        categories=[{"name": "Gifts", "slug": "gifts"}],
        products=[
            {"name": "Mug", "category_slug": "gifts", "price": "10.00", "image_1": "mug-01.jpg"}
        ],
    )
    dataset = prepare(db, workbook).dataset
    storage = LocalStorageProvider(tmp_path / "media", "/media")

    PreviewImporter(db, dataset, storage=storage).seed()
    second = PreviewImporter(db, dataset, storage=storage).plan()

    assert "create" not in second.counts()
    assert "update" not in {
        action.outcome for action in second.actions if not action.target.startswith("import_batch")
    }
