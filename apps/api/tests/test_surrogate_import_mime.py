import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import UploadFile, HTTPException
from app.routers.surrogates_import import preview_csv_enhanced

@pytest.mark.asyncio
async def test_preview_csv_rejects_invalid_mime_unit():
    # Mock dependencies
    mock_request = MagicMock()
    mock_session = MagicMock()
    mock_db = MagicMock()

    # Mock file with invalid MIME
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "test.csv"
    mock_file.content_type = "image/png"

    # We expect HTTPException
    with pytest.raises(HTTPException) as excinfo:
        await preview_csv_enhanced(
            request=mock_request,
            file=mock_file,
            session=mock_session,
            db=mock_db
        )

    assert excinfo.value.status_code == 400
    assert "Content type 'image/png' does not match extension '.csv'" in excinfo.value.detail

@pytest.mark.asyncio
async def test_preview_tsv_rejects_invalid_mime_unit():
    # Mock dependencies
    mock_request = MagicMock()
    mock_session = MagicMock()
    mock_db = MagicMock()

    # Mock file with invalid MIME
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "test.tsv"
    mock_file.content_type = "image/png"

    # We expect HTTPException
    with pytest.raises(HTTPException) as excinfo:
        await preview_csv_enhanced(
            request=mock_request,
            file=mock_file,
            session=mock_session,
            db=mock_db
        )

    assert excinfo.value.status_code == 400
    assert "Content type 'image/png' is not valid for '.tsv'" in excinfo.value.detail
