"""Small, persistent previews for the admin media library."""

from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath

from PIL import Image, ImageOps

from app.storage.base import StorageProvider, StoredFile

THUMBNAIL_MAX_SIZE = 400
THUMBNAIL_QUALITY = 80


def thumbnail_key_for(original_key: str) -> str:
    path = PurePosixPath(original_key)
    if path.is_absolute() or not path.name or any(part in {".", ".."} for part in path.parts):
        raise ValueError("Invalid media storage key")
    return str(path.parent / "thumbnails" / f"{path.stem}.webp")


def generate_thumbnail(data: bytes) -> bytes:
    with Image.open(BytesIO(data)) as source:
        source.seek(0)
        image = ImageOps.exif_transpose(source).copy()
    image.thumbnail((THUMBNAIL_MAX_SIZE, THUMBNAIL_MAX_SIZE), Image.Resampling.LANCZOS)
    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGBA" if "transparency" in image.info else "RGB")
    output = BytesIO()
    image.save(output, format="WEBP", quality=THUMBNAIL_QUALITY, method=4)
    return output.getvalue()


def store_thumbnail(storage: StorageProvider, original_key: str, data: bytes) -> StoredFile:
    return storage.restore(
        thumbnail_key_for(original_key), generate_thumbnail(data), content_type="image/webp"
    )
