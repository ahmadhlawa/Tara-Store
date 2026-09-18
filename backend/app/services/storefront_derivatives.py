"""Persistent, deterministic WebP derivatives for public storefront media."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from threading import Lock, Semaphore
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, HeroSlide, MediaAsset, Product, ProductImage, StoreSettings
from app.services.media_thumbnails import generate_storefront_image
from app.storage.base import StorageProvider

STOREFRONT_WIDTHS = (96, 240, 480, 800, 1440, 2048)
DERIVATIVE_VERSION = "v1"
_TRANSFORM_SIGNATURE = "webp-q85-m4"
_locks = [Lock() for _ in range(16)]
_encoders = Semaphore(2)
_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StorefrontDerivative:
    key: str
    url: str
    generated: bool


@dataclass(slots=True)
class BackfillReport:
    assets: int = 0
    generated: int = 0
    skipped: int = 0
    failed: int = 0


def derivative_key_for(source_key: str, width: int) -> str:
    """Return a stable key below the source object's provider-owned namespace."""
    path = PurePosixPath(source_key)
    if not source_key or path.is_absolute() or "\\" in source_key or any(part in {".", ".."} for part in path.parts):
        raise ValueError("Invalid source media key")
    if width not in STOREFRONT_WIDTHS:
        raise ValueError("Unsupported storefront image width")
    digest = sha256(f"{DERIVATIVE_VERSION}:{_TRANSFORM_SIGNATURE}:{source_key}:{width}".encode()).hexdigest()
    parent = "" if str(path.parent) == "." else f"{path.parent}/"
    return f"{parent}storefront-cache/{DERIVATIVE_VERSION}/{digest}-{width}.webp"


def ensure_storefront_derivative(storage: StorageProvider, source_key: str, width: int) -> StorefrontDerivative:
    """Reuse a shared object or encode and persist one at its deterministic key."""
    derivative_key = derivative_key_for(source_key, width)
    if storage.exists(derivative_key):
        return StorefrontDerivative(derivative_key, storage.url_for(derivative_key), generated=False)

    lock = _locks[int(sha256(derivative_key.encode()).hexdigest()[:2], 16) % len(_locks)]
    with lock:
        if storage.exists(derivative_key):
            return StorefrontDerivative(derivative_key, storage.url_for(derivative_key), generated=False)
        with _encoders:
            data = generate_storefront_image(storage.read(source_key), width)
        stored = storage.restore(
            derivative_key,
            data,
            content_type="image/webp",
            cache_control="public, max-age=31536000, immutable",
        )
    return StorefrontDerivative(stored.key, stored.url, generated=True)


def storefront_media_assets(db: Session, storage: StorageProvider) -> list[MediaAsset]:
    """Return registered uploads presently referenced by public storefront content."""
    urls = set()
    for statement in (
        select(Category.image_url).where(Category.is_active.is_(True)),
        select(Category.banner_image_url).where(Category.is_active.is_(True)),
        select(HeroSlide.image_url).where(HeroSlide.is_active.is_(True)),
        select(ProductImage.url).join(Product).where(Product.is_active.is_(True)),
        select(StoreSettings.logo_url),
        select(StoreSettings.favicon_url),
    ):
        urls.update(url for (url,) in db.execute(statement) if url)
    if not urls:
        return []
    return list(db.execute(
        select(MediaAsset)
        .where(MediaAsset.storage_provider == storage.name, MediaAsset.url.in_(urls))
        .order_by(MediaAsset.id)
    ).scalars())


def backfill_storefront_derivatives(db: Session, storage: StorageProvider, *, write: bool = True) -> BackfillReport:
    """Fill only missing storefront widths for media currently referenced by the storefront."""
    report = BackfillReport()
    for asset in storefront_media_assets(db, storage):
        report.assets += 1
        try:
            for width in STOREFRONT_WIDTHS:
                key = derivative_key_for(asset.stored_key, width)
                if storage.exists(key):
                    report.skipped += 1
                elif write:
                    ensure_storefront_derivative(storage, asset.stored_key, width)
                    report.generated += 1
                else:
                    report.generated += 1
        except Exception as exc:  # The caller reports a bounded count; no batch-wide failure.
            report.failed += 1
            _logger.warning("Storefront derivative backfill failed for asset %s (%s)", asset.id, type(exc).__name__)
    return report
