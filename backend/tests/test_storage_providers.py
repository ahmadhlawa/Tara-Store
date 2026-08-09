"""Storage provider selection, object-key scoping, and the R2 adapter.

No network is touched: the R2 client is a stub that records the calls it received. What
is being tested is the part that is ours — key construction, prefix containment, and the
refusal to delete anything outside the configured namespace.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.enums import StorageProviderName
from app.storage import build_storage
from app.storage.base import build_stored_key, normalize_prefix, validate_image_upload
from app.storage.local import LocalStorageProvider
from app.storage.r2 import R2NotConfiguredError, R2StorageError, R2StorageProvider
from app.services.errors import DomainError
from app.services.placeholder_image import gradient_png

R2_ENV = {
    "STORAGE_PROVIDER": "r2",
    "R2_ACCOUNT_ID": "account",
    "R2_ACCESS_KEY_ID": "key-id",
    "R2_SECRET_ACCESS_KEY": "secret",
    "R2_BUCKET_NAME": "bucket",
    "R2_PUBLIC_BASE_URL": "https://media.example.test",
    "R2_OBJECT_PREFIX": "vista-store/",
}


class StubS3Client:
    """Records calls instead of making them."""

    def __init__(self, *, missing: set[str] | None = None) -> None:
        self.objects: dict[str, bytes] = {}
        self.puts: list[dict] = []
        self.deletes: list[str] = []
        self.missing = missing or set()

    def put_object(self, **kwargs) -> dict:
        self.puts.append(kwargs)
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return {}

    def head_object(self, *, Bucket: str, Key: str) -> dict:  # noqa: N803 - boto3 casing
        if Key in self.missing or Key not in self.objects:
            raise RuntimeError("404")
        return {"ContentLength": len(self.objects[Key])}

    def delete_object(self, *, Bucket: str, Key: str) -> dict:  # noqa: N803 - boto3 casing
        self.deletes.append(Key)
        self.objects.pop(Key, None)
        return {}


@pytest.fixture()
def stub() -> StubS3Client:
    return StubS3Client()


@pytest.fixture()
def r2(stub: StubS3Client) -> R2StorageProvider:
    return R2StorageProvider(
        account_id="account",
        access_key_id="key-id",
        secret_access_key="secret",
        bucket_name="bucket",
        public_base_url="https://media.example.test/",
        object_prefix="vista-store/",
        client=stub,
    )


# ── provider selection ───────────────────────────────────────────────────────
def test_default_configuration_selects_local_storage(tmp_path: Path) -> None:
    config = Settings(LOCAL_MEDIA_ROOT=str(tmp_path))
    provider = build_storage(config)
    assert isinstance(provider, LocalStorageProvider)
    assert provider.name == StorageProviderName.LOCAL.value


def test_r2_configuration_selects_the_r2_provider() -> None:
    provider = build_storage(Settings(**R2_ENV))
    assert isinstance(provider, R2StorageProvider)
    assert provider.name == StorageProviderName.R2.value
    assert provider.object_prefix == "vista-store/"


def test_selecting_r2_without_credentials_fails_loudly_and_names_what_is_missing() -> None:
    with pytest.raises(R2NotConfiguredError) as exc:
        build_storage(Settings(STORAGE_PROVIDER="r2"))
    message = str(exc.value)
    assert "R2_ACCOUNT_ID" in message and "R2_BUCKET_NAME" in message


def test_the_error_never_contains_a_credential_value() -> None:
    with pytest.raises(R2NotConfiguredError) as exc:
        build_storage(Settings(STORAGE_PROVIDER="r2", R2_ACCESS_KEY_ID="super-secret-value"))
    assert "super-secret-value" not in str(exc.value)


# ── keys and prefixes ────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("given", "expected"),
    [(None, ""), ("", ""), ("a", "a/"), ("/a/b/", "a/b/"), ("a//b", "a/b/")],
)
def test_prefix_normalisation(given: str | None, expected: str) -> None:
    assert normalize_prefix(given) == expected


@pytest.mark.parametrize("bad", ["../escape/", "a/../b", "a/./b"])
def test_traversal_in_a_prefix_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="traversal"):
        normalize_prefix(bad)


def test_stored_keys_are_collision_resistant() -> None:
    keys = {build_stored_key(".png", "p/") for _ in range(200)}
    assert len(keys) == 200
    assert all(key.startswith("p/") and key.endswith(".png") for key in keys)


def test_r2_keys_carry_the_object_prefix_then_the_caller_prefix(r2: R2StorageProvider) -> None:
    key = r2.build_key(".png", "vista-store/preview/")
    assert key.startswith("vista-store/vista-store/preview/")


def test_owns_key_is_true_only_inside_the_configured_prefix(r2: R2StorageProvider) -> None:
    assert r2.owns_key("vista-store/preview/abc.png")
    assert not r2.owns_key("someone-else/abc.png")
    assert not r2.owns_key("/vista-store/abc.png")
    assert not r2.owns_key("vista-store/../other/abc.png")
    assert not r2.owns_key("")


# ── upload / read / delete ───────────────────────────────────────────────────
def test_upload_stores_the_bytes_and_returns_a_public_url(
    r2: R2StorageProvider, stub: StubS3Client
) -> None:
    data = gradient_png(8, 8, (255, 0, 0), (0, 0, 255))
    stored = r2.save(data, content_type="image/png", extension=".png", prefix="preview/")

    assert stub.puts[0]["Bucket"] == "bucket"
    assert stub.puts[0]["ContentType"] == "image/png"
    assert stored.size_bytes == len(data)
    assert stored.key.startswith("vista-store/preview/")
    assert stored.url == f"https://media.example.test/{stored.key}"


def test_uploaded_object_is_then_visible(r2: R2StorageProvider) -> None:
    data = gradient_png(8, 8, (0, 0, 0), (255, 255, 255))
    stored = r2.save(data, content_type="image/png", extension=".png")
    assert r2.exists(stored.key) is True


def test_delete_removes_the_object(r2: R2StorageProvider, stub: StubS3Client) -> None:
    data = gradient_png(8, 8, (0, 0, 0), (255, 255, 255))
    stored = r2.save(data, content_type="image/png", extension=".png")

    r2.delete(stored.key)

    assert stub.deletes == [stored.key]
    assert r2.exists(stored.key) is False


def test_delete_refuses_a_key_outside_the_prefix(r2: R2StorageProvider, stub: StubS3Client) -> None:
    with pytest.raises(R2StorageError, match="outside the configured prefix"):
        r2.delete("someone-elses-backup/important.zip")
    assert stub.deletes == []


# ── existence and repair ─────────────────────────────────────────────────────
def test_exists_is_false_for_a_key_never_written(r2: R2StorageProvider) -> None:
    assert r2.exists("vista-store/preview/never-written.png") is False


def test_exists_never_probes_an_object_outside_the_prefix(r2: R2StorageProvider) -> None:
    class Loud(StubS3Client):
        def head_object(self, **kwargs):
            raise AssertionError("head_object must not be called for a foreign key")

    r2._client = Loud()
    assert r2.exists("someone-elses-backup/important.zip") is False


def test_restore_rewrites_the_same_key_and_keeps_the_url(
    r2: R2StorageProvider, stub: StubS3Client
) -> None:
    data = gradient_png(8, 8, (1, 2, 3), (4, 5, 6))
    stored = r2.save(data, content_type="image/png", extension=".png", prefix="preview/")
    stub.objects.pop(stored.key)
    assert r2.exists(stored.key) is False

    repaired = r2.restore(stored.key, data, content_type="image/png")

    assert repaired.key == stored.key
    assert repaired.url == stored.url
    assert repaired.size_bytes == len(data)
    assert r2.exists(stored.key) is True


def test_restore_refuses_a_key_outside_the_prefix(
    r2: R2StorageProvider, stub: StubS3Client
) -> None:
    before = len(stub.puts)
    with pytest.raises(R2StorageError, match="outside the configured prefix"):
        r2.restore("someone-elses-backup/important.zip", b"x", content_type="image/png")
    assert len(stub.puts) == before


def test_local_exists_and_restore_round_trip(tmp_path: Path) -> None:
    provider = LocalStorageProvider(tmp_path / "media", "/media")
    data = gradient_png(8, 8, (0, 0, 0), (255, 255, 255))
    stored = provider.save(data, content_type="image/png", extension=".png", prefix="preview/")

    assert provider.exists(stored.key) is True
    (provider.root / stored.key).unlink()
    assert provider.exists(stored.key) is False

    repaired = provider.restore(stored.key, data, content_type="image/png")

    assert repaired.key == stored.key
    assert repaired.url == stored.url
    assert (provider.root / stored.key).read_bytes() == data
    assert provider.exists(stored.key) is True


@pytest.mark.parametrize("outside", ["", "../escape.png", "missing.png"])
def test_local_exists_is_false_outside_the_media_root(tmp_path: Path, outside: str) -> None:
    provider = LocalStorageProvider(tmp_path / "media", "/media")
    assert provider.exists(outside) is False


def test_a_failing_upload_is_reported_without_the_credential() -> None:
    class Failing(StubS3Client):
        def put_object(self, **kwargs):
            raise RuntimeError("AccessDenied for secret-value")

    provider = R2StorageProvider(
        account_id="account",
        access_key_id="secret-value",
        secret_access_key="secret-value",
        bucket_name="bucket",
        public_base_url="https://media.example.test",
        object_prefix="p/",
        client=Failing(),
    )
    with pytest.raises(R2StorageError) as exc:
        provider.save(b"\x89PNG\r\n\x1a\n", content_type="image/png", extension=".png")
    assert "secret-value" not in str(exc.value)


def test_endpoint_is_derived_from_the_account_id(r2: R2StorageProvider) -> None:
    assert r2.endpoint_url == "https://account.r2.cloudflarestorage.com"


# ── local storage keeps working ──────────────────────────────────────────────
def test_local_storage_still_saves_reads_and_deletes(tmp_path: Path) -> None:
    provider = LocalStorageProvider(tmp_path / "media", "/media")
    data = gradient_png(8, 8, (1, 2, 3), (4, 5, 6))

    stored = provider.save(data, content_type="image/png", extension=".png")

    assert (provider.root / stored.key).read_bytes() == data
    assert stored.url == f"/media/{stored.key}"

    provider.delete(stored.key)
    assert not (provider.root / stored.key).exists()


def test_local_storage_honours_a_prefix(tmp_path: Path) -> None:
    provider = LocalStorageProvider(tmp_path / "media", "/media")
    stored = provider.save(
        gradient_png(4, 4, (0, 0, 0), (1, 1, 1)),
        content_type="image/png",
        extension=".png",
        prefix="vista-store/preview/",
    )
    assert stored.key.startswith("vista-store/preview/")
    assert (provider.root / stored.key).exists()


# ── validation applies to every provider ─────────────────────────────────────
def test_upload_validation_rejects_a_non_image() -> None:
    with pytest.raises(DomainError, match="نوع الملف غير مدعوم"):
        validate_image_upload(b"not an image at all", 5 * 1024 * 1024)


def test_upload_validation_rejects_an_oversized_file() -> None:
    with pytest.raises(DomainError, match="حجم الملف"):
        validate_image_upload(gradient_png(64, 64, (0, 0, 0), (255, 255, 255)), 16)
