"""Media uploads. Files go to the configured storage provider; the DB keeps metadata."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.crud import get_or_404
from app.api.deps import CurrentAdmin, DbSession, PageParams
from app.core.config import settings
from app.models import MediaAsset
from app.schemas.common import MessageResponse, Page
from app.schemas.media import MAX_MEDIA_FILENAME_LENGTH, MediaAssetOut, MediaAssetRenameIn
from app.services import audit as audit_service
from app.services import catalog as catalog_service
from app.services.errors import ConflictError
from app.storage import get_storage, validate_image_upload

router = APIRouter(prefix="/admin", tags=["admin-media"])

MAX_FILENAME_LENGTH = 300

DUPLICATE_FILENAME_MESSAGE = "يوجد ملف بهذا الاسم بالفعل."


def _asset_id_named(db, filename: str) -> int | None:
    return db.scalar(select(MediaAsset.id).where(MediaAsset.original_filename == filename))


def filename_is_taken(db, filename: str) -> bool:
    """The pre-check. Advisory only — the unique index is what actually decides."""
    return _asset_id_named(db, filename) is not None


def filename_is_taken_by_other(db, filename: str, asset_id: int) -> bool:
    return db.scalar(
        select(MediaAsset.id).where(
            MediaAsset.original_filename == filename, MediaAsset.id != asset_id
        )
    ) is not None


@router.get("/media", response_model=Page[MediaAssetOut])
def list_media(
    db: DbSession,
    admin: CurrentAdmin,
    pagination: PageParams,
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> Page[MediaAssetOut]:
    stmt = select(MediaAsset)
    if q:
        stmt = stmt.where(MediaAsset.original_filename.like(f"%{q}%"))
    stmt = stmt.order_by(MediaAsset.id.desc())
    rows, total = catalog_service.paginate(
        db, stmt, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.build(
        [MediaAssetOut.model_validate(row) for row in rows],
        total,
        pagination.page,
        pagination.page_size,
    )


@router.post("/media", response_model=MediaAssetOut, status_code=status.HTTP_201_CREATED)
async def upload_media(
    db: DbSession,
    admin: CurrentAdmin,
    file: UploadFile = File(...),
) -> MediaAsset:
    data = await file.read()
    # The declared content type and the file name are both attacker-controlled;
    # the real type comes from the bytes.
    content_type, extension = validate_image_upload(
        data, settings.MAX_UPLOAD_SIZE_BYTES, settings.MAX_IMAGE_PIXELS
    )

    # The catalog importer resolves a product image by `original_filename`, so two rows
    # sharing one name make that lookup ambiguous. Refuse the second upload rather than
    # create the ambiguity — and never overwrite the first one. Checked before the bytes
    # are written so the ordinary rejection leaves nothing behind in storage; the unique
    # index on the column is what makes it true under concurrency (see below).
    original_filename = (file.filename or "upload")[:MAX_MEDIA_FILENAME_LENGTH]
    if filename_is_taken(db, original_filename):
        raise ConflictError(DUPLICATE_FILENAME_MESSAGE, code="duplicate_filename")

    storage = get_storage()
    stored = storage.save(data, content_type=content_type, extension=extension)
    asset = MediaAsset(
        original_filename=original_filename,
        stored_key=stored.key,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        url=stored.url,
        storage_provider=storage.name,
        uploaded_by_id=admin.id,
    )
    db.add(asset)
    try:
        db.flush()
        audit_service.record(
            db,
            admin=admin,
            action="media.uploaded",
            entity_type="media_asset",
            entity_id=asset.id,
            meta={"content_type": content_type, "size_bytes": asset.size_bytes},
        )
        db.commit()
    except IntegrityError:
        # The pre-check above is for the message, not for correctness: a second request
        # can commit the same name between that SELECT and this INSERT. The unique index
        # is what actually decides, so the loser of that race is handled here.
        db.rollback()
        # Only this request's object — the winner's bytes are a different key and stay.
        storage.delete(stored.key)
        if _asset_id_named(db, original_filename) is None:
            # Some other constraint failed; it is a server fault, not a duplicate name.
            raise
        raise ConflictError(DUPLICATE_FILENAME_MESSAGE, code="duplicate_filename") from None
    db.refresh(asset)
    return asset


@router.patch("/media/{asset_id}", response_model=MediaAssetOut)
def rename_media(
    asset_id: int, payload: MediaAssetRenameIn, db: DbSession, admin: CurrentAdmin
) -> MediaAsset:
    asset = get_or_404(db, MediaAsset, asset_id)
    original_filename = payload.original_filename
    if filename_is_taken_by_other(db, original_filename, asset_id):
        raise ConflictError(DUPLICATE_FILENAME_MESSAGE, code="duplicate_filename")

    previous_filename = asset.original_filename
    asset.original_filename = original_filename
    try:
        db.flush()
        audit_service.record(
            db,
            admin=admin,
            action="media.renamed",
            entity_type="media_asset",
            entity_id=asset.id,
            meta={"original_filename": original_filename, "previous_filename": previous_filename},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        if not filename_is_taken_by_other(db, original_filename, asset_id):
            raise
        raise ConflictError(DUPLICATE_FILENAME_MESSAGE, code="duplicate_filename") from None
    db.refresh(asset)
    return asset


@router.delete("/media/{asset_id}", response_model=MessageResponse)
def delete_media(asset_id: int, db: DbSession, admin: CurrentAdmin):
    asset = get_or_404(db, MediaAsset, asset_id, "الملف غير موجود.")

    # Delete the stored object only when the running provider is the one that wrote it.
    # After a switch from local to R2 (or back) the old keys belong to the other
    # provider's namespace; asking this one to delete them would either do nothing
    # useful or, on R2, be refused as an out-of-prefix key. The metadata row goes
    # either way — the orphan is then a file, not a broken record.
    storage = get_storage()
    object_deleted = asset.storage_provider == storage.name
    if object_deleted:
        storage.delete(asset.stored_key)

    audit_service.record(
        db,
        admin=admin,
        action="media.deleted",
        entity_type="media_asset",
        entity_id=asset.id,
        meta={
            "stored_key": asset.stored_key,
            "storage_provider": asset.storage_provider,
            "object_deleted": object_deleted,
        },
    )
    db.delete(asset)
    db.commit()
    return MessageResponse(message="تم حذف الملف.")
