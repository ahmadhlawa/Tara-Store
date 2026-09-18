"""Storage provider interface plus upload validation shared by every provider."""

from __future__ import annotations

import uuid
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageSequence, UnidentifiedImageError

from app.services.errors import DomainError

@dataclass(frozen=True, slots=True)
class ImageFormatRule:
    content_type: str
    canonical_extension: str
    pillow_formats: frozenset[str]


IMAGE_FORMAT_RULES = {
    ".jpg": ImageFormatRule("image/jpeg", ".jpg", frozenset({"JPEG", "MPO"})),
    ".jpeg": ImageFormatRule("image/jpeg", ".jpg", frozenset({"JPEG", "MPO"})),
    ".png": ImageFormatRule("image/png", ".png", frozenset({"PNG"})),
    ".webp": ImageFormatRule("image/webp", ".webp", frozenset({"WEBP"})),
    ".gif": ImageFormatRule("image/gif", ".gif", frozenset({"GIF"})),
    ".ico": ImageFormatRule("image/x-icon", ".ico", frozenset({"ICO"})),
}

_RULES_BY_CONTENT_TYPE = {
    rule.content_type: rule for rule in IMAGE_FORMAT_RULES.values()
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


def validate_image_upload(
    data: bytes,
    max_bytes: int,
    max_pixels: int = 40_000_000,
    *,
    filename: str | None = None,
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
    content_rule = _RULES_BY_CONTENT_TYPE.get(content_type or "")
    if content_rule is None:
        raise DomainError(
            "نوع الملف غير مدعوم. الأنواع المسموحة: JPEG, PNG, WebP, GIF, ICO.",
            code="unsupported_media_type",
        )
    filename_rule = None
    if filename is not None:
        filename_rule = IMAGE_FORMAT_RULES.get(Path(filename).suffix.lower())
        if filename_rule is None:
            raise DomainError(
                "نوع الملف غير مدعوم. الأنواع المسموحة: JPEG, PNG, WebP, GIF, ICO.",
                code="unsupported_media_type",
            )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                decoded_format = (image.format or "").upper()
                if (
                    decoded_format not in content_rule.pillow_formats
                    or filename_rule is not None
                    and (
                        filename_rule.content_type != content_type
                        or decoded_format not in filename_rule.pillow_formats
                    )
                ):
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
    return content_type, content_rule.canonical_extension


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
    def read(self, key: str) -> bytes:
        """Read an object owned by this provider."""
        ...

    @abstractmethod
    def restore(
        self, key: str, data: bytes, *, content_type: str, cache_control: str | None = None
    ) -> StoredFile:
        """Write `data` at a caller-known stable `key`, keeping its URL.

        Used for repairs and deterministic derived objects. It deliberately does not mint
        a key: callers retain control of stable cache identity.
        """
        ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def url_for(self, key: str) -> str: ...
