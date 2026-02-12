import os
from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool


async def get_upload_file_size(file: UploadFile) -> int:
    """
    Get the size of an UploadFile safely.

    This function attempts to determine the file size without reading the entire content
    into memory. It uses seek/tell on the underlying file object.

    Args:
        file: The UploadFile object.

    Returns:
        The size of the file in bytes, or 0 if size cannot be determined.
    """
    try:
        # Try to get size from file object using seek/tell
        if hasattr(file.file, "seek") and hasattr(file.file, "tell"):
            await run_in_threadpool(file.file.seek, 0, os.SEEK_END)
            size = await run_in_threadpool(file.file.tell)
            await run_in_threadpool(file.file.seek, 0)
            return size
    except Exception:
        pass

    return 0
