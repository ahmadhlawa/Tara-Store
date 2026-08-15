"""Storage provider selection."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, settings
from app.core.enums import StorageProviderName
from app.storage.base import StorageProvider, StoredFile, validate_image_upload
from app.storage.local import LocalStorageProvider
from app.storage.r2 import R2StorageProvider

__all__ = [
    "LocalStorageProvider",
    "R2StorageProvider",
    "StorageProvider",
    "StoredFile",
    "get_storage",
    "build_storage",
    "validate_image_upload",
]


def build_storage(config: Settings) -> StorageProvider:
    if config.STORAGE_PROVIDER == StorageProviderName.R2.value:
        return R2StorageProvider(
            endpoint_url=config.R2_ENDPOINT_URL,
            access_key_id=config.R2_ACCESS_KEY_ID,
            secret_access_key=config.R2_SECRET_ACCESS_KEY,
            bucket_name=config.R2_BUCKET_NAME,
            public_base_url=config.R2_PUBLIC_BASE_URL,
            region_name=config.R2_REGION,
            object_prefix=config.R2_OBJECT_PREFIX,
        )
    return LocalStorageProvider(config.media_root, config.LOCAL_MEDIA_BASE_URL)


@lru_cache
def get_storage() -> StorageProvider:
    return build_storage(settings)
