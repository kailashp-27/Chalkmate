from pathlib import Path

import httpx
from fastapi import HTTPException

from chalkmate.config import get_settings
from chalkmate.documents import inspect_document

MAX_FILE_BYTES = 10 * 1024 * 1024
TYPES = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
}


def validate_file(filename: str, content: bytes) -> str:
    if not content or len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "Choose a nonempty file of 10 MB or smaller")
    kind = TYPES.get(Path(filename).suffix.lower())
    if not kind or not content.startswith(kind[1]):
        raise HTTPException(415, "Choose a PDF, JPEG, or PNG with a matching file extension")
    try:
        inspect_document(content, kind[0])
    except Exception as exc:
        raise HTTPException(
            415, "Use a valid unencrypted PDF (1–30 pages), JPEG or PNG (up to 25 megapixels)"
        ) from exc
    return kind[0]


def storage_request(method: str, path: str, **kwargs) -> httpx.Response:
    settings = get_settings()
    try:
        response = httpx.request(
            method,
            f"{settings.supabase_url}/storage/v1/{path}",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
                **kwargs.pop("headers", {}),
            },
            timeout=30,
            **kwargs,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Private file storage is temporarily unavailable") from exc
    if response.is_error:
        raise HTTPException(503, "Private file storage is temporarily unavailable")
    return response
