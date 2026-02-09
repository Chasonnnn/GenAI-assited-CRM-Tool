import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, Request, UploadFile
from starlette.datastructures import Headers
from uuid import UUID

from app.routers.attachments import upload_attachment
from app.routers.auth import upload_avatar
from app.services import attachment_service
from app.schemas.auth import UserSession
from app.db.enums import Role


# Mock dependencies
@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_session():
    return UserSession(
        user_id="00000000-0000-0000-0000-000000000001",
        org_id="00000000-0000-0000-0000-000000000002",
        role=Role.ADMIN,
        token_hash="hash",
        mfa_verified=True,
        mfa_required=False,
        email="test@example.com",
        display_name="Test User",
    )


@pytest.fixture
def mock_surrogate():
    surrogate = MagicMock()
    surrogate.id = UUID("00000000-0000-0000-0000-000000000003")
    surrogate.organization_id = UUID("00000000-0000-0000-0000-000000000002")
    return surrogate


@pytest.mark.asyncio
async def test_upload_attachment_content_length_too_large(mock_db, mock_session):
    request = MagicMock(spec=Request)
    request.headers = Headers(
        {"content-length": str(attachment_service.MAX_FILE_SIZE_BYTES + 2048)}
    )
    file = MagicMock(spec=UploadFile)

    with pytest.raises(HTTPException) as exc:
        await upload_attachment(
            surrogate_id=UUID("00000000-0000-0000-0000-000000000003"),
            request=request,
            file=file,
            db=mock_db,
            session=mock_session,
            _="csrf_token",
        )
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_upload_attachment_actual_size_too_large(mock_db, mock_session, mock_surrogate):
    request = MagicMock(spec=Request)
    request.headers = Headers({})

    file = MagicMock(spec=UploadFile)
    file.filename = "large.pdf"
    file.content_type = "application/pdf"
    file.file = MagicMock()

    # Mock run_in_threadpool for seek/tell
    with patch("app.routers.attachments.run_in_threadpool", new_callable=AsyncMock) as mock_run:
        # First call: seek(0, 2) returns size
        # Second call: seek(0) returns 0
        mock_run.side_effect = [attachment_service.MAX_FILE_SIZE_BYTES + 100, 0]

        # Mock dependencies
        with patch(
            "app.routers.attachments._get_surrogate_with_access", return_value=mock_surrogate
        ):
            # Service raises ValueError for size
            with patch(
                "app.services.attachment_service.upload_attachment",
                side_effect=ValueError("File size exceeds limit"),
            ):
                with pytest.raises(HTTPException) as exc:
                    await upload_attachment(
                        surrogate_id=mock_surrogate.id,
                        request=request,
                        file=file,
                        db=mock_db,
                        session=mock_session,
                        _="csrf_token",
                    )
                assert exc.value.status_code == 400
                assert "File size exceeds limit" in exc.value.detail

        # Verify seek called
        assert mock_run.call_count == 2
        mock_run.assert_any_call(file.file.seek, 0, 2)
        mock_run.assert_any_call(file.file.seek, 0)


@pytest.mark.asyncio
async def test_upload_avatar_content_length_too_large(mock_db, mock_session):
    request = MagicMock(spec=Request)
    # AVATAR_MAX_SIZE is 2MB
    request.headers = Headers({"content-length": str(2 * 1024 * 1024 + 2048)})
    file = MagicMock(spec=UploadFile)

    with pytest.raises(HTTPException) as exc:
        await upload_avatar(
            request=request,
            background_tasks=MagicMock(),
            file=file,
            session=mock_session,
            db=mock_db,
        )
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_upload_avatar_actual_size_too_large(mock_db, mock_session):
    request = MagicMock(spec=Request)
    request.headers = Headers({})

    file = MagicMock(spec=UploadFile)
    file.content_type = "image/png"
    file.file = MagicMock()

    with patch("app.routers.auth.run_in_threadpool", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = [2 * 1024 * 1024 + 100, 0]

        with pytest.raises(HTTPException) as exc:
            await upload_avatar(
                request=request,
                background_tasks=MagicMock(),
                file=file,
                session=mock_session,
                db=mock_db,
            )
        assert exc.value.status_code == 400
        assert "File too large" in exc.value.detail
