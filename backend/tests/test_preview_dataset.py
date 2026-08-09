"""Preview dataset validation.

The shipped Vista dataset is validated here too, so a typo in the YAML is a test
failure rather than something discovered during a client demonstration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.preview.dataset import DatasetError, load_dataset, parse_dataset

DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "instance" / "preview" / "vista-social-preview.yaml"
)


def minimal(**overrides) -> dict:
    document = {
        "preview_schema_version": 1,
        "batch_key": "test-preview",
        "source_label": "test",
        "media_prefix": "test/preview/",
        "media": [
            {
                "key": "tile",
                "alt_text": "tile",
                "start_color": "#112233",
                "end_color": "#445566",
            }
        ],
        "categories": [{"slug": "cat", "name": "قسم", "image": "tile", "origin": "inferred"}],
        "products": [
            {
                "slug": "prod",
                "name": "منتج",
                "category": "cat",
                "price": "10.00",
                "origin": "inferred",
            }
        ],
    }
    document.update(overrides)
    return document


def test_shipped_vista_dataset_is_valid() -> None:
    dataset = load_dataset(DATASET_PATH)
    assert dataset.batch_key == "vista-social-preview"
    assert dataset.media_prefix.endswith("/")
    counts = dataset.counts()
    assert 5 <= counts["categories"] <= 8
    # A demonstration catalogue, not a dump: wide enough to fill every storefront
    # section, small enough to stay reviewable and removable in one batch.
    assert 18 <= counts["products"] <= 60
    assert counts["delivery_areas"] >= 1
    assert counts["hero_slides"] >= 1


def test_shipped_dataset_advertises_at_least_one_offer_and_one_package() -> None:
    dataset = load_dataset(DATASET_PATH)
    assert any(product.compare_at_price is not None for product in dataset.products)
    assert any(product.package_items for product in dataset.products)


def test_shipped_dataset_marks_every_price_as_unverified() -> None:
    """No price on the Vista social pages was legible, so none may be `confirmed`."""
    dataset = load_dataset(DATASET_PATH)
    assert all(product.origin != "confirmed" for product in dataset.products)


def test_dataset_hash_is_stable_and_content_sensitive() -> None:
    first = parse_dataset(minimal())
    second = parse_dataset(minimal())
    assert first.dataset_hash() == second.dataset_hash()

    changed = minimal()
    changed["products"][0]["price"] = "11.00"
    assert parse_dataset(changed).dataset_hash() != first.dataset_hash()


def test_unknown_key_is_rejected() -> None:
    with pytest.raises(DatasetError, match="extra_forbidden|Extra inputs"):
        parse_dataset(minimal(unexpected_key="x"))


def test_credential_shaped_key_is_rejected_before_validation() -> None:
    with pytest.raises(DatasetError, match="looks like a secret"):
        parse_dataset(minimal(r2_secret_access_key="x"))


def test_product_referencing_an_unknown_category_is_rejected() -> None:
    document = minimal()
    document["products"][0]["category"] = "nope"
    with pytest.raises(DatasetError, match="unknown category"):
        parse_dataset(document)


def test_product_referencing_unknown_media_is_rejected() -> None:
    document = minimal()
    document["products"][0]["image"] = "nope"
    with pytest.raises(DatasetError, match="unknown media key"):
        parse_dataset(document)


def test_compare_at_price_below_price_is_rejected() -> None:
    document = minimal()
    document["products"][0]["compare_at_price"] = "5.00"
    with pytest.raises(DatasetError, match="compare_at_price must be above price"):
        parse_dataset(document)


def test_duplicate_product_slug_is_rejected() -> None:
    document = minimal()
    document["products"].append(dict(document["products"][0]))
    with pytest.raises(DatasetError, match="duplicate product slug"):
        parse_dataset(document)


def test_package_without_contents_is_rejected() -> None:
    document = minimal()
    document["products"][0]["product_type"] = "package"
    with pytest.raises(DatasetError, match="has no package items"):
        parse_dataset(document)


def test_package_cannot_contain_itself() -> None:
    document = minimal()
    document["products"][0]["product_type"] = "package"
    document["products"][0]["package_items"] = [{"product": "prod"}]
    with pytest.raises(DatasetError, match="cannot include itself"):
        parse_dataset(document)


@pytest.mark.parametrize("prefix", ["/absolute/", "relative", "a/../b/", "a//b/"])
def test_unsafe_media_prefix_is_rejected(prefix: str) -> None:
    """The prefix is the only containment a purge has; it must not be escapable."""
    with pytest.raises(DatasetError):
        parse_dataset(minimal(media_prefix=prefix))


def test_unsupported_schema_version_is_rejected() -> None:
    with pytest.raises(DatasetError, match="not supported"):
        parse_dataset(minimal(preview_schema_version=99))


def test_missing_file_is_reported_clearly(tmp_path: Path) -> None:
    with pytest.raises(DatasetError, match="not found"):
        load_dataset(tmp_path / "absent.yaml")
