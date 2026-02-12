import pytest
from io import BytesIO
import uuid
from fastapi import UploadFile, HTTPException
from unittest.mock import MagicMock
from app.utils.file_upload import get_upload_file_size
from app.services import attachment_service
from app.routers.attachments import upload_attachment


@pytest.mark.asyncio
async def test_get_upload_file_size():
    content = b"test content"
    file = UploadFile(filename="test.txt", file=BytesIO(content))

    size = await get_upload_file_size(file)
    assert size == len(content)

    # Verify pointer is reset
    assert file.file.tell() == 0
    await file.close()


@pytest.mark.asyncio
async def test_get_upload_file_size_empty():
    content = b""
    file = UploadFile(filename="empty.txt", file=BytesIO(content))

    size = await get_upload_file_size(file)
    assert size == 0
    await file.close()


@pytest.mark.asyncio
async def test_upload_attachment_router_logic(monkeypatch):
    """Verify that uploading a file larger than MAX_FILE_SIZE_BYTES returns 413."""
    # Mock MAX_FILE_SIZE_BYTES to be very small (5 bytes)
    monkeypatch.setattr(attachment_service, "MAX_FILE_SIZE_BYTES", 5)

    # Mock _get_surrogate_with_access
    mock_surrogate = MagicMock()
    mock_surrogate.organization_id = uuid.uuid4()
    mock_surrogate.id = uuid.uuid4()

    # Mock the helper function in the router module
    import app.routers.attachments as attachments_module

    monkeypatch.setattr(
        attachments_module, "_get_surrogate_with_access", lambda *args, **kwargs: mock_surrogate
    )

    # Mock file with content > 5 bytes
    content = b"too large content"
    file = UploadFile(filename="large.txt", file=BytesIO(content))

    # Mock session
    mock_session = MagicMock()
    mock_session.user_id = uuid.uuid4()
    mock_session.org_id = uuid.uuid4()

    # Mock db
    mock_db = MagicMock()

    # Call the function directly
    with pytest.raises(HTTPException) as excinfo:
        await upload_attachment(
            surrogate_id=uuid.uuid4(), file=file, db=mock_db, session=mock_session, _=None
        )

    assert excinfo.value.status_code == 413
    assert "File size exceeds" in excinfo.value.detail
