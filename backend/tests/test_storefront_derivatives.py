from io import BytesIO

import pytest
from PIL import Image

from app.services.storefront_derivatives import (
    STOREFRONT_WIDTHS,
    backfill_storefront_derivatives,
    derivative_key_for,
    ensure_storefront_derivative,
)
from app.models import HeroSlide, MediaAsset
from app.storage.local import LocalStorageProvider
from app.storage.r2 import R2StorageError, R2StorageProvider
from tests.test_storage_providers import StubS3Client


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1200, 800), "purple").save(output, "PNG")
    return output.getvalue()


def provider(client: StubS3Client) -> R2StorageProvider:
    return R2StorageProvider(
        endpoint_url="https://account.r2.cloudflarestorage.com",
        access_key_id="key-id",
        secret_access_key="secret",
        bucket_name="bucket",
        public_base_url="https://media.example.test",
        object_prefix="tara-store/",
        client=client,
    )


def test_missing_derivative_is_generated_once_and_persisted_in_r2():
    client = StubS3Client()
    storage = provider(client)
    original = storage.save(image_bytes(), content_type="image/png", extension=".png")

    derivative = ensure_storefront_derivative(storage, original.key, 480)

    assert derivative.generated is True
    assert derivative.key == derivative_key_for(original.key, 480)
    assert derivative.url == storage.url_for(derivative.key)
    assert storage.exists(derivative.key)
    assert Image.open(BytesIO(storage.read(derivative.key))).size == (480, 320)
    assert client.puts[-1]["CacheControl"] == "public, max-age=31536000, immutable"


def test_existing_r2_derivative_skips_regeneration_after_a_new_worker_starts(monkeypatch):
    client = StubS3Client()
    first_worker = provider(client)
    original = first_worker.save(image_bytes(), content_type="image/png", extension=".png")
    first = ensure_storefront_derivative(first_worker, original.key, 480)
    second_worker = provider(client)

    monkeypatch.setattr(
        "app.services.storefront_derivatives.generate_storefront_image",
        lambda *_: pytest.fail("existing R2 derivative must not regenerate"),
    )
    second = ensure_storefront_derivative(second_worker, original.key, 480)

    assert first.key == second.key
    assert second.generated is False


def test_equivalent_requests_use_a_deterministic_versioned_key():
    key = "tara-store/9f6a9f4a67d64d319ee209529bfd1c28.png"

    assert derivative_key_for(key, 480) == derivative_key_for(key, 480)
    assert "/storefront-cache/v1/" in derivative_key_for(key, 480)
    assert derivative_key_for(key, 480) != derivative_key_for(key, 800)
    assert set(STOREFRONT_WIDTHS) == {96, 240, 480, 800, 1440, 2048}


def test_r2_upload_failure_leaves_original_usable(monkeypatch):
    client = StubS3Client()
    storage = provider(client)
    original = storage.save(image_bytes(), content_type="image/png", extension=".png")

    monkeypatch.setattr(storage, "restore", lambda *_args, **_kwargs: (_ for _ in ()).throw(R2StorageError("upload failed")))

    with pytest.raises(R2StorageError, match="upload failed"):
        ensure_storefront_derivative(storage, original.key, 480)
    assert storage.read(original.key) == image_bytes()


def test_endpoint_returns_the_original_when_derivative_generation_or_upload_fails(client, db, media_root, monkeypatch):
    from app.api.v1.endpoints import public_catalog

    storage = LocalStorageProvider(media_root, "/media")
    original = storage.save(image_bytes(), content_type="image/png", extension=".png")
    db.add(MediaAsset(
        original_filename="fallback.png", stored_key=original.key,
        content_type=original.content_type, size_bytes=original.size_bytes,
        url=original.url, storage_provider="local",
    ))
    db.commit()
    monkeypatch.setattr(public_catalog, "get_storage", lambda: storage)
    monkeypatch.setattr(
        public_catalog,
        "ensure_storefront_derivative",
        lambda *_args: (_ for _ in ()).throw(R2StorageError("upload failed")),
    )

    response = client.get(f"/api/v1/storefront-media/{original.key}?width=480", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == original.url
    assert response.headers["cache-control"] == "no-store"


def test_endpoint_redirects_to_the_persisted_r2_derivative(client, db, monkeypatch):
    from app.api.v1.endpoints import public_catalog

    client_stub = StubS3Client()
    storage = provider(client_stub)
    original = storage.save(image_bytes(), content_type="image/png", extension=".png")
    db.add(MediaAsset(
        original_filename="cdn.png", stored_key=original.key,
        content_type=original.content_type, size_bytes=original.size_bytes,
        url=original.url, storage_provider="r2",
    ))
    db.commit()
    monkeypatch.setattr(public_catalog, "get_storage", lambda: storage)

    response = client.get(f"/api/v1/storefront-media/{original.key}?width=480", follow_redirects=False)

    key = derivative_key_for(original.key, 480)
    assert response.status_code == 307
    assert response.headers["location"] == storage.url_for(key)
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert storage.exists(key)


def test_backfill_only_generates_missing_sizes_for_storefront_referenced_media(db):
    client = StubS3Client()
    storage = provider(client)
    referenced = storage.save(image_bytes(), content_type="image/png", extension=".png")
    unused = storage.save(image_bytes(), content_type="image/png", extension=".png")
    db.add_all([
        MediaAsset(original_filename="hero.png", stored_key=referenced.key, content_type="image/png",
                   size_bytes=len(image_bytes()), url=referenced.url, storage_provider="r2"),
        MediaAsset(original_filename="unused.png", stored_key=unused.key, content_type="image/png",
                   size_bytes=len(image_bytes()), url=unused.url, storage_provider="r2"),
        HeroSlide(title="Hero", image_url=referenced.url),
    ])
    db.commit()

    first = backfill_storefront_derivatives(db, storage)
    second = backfill_storefront_derivatives(db, storage)

    assert first.assets == 1
    assert first.generated == len(STOREFRONT_WIDTHS)
    assert first.failed == 0
    assert second.generated == 0
    assert second.skipped == len(STOREFRONT_WIDTHS)
