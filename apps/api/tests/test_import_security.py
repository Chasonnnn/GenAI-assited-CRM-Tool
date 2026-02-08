import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException, UploadFile, status
from starlette.datastructures import Headers

from app.routers.surrogates_import import preview_csv_enhanced
from app.schemas.auth import UserSession
from app.db.enums import Role
from uuid import uuid4


@pytest.mark.asyncio
async def test_preview_csv_enhanced_dos_vulnerability_fixed():
    """
    Unit test to verify file size validation in preview_csv_enhanced.
    Checks both Content-Length header and actual file size.
    """
    # 1. Test Content-Length header check (fast fail)
    mock_request = MagicMock()
    mock_request.headers = Headers({"content-length": str(11 * 1024 * 1024)})  # 11MB

    mock_upload_file = MagicMock(spec=UploadFile)
    mock_upload_file.filename = "large.csv"
    mock_upload_file.content_type = "text/csv"

    mock_session = UserSession(
        user_id=uuid4(), org_id=uuid4(), role=Role.ADMIN, email="test@test.com", display_name="Test"
    )
    mock_db = MagicMock()

    # Expect 413 due to header
    with pytest.raises(HTTPException) as excinfo:
        await preview_csv_enhanced(
            request=mock_request,
            file=mock_upload_file,
            apply_template=True,
            enable_ai=False,
            session=mock_session,
            db=mock_db,
        )
    assert excinfo.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    # 2. Test actual file size check (slow fail)
    mock_request.headers = Headers({})  # No content-length

    # Mock file methods
    target_size = 11 * 1024 * 1024  # 11MB

    # UploadFile methods are async
    mock_upload_file.seek = AsyncMock()
    mock_upload_file.tell = AsyncMock(return_value=target_size)
    mock_upload_file.read = AsyncMock(
        return_value=b"too large"
    )  # Should not be called if size check fails

    with pytest.raises(HTTPException) as excinfo:
        await preview_csv_enhanced(
            request=mock_request,
            file=mock_upload_file,
            apply_template=True,
            enable_ai=False,
            session=mock_session,
            db=mock_db,
        )
    assert excinfo.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    # Verify read was NOT called (protection against DoS)
    mock_upload_file.read.assert_not_called()
