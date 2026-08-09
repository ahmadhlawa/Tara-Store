"""Preview dataset validation.

Any dataset shipped in instance/preview/ is validated here too, so a typo in the
YAML is a test failure rather than something discovered during a client
demonstration. Tara ships none today — the fork deliberately left the template's
Vista demo catalogue behind — so that check is a standing guard rather than
coverage of a particular file, and the loader itself is exercised against a
fixture written per-test instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.preview.dataset import DatasetError, load_dataset, parse_dataset

INSTANCE_DIR = Path(__file__).resolve().parents[2] / "instance"
PREVIEW_DIR = INSTANCE_DIR / "preview"


def shipped_datasets() -> list[Path]:
    """Datasets committed to instance/preview/, of which there are currently none.

    The directory itself is not in git — it is empty, and git cannot track an
    empty directory — so a checkout may not have it at all. `glob` on a missing
    directory is empty rather than an error, which is the behaviour wanted here.
    """
    return sorted(PREVIEW_DIR.glob("*.yaml")) + sorted(PREVIEW_DIR.glob("*.yml"))


def write(tmp_path: Path, document: dict, name: str = "preview.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    return path


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


# ── the file loader ──────────────────────────────────────────────────────────────────
# These used to run against the template's shipped Vista catalogue, which is the
# one thing this fork did not copy. Most of what they asserted was that
# catalogue's own content — how many categories it had, that it advertised an
# offer — which says nothing about a repository that ships no dataset. What was
# worth keeping is the loader path itself: reading YAML off disk, which nothing
# else here covered, and the price-honesty rule, which is now a rule about any
# dataset rather than about that one.
def test_a_dataset_round_trips_through_the_file_loader(tmp_path: Path) -> None:
    path = write(tmp_path, minimal())
    dataset = load_dataset(path)

    assert dataset.batch_key == "test-preview"
    assert dataset.media_prefix.endswith("/")
    assert dataset.counts() == {
        "media": 1,
        "categories": 1,
        "products": 1,
        "delivery_areas": 0,
        "hero_slides": 0,
        "banners": 0,
        "home_sections": 0,
        "coupons": 0,
    }


def test_malformed_yaml_is_reported_clearly(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("products: [unclosed\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="not valid YAML"):
        load_dataset(path)


def test_an_empty_dataset_file_is_reported_clearly(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("# nothing here\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="is empty"):
        load_dataset(path)


# ── whatever this repository actually ships ─────────────────────────────────────
def test_every_shipped_preview_dataset_is_valid_and_price_honest() -> None:
    """Shipping no dataset is a valid state, and is where Tara stands.

    The rule matters the moment one is added: a preview catalogue is assembled
    from whatever could be read off a client's public pages, so a price that was
    guessed must not be dressed up as `confirmed` — that is the difference
    between a demonstration and a misrepresentation.
    """
    # Anchored to a directory that *is* tracked, so this cannot quietly degrade
    # into globbing the wrong root and passing forever.
    assert INSTANCE_DIR.is_dir()

    for path in shipped_datasets():
        dataset = load_dataset(path)
        assert dataset.media_prefix.endswith("/"), path.name
        claimed = [p.slug for p in dataset.products if p.origin == "confirmed"]
        assert not claimed, f"{path.name} marks guessed prices as confirmed: {claimed}"


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
