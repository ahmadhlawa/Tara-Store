"""Instance profile validation, and the template version's single source."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.core.template_version import (
    TemplateVersionError,
    template_version,
    version_file,
)
from app.instance.profile import (
    SUPPORTED_FEATURES,
    ProfileError,
    load_profile,
    parse_profile,
)
from app.models.store import STORE_SETTINGS_DEFAULTS

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PROFILE = REPO_ROOT / "instance" / "client-profile.example.yaml"
# This fork ships Tara's own profile in place of the template's demo one. It is the
# document a fresh Tara instance is actually bootstrapped from, so it belongs in
# every check below that the demo profile used to be in.
TARA_PROFILE = REPO_ROOT / "instance" / "tara-store.yaml"
SHIPPED_PROFILES = (EXAMPLE_PROFILE, TARA_PROFILE)


def minimal(**overrides) -> dict:
    document = {
        "profile_schema_version": 1,
        "template_version": "0.2.0",
        "client_slug": "acme-store",
        "store": {"name": "Acme"},
    }
    document.update(overrides)
    return document


# ── shipped profiles ─────────────────────────────────────────────────────────
def test_shipped_profiles_are_valid() -> None:
    for path in SHIPPED_PROFILES:
        profile = load_profile(path)
        assert profile.client_slug
        assert profile.store.name


def test_the_shipped_tara_profile_carries_the_tara_palette() -> None:
    """The profile is what a fresh instance is branded from, so it is where the old
    template teal survived the branding pass: the Python defaults in ThemeProfile
    only apply when a profile omits `theme:`, and this one states it outright. A
    fresh bootstrap wrote #1F4E4A into store settings and the storefront came up in
    the source project's colours with nothing in the frontend able to stop it."""
    profile = load_profile(TARA_PROFILE)
    assert profile.theme.primary_color == "#7F568F"
    assert profile.theme.secondary_color == "#D19F57"
    assert profile.theme.accent_color == "#4C7C63"

    text = TARA_PROFILE.read_text(encoding="utf-8").upper()
    for retired in ("#1F4E4A", "#C9A24B", "#2E7D5B"):
        assert retired not in text, f"{TARA_PROFILE.name} still carries {retired}"


def test_the_shipped_theme_matches_the_shipped_column_defaults() -> None:
    """Two sources write the same three colours — the profile on bootstrap and the
    column defaults for a settings row created without one. They have to agree, or
    which of them a store ends up with depends on how it was set up."""
    profile = load_profile(TARA_PROFILE)
    assert profile.theme.primary_color == STORE_SETTINGS_DEFAULTS["primary_color"]
    assert profile.theme.secondary_color == STORE_SETTINGS_DEFAULTS["secondary_color"]
    assert profile.theme.accent_color == STORE_SETTINGS_DEFAULTS["accent_color"]


def test_a_valid_profile_parses_with_defaults() -> None:
    profile = parse_profile(minimal())
    assert profile.client_slug == "acme-store"
    assert profile.store.currency_code == "ILS"
    # Features not mentioned default to enabled.
    assert profile.enabled_features() == list(SUPPORTED_FEATURES)


def test_profile_hash_is_stable_and_content_sensitive() -> None:
    first = parse_profile(minimal())
    assert first.profile_hash() == parse_profile(minimal()).profile_hash()
    other = parse_profile(minimal(client_slug="acme-store-two"))
    assert other.profile_hash() != first.profile_hash()


# ── rejection ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "bad_slug",
    ["Acme", "ab", "-acme", "acme-", "acme store", "acme_store", "a" * 41],
)
def test_invalid_slugs_are_rejected(bad_slug: str) -> None:
    with pytest.raises(ProfileError, match="client_slug"):
        parse_profile(minimal(client_slug=bad_slug))


@pytest.mark.parametrize(
    "bad_email",
    [
        "not-an-email",
        "owner@",
        "owner@localhost",
        # Reserved and special-use domains: the API's EmailStr refuses to serialise
        # them, so a profile carrying one would apply cleanly and then 500 the
        # storefront on `/store/settings`. Caught here instead.
        "owner@acceptance.example.test",
        "owner@shop.invalid",
    ],
)
def test_unusable_contact_emails_are_rejected(bad_email: str) -> None:
    with pytest.raises(ProfileError, match="contact.email"):
        parse_profile(minimal(contact={"email": bad_email}))


def test_a_usable_contact_email_is_accepted() -> None:
    profile = parse_profile(minimal(contact={"email": "owner@acme-store.com"}))
    assert profile.contact.email == "owner@acme-store.com"


def test_unsupported_schema_version_is_rejected() -> None:
    with pytest.raises(ProfileError, match="profile_schema_version"):
        parse_profile(minimal(profile_schema_version=99))


def test_malformed_colour_is_rejected() -> None:
    with pytest.raises(ProfileError, match="colour"):
        parse_profile(minimal(theme={"primary_color": "teal"}))


def test_unknown_feature_flag_is_rejected() -> None:
    with pytest.raises(ProfileError, match="unknown feature flag"):
        parse_profile(minimal(features={"crypto_payments": True}))


def test_missing_required_value_is_rejected() -> None:
    document = minimal()
    del document["store"]
    with pytest.raises(ProfileError, match="store"):
        parse_profile(document)


def test_unknown_home_section_type_is_rejected() -> None:
    with pytest.raises(ProfileError, match="unknown home section type"):
        parse_profile(minimal(home_sections=[{"key": "x", "type": "carousel_of_doom"}]))


def test_duplicate_home_section_keys_are_rejected() -> None:
    sections = [
        {"key": "featured", "type": "featured_products"},
        {"key": "featured", "type": "bestsellers"},
    ]
    with pytest.raises(ProfileError, match="duplicate home section"):
        parse_profile(minimal(home_sections=sections))


def test_bad_currency_code_is_rejected() -> None:
    with pytest.raises(ProfileError, match="currency"):
        parse_profile(minimal(store={"name": "Acme", "currency_code": "shekel"}))


def test_a_non_mapping_document_is_rejected() -> None:
    with pytest.raises(ProfileError, match="mapping"):
        parse_profile(["not", "a", "mapping"])


def test_a_missing_file_is_reported_clearly(tmp_path: Path) -> None:
    with pytest.raises(ProfileError, match="not found"):
        load_profile(tmp_path / "nope.yaml")


def test_malformed_yaml_is_reported_clearly(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("store: [unclosed\n", encoding="utf-8")
    with pytest.raises(ProfileError, match="not valid YAML"):
        load_profile(path)


# ── secrets ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "secret_field",
    [
        {"database_url": "mysql+pymysql://u:p@h/db"},
        {"secret_key": "abc"},
        {"admin_password": "hunter2"},
        {"jwt_secret": "abc"},
        {"r2_access_key_id": "abc"},
        {"api_key": "abc"},
        {"private_key": "-----BEGIN"},
    ],
)
def test_secret_like_top_level_keys_are_rejected(secret_field: dict) -> None:
    with pytest.raises(ProfileError, match="looks like a secret"):
        parse_profile(minimal(**secret_field))


def test_secret_like_keys_are_rejected_at_any_depth() -> None:
    with pytest.raises(ProfileError, match="looks like a secret"):
        parse_profile(minimal(contact={"phone": "1", "smtp_password": "x"}))

    with pytest.raises(ProfileError, match="looks like a secret"):
        parse_profile(
            minimal(home_sections=[{"key": "a", "type": "categories", "access_token": "x"}])
        )


def test_shipped_profiles_contain_no_secret_like_keys() -> None:
    """Belt and braces: the files we tell operators to copy must stay non-secret."""
    for path in SHIPPED_PROFILES:
        text = path.read_text(encoding="utf-8").lower()
        for forbidden in ("password:", "secret:", "database_url:", "private_key:"):
            assert forbidden not in text, f"{path.name} contains {forbidden}"
        # It must also actually parse, which is where the structural rejection happens.
        load_profile(path)


def test_an_unknown_top_level_key_is_rejected() -> None:
    with pytest.raises(ProfileError):
        parse_profile(minimal(unexpected_section={"a": 1}))


# ── template version ─────────────────────────────────────────────────────────
def test_template_version_comes_from_one_authoritative_file() -> None:
    resolved = version_file()
    assert resolved.name == "VERSION"
    assert resolved.read_text(encoding="utf-8").strip() == template_version()


def test_template_version_is_not_duplicated_in_python_sources() -> None:
    """Nothing may hard-code the template version alongside the VERSION file."""
    current = template_version()
    backend = Path(__file__).resolve().parents[1]
    offenders = []
    for path in backend.rglob("*.py"):
        if ".venv" in path.parts or path.name == "test_instance_profile.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if f'"{current}"' in line or f"'{current}'" in line:
                offenders.append(f"{path.relative_to(backend)}:{number}")
    assert not offenders, f"template version hard-coded outside VERSION: {offenders}"


def test_a_malformed_version_file_is_rejected(tmp_path: Path, monkeypatch) -> None:
    bad = tmp_path / "VERSION"
    bad.write_text("not-a-version\n", encoding="utf-8")
    monkeypatch.setenv("TEMPLATE_VERSION_FILE", str(bad))
    template_version.cache_clear()
    try:
        with pytest.raises(TemplateVersionError, match="MAJOR.MINOR.PATCH"):
            template_version()
    finally:
        monkeypatch.delenv("TEMPLATE_VERSION_FILE", raising=False)
        template_version.cache_clear()


def test_profiles_declare_a_template_version_matching_the_repository() -> None:
    current = template_version()
    for path in SHIPPED_PROFILES:
        declared = yaml.safe_load(path.read_text(encoding="utf-8"))["template_version"]
        assert declared == current, f"{path.name} targets {declared}, repository is {current}"
