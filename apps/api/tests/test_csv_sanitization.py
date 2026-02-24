import pytest
from unittest.mock import MagicMock, patch
from io import BytesIO
import uuid
from app.services import attachment_service

# Test the sanitization logic itself (Unit Test)
def test_sanitize_csv_implementation():
    if not hasattr(attachment_service, "sanitize_csv"):
        pytest.skip("sanitize_csv not implemented yet")

    # Malicious content
    content = b"id,data\n1,=cmd|' /C calc'!A0"
    file = BytesIO(content)

    sanitized = attachment_service.sanitize_csv(file, "text/csv")
    result = sanitized.read()

    # Verify escaping
    assert b"'=cmd|' /C calc'!A0" in result

    # Verify safe content
    assert b"id,data" in result

# Test integration into upload_attachment (Unit Test with Mocks)
@patch("app.services.attachment_service.store_file")
@patch("app.services.attachment_service.audit_service")
@patch("app.services.attachment_service.job_service")
@patch("app.services.attachment_service.validate_file")
@patch("app.services.attachment_service.strip_exif_data")
def test_upload_attachment_flow_sanitization(
    mock_strip, mock_validate, mock_job, mock_audit, mock_store
):
    # Setup mocks
    mock_validate.return_value = (True, None)
    mock_strip.side_effect = lambda f, t: f # Return original file

    db = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    surrogate_id = uuid.uuid4()

    payload = b"=cmd|' /C calc'!A0"
    content = b"id,data\n1," + payload
    file = BytesIO(content)

    # Call upload
    attachment_service.upload_attachment(
        db=db,
        org_id=org_id,
        user_id=user_id,
        filename="test.csv",
        content_type="text/csv",
        file=file,
        file_size=len(content),
        surrogate_id=surrogate_id,
    )

    # Verify store_file received sanitized content
    mock_store.assert_called_once()
    args, _ = mock_store.call_args
    _, stored_file, _ = args
    stored_content = stored_file.read()

    # Assert it contains the escaped payload
    assert b"'=cmd|' /C calc'!A0" in stored_content
