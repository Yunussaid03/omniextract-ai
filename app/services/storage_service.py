import os
import re
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

# Supported Magic Byte Signatures
MAGIC_BYTES: dict[str, bytes] = {
    "application/pdf": b"%PDF-",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}


def detect_content_type(header: bytes) -> str | None:
    """Detects content type by matching initial file bytes against known signatures."""
    for mime_type, signature in MAGIC_BYTES.items():
        if header.startswith(signature):
            return mime_type
    return None


def sanitize_filename(filename: str) -> str:
    """Sanitizes user-provided filename to remove dangerous path traversal characters."""
    base_name = os.path.basename(filename)
    sanitized = re.sub(r"[^\w\.-]", "_", base_name)
    return sanitized or "document"


async def save_uploaded_file(
    file: UploadFile,
) -> tuple[str, str, int]:
    """Validates file size & header magic bytes, saves file securely to disk, and returns storage metadata.

    Returns:
        tuple[storage_path, content_type, file_size]
    """
    if not file.filename or not file.filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty",
        )

    # 1. Read initial chunk for magic bytes validation
    header_chunk = await file.read(512)
    if not header_chunk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    content_type = detect_content_type(header_chunk)
    if not content_type:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported document format. Allowed types: PDF, PNG, JPEG.",
        )

    # 2. Reset cursor and stream to disk while enforcing max size limit
    await file.seek(0)
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)

    unique_id = uuid.uuid4()
    safe_original_name = sanitize_filename(file.filename)
    storage_filename = f"{unique_id}_{safe_original_name}"
    storage_path = os.path.join(settings.STORAGE_DIR, storage_filename)

    file_size = 0
    chunk_size = 64 * 1024  # 64 KB chunks

    try:
        with open(storage_path, "wb") as out_file:
            while chunk := await file.read(chunk_size):
                file_size += len(chunk)
                if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
                    out_file.close()
                    delete_stored_file(storage_path)
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"File size exceeds maximum allowed limit of "
                            f"{settings.MAX_UPLOAD_SIZE_BYTES} bytes"
                        ),
                    )
                out_file.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        delete_stored_file(storage_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save document file: {exc}",
        ) from exc

    return storage_path, content_type, file_size


def delete_stored_file(file_path: str) -> None:
    """Safely removes a stored file from disk if present."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass
