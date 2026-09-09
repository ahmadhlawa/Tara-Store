"""Storage provider interface plus upload validation shared by every provider."""

from __future__ import annotations

import uuid
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageSequence, UnidentifiedImageError

from app.services.errors import DomainError

# (mime type, canonical extension, magic prefix checker)
ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}


def sniff_content_type(data: bytes) -> str | None:
    """Identify the file from its bytes. The client-declared type is not trusted."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"\x00\x00\x01\x00"):
        return "image/x-icon"
    return None


_PIL_FORMATS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
    "image/gif": "GIF",
    "image/x-icon": "ICO",
    "image/vnd.microsoft.icon": "ICO",
}


def validate_image_upload(
    data: bytes, max_bytes: int, max_pixels: int = 40_000_000
) -> tuple[str, str]:
    """Return `(content_type, extension)` or raise a DomainError."""
    if not data:
        raise DomainError("الملف فارغ.", code="empty_file")
    if len(data) > max_bytes:
        limit_mb = round(max_bytes / (1024 * 1024), 1)
        raise DomainError(
            f"حجم الملف يتجاوز الحد المسموح ({limit_mb} ميغابايت).", code="file_too_large"
        )
    content_type = sniff_content_type(data)
    if content_type is None or content_type not in ALLOWED_IMAGE_TYPES:
        raise DomainError(
            "نوع الملف غير مدعوم. الأنواع المسموحة: JPEG, PNG, WebP, GIF, ICO.",
            code="unsupported_media_type",
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format != _PIL_FORMATS[content_type]:
                    raise DomainError(
                        "تنسيق الصورة الفعلي لا يطابق ترويسة الملف.",
                        code="image_format_mismatch",
                    )
                width, height = image.size
                if width <= 0 or height <= 0:
                    raise DomainError("أبعاد الصورة غير صالحة.", code="invalid_image_dimensions")
                if width * height > max_pixels:
                    raise DomainError("أبعاد الصورة تتجاوز الحد المسموح.", code="image_too_many_pixels")
                image.verify()
            with Image.open(BytesIO(data)) as decoded:
                for frame in ImageSequence.Iterator(decoded):
                    frame.load()
    except DomainError:
        raise
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise DomainError("أبعاد الصورة تتجاوز الحد المسموح.", code="image_too_many_pixels") from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise DomainError("ملف الصورة تالف أو غير صالح.", code="invalid_image") from None
    return content_type, ALLOWED_IMAGE_TYPES[content_type]


def normalize_prefix(prefix: str | None) -> str:
    """Return a safe, trailing-slashed object prefix, or `""`.

    A prefix decides which objects a delete is allowed to touch, so it must never be
    absolute and never contain a traversal segment.
    """
    if not prefix:
        return ""
    cleaned = prefix.strip().strip("/")
    if not cleaned:
        return ""
    segments = [segment for segment in cleaned.split("/") if segment]
    if any(segment in (".", "..") for segment in segments):
        raise ValueError(f"Refusing to use an object prefix containing a traversal: {prefix!r}")
    return "/".join(segments) + "/"


def build_stored_key(extension: str, prefix: str | None = None) -> str:
    """Collision-resistant and traversal-proof: the caller's name is never reused."""
    return f"{normalize_prefix(prefix)}{uuid.uuid4().hex}{extension}"


@dataclass(slots=True)
class StoredFile:
    key: str
    url: str
    content_type: str
    size_bytes: int


class StorageProvider(ABC):
    name: str

    @abstractmethod
    def save(
        self, data: bytes, *, content_type: str, extension: str, prefix: str | None = None
    ) -> StoredFile:
        """Store `data` and return its metadata.

        `prefix` groups an upload into a namespace inside the provider — used by the
        preview importer so its objects can later be found and removed as a set. It is
        additional to any provider-wide prefix.
        """
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """True when an object this provider owns is stored under `key`.

        A `MediaAsset` row is only a claim that bytes were written once. The object can
        disappear underneath it — a cleared upload directory, a bucket lifecycle rule, a
        restored machine — and nothing in the database notices. Callers that must trust
        the object, not just the row, ask here.

        Never raises for a missing or foreign key: a key this provider does not own is
        simply not present as far as the caller is concerned.
        """
        ...

    @abstractmethod
    def restore(self, key: str, data: bytes, *, content_type: str) -> StoredFile:
        """Re-write `data` at an existing `key`, keeping its URL.

        Only for repairing an object whose key is already recorded. It deliberately does
        not mint a key: reusing the recorded one is what lets a caller repair storage
        without touching the database row that points at it.
        """
        ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def url_for(self, key: str) -> str: ...
