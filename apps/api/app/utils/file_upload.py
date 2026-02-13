"""Helpers for safe upload size checks."""

from __future__ import annotations

from os import SEEK_END

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool


MULTIPART_OVERHEAD_BYTES = 64 * 1024


def content_length_exceeds_limit(
    content_length_header: str | None,
    *,
    max_size_bytes: int,
    overhead_bytes: int = MULTIPART_OVERHEAD_BYTES,
) -> bool:
    """Return True when Content-Length clearly exceeds the allowed file size."""
    if not content_length_header:
        return False
    try:
        content_length = int(content_length_header)
    except (TypeError, ValueError):
        return False
    return content_length > (max_size_bytes + overhead_bytes)


async def get_upload_file_size(file: UploadFile) -> int:
    """Read size from the underlying file object without loading into memory."""

    def _get_size() -> int:
        stream = file.file
        original_pos = stream.tell()
        try:
            stream.seek(0, SEEK_END)
            return stream.tell()
        finally:
            stream.seek(original_pos)

    return await run_in_threadpool(_get_size)
