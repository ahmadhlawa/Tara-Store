"""Cloudflare R2 storage, over its S3-compatible API.

Nothing outside this module knows where bytes live. Selecting R2 is a configuration
change — `STORAGE_PROVIDER=r2` plus the `R2_*` variables — and the local provider stays
fully functional beside it.

Two safety properties are enforced here and are the reason this file exists at all:

* **Every object this application writes lives under `R2_OBJECT_PREFIX`.** The prefix is
  applied on write and re-checked on delete.
* **`delete()` and `restore()` refuse any key outside that prefix, and `exists()` reports
  such a key as absent without issuing a request.** A bucket may hold objects this
  application did not create — a backup, another tool's output, a previous instance —
  and a media record whose key points outside our namespace is a bug or tampering, not a
  licence to delete someone else's file.

No bucket is ever created and no account API is called: this module speaks only
`put_object`, `head_object` and `delete_object` against a bucket that already exists.

`boto3` is imported lazily so a local-storage instance never needs the dependency
installed. Install it with the `r2` extra.
"""

from __future__ import annotations

from typing import Any

from app.core.enums import StorageProviderName
from app.storage.base import StorageProvider, StoredFile, build_stored_key, normalize_prefix


class R2NotConfiguredError(RuntimeError):
    pass


class R2StorageError(RuntimeError):
    """An R2 operation failed. Never carries a credential."""


class R2StorageProvider(StorageProvider):
    name = StorageProviderName.R2.value

    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        public_base_url: str,
        object_prefix: str = "",
        client: Any | None = None,
    ) -> None:
        missing = [
            field
            for field, value in (
                ("R2_ACCOUNT_ID", account_id),
                ("R2_ACCESS_KEY_ID", access_key_id),
                ("R2_SECRET_ACCESS_KEY", secret_access_key),
                ("R2_BUCKET_NAME", bucket_name),
                ("R2_PUBLIC_BASE_URL", public_base_url),
            )
            if not value
        ]
        if missing:
            raise R2NotConfiguredError(
                "R2 storage is selected but not configured. Missing: " + ", ".join(missing)
            )
        self.account_id = account_id
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.bucket_name = bucket_name
        self.public_base_url = public_base_url.rstrip("/")
        self.object_prefix = normalize_prefix(object_prefix)
        self._client = client

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"

    @property
    def client(self) -> Any:
        """The S3 client. Built once, lazily, so importing this module is free."""
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:  # pragma: no cover - depends on the environment
                raise R2NotConfiguredError(
                    "STORAGE_PROVIDER=r2 needs boto3. Install it with: pip install -e '.[r2]'"
                ) from exc
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name="auto",
                config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
            )
        return self._client

    # ── keys ─────────────────────────────────────────────────────────────────
    def build_key(self, extension: str, prefix: str | None = None) -> str:
        """`<object prefix><caller prefix><random>.<ext>` — collision-resistant."""
        combined = f"{self.object_prefix}{normalize_prefix(prefix)}"
        return build_stored_key(extension, combined)

    def owns_key(self, key: str) -> bool:
        """True when `key` is inside this instance's configured prefix."""
        if not key or key.startswith("/") or ".." in key.split("/"):
            return False
        return key.startswith(self.object_prefix)

    # ── operations ───────────────────────────────────────────────────────────
    def save(
        self, data: bytes, *, content_type: str, extension: str, prefix: str | None = None
    ) -> StoredFile:
        key = self.build_key(extension, prefix)
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
                # Media is public read-only content served straight from the public base
                # URL; a long cache is safe because keys are immutable and random.
                CacheControl="public, max-age=31536000, immutable",
            )
        except Exception as exc:  # noqa: BLE001 - re-raised without the credential
            raise R2StorageError(f"R2 upload failed for {key!r}: {type(exc).__name__}") from exc
        return StoredFile(
            key=key,
            url=self.url_for(key),
            content_type=content_type,
            size_bytes=len(data),
        )

    def exists(self, key: str) -> bool:
        # A key outside the prefix is reported absent without a request: this application
        # does not probe objects it did not write.
        if not self.owns_key(key):
            return False
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
        except Exception:  # noqa: BLE001 - any failure means "not readable as ours"
            return False
        return True

    def restore(self, key: str, data: bytes, *, content_type: str) -> StoredFile:
        if not self.owns_key(key):
            raise R2StorageError(
                f"Refusing to write {key!r}: it is outside the configured prefix "
                f"{self.object_prefix!r}."
            )
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
                CacheControl="public, max-age=31536000, immutable",
            )
        except Exception as exc:  # noqa: BLE001 - re-raised without the credential
            raise R2StorageError(f"R2 repair failed for {key!r}: {type(exc).__name__}") from exc
        return StoredFile(
            key=key,
            url=self.url_for(key),
            content_type=content_type,
            size_bytes=len(data),
        )

    def delete(self, key: str) -> None:
        if not self.owns_key(key):
            raise R2StorageError(
                f"Refusing to delete {key!r}: it is outside the configured prefix "
                f"{self.object_prefix!r}."
            )
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
        except Exception as exc:  # noqa: BLE001 - re-raised without the credential
            raise R2StorageError(f"R2 delete failed for {key!r}: {type(exc).__name__}") from exc

    def url_for(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"
