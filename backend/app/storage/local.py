"""Local filesystem storage — the provider used by this template out of the box."""

from __future__ import annotations

from pathlib import Path

from app.core.enums import StorageProviderName
from app.storage.base import StorageProvider, StoredFile, build_stored_key


class LocalStorageProvider(StorageProvider):
    name = StorageProviderName.LOCAL.value

    def __init__(self, root: Path, base_url: str) -> None:
        self.root = Path(root)
        self.base_url = base_url.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("Refusing to operate outside the media root")
        return path

    def save(
        self, data: bytes, *, content_type: str, extension: str, prefix: str | None = None
    ) -> StoredFile:
        key = build_stored_key(extension, prefix)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredFile(
            key=key,
            url=self.url_for(key),
            content_type=content_type,
            size_bytes=len(data),
        )

    def exists(self, key: str) -> bool:
        if not key:
            return False
        try:
            path = self._path(key)
        except ValueError:
            # A key pointing outside the media root is not ours, so it is not present.
            return False
        return path.is_file()

    def restore(self, key: str, data: bytes, *, content_type: str) -> StoredFile:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredFile(
            key=key,
            url=self.url_for(key),
            content_type=content_type,
            size_bytes=len(data),
        )

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def url_for(self, key: str) -> str:
        return f"{self.base_url}/{key}"
