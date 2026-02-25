import uuid
import io
from unittest.mock import MagicMock, patch

from app.services import attachment_service


def test_csv_upload_sanitization():
    # Mocks
    db = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    surrogate_id = uuid.uuid4()

    # Malicious content
    malicious_content = b"=cmd|' /C calc'!A0,value2\n+1+1,value4"
    file = io.BytesIO(malicious_content)

    # Mock dependencies
    # We need to mock validate_file because MAX_FILE_SIZE_BYTES check might read the file
    # calculate_checksum also reads the file

    with (
        patch("app.services.attachment_service.store_file") as mock_store_file,
        patch("app.services.attachment_service.job_service.enqueue_job"),
        patch("app.services.attachment_service.audit_service.log_event"),
    ):
        # Call the function
        attachment_service.upload_attachment(
            db=db,
            org_id=org_id,
            user_id=user_id,
            filename="malicious.csv",
            content_type="text/csv",
            file=file,
            file_size=len(malicious_content),
            surrogate_id=surrogate_id,
        )

        # Check what was passed to store_file
        args, _ = mock_store_file.call_args
        storage_key, stored_file, content_type = args

        stored_file.seek(0)
        content = stored_file.read()

        # Expectation: Should be sanitized
        # csv.writer uses \r\n by default
        expected_content = b"'=cmd|' /C calc'!A0,value2\r\n'+1+1,value4\r\n"

        # Normalize line endings for comparison
        content_str = content.decode("utf-8").replace("\r\n", "\n").strip()
        expected_str = expected_content.decode("utf-8").replace("\r\n", "\n").strip()

        assert content_str == expected_str


def test_csv_upload_sanitization_ignores_safe_content():
    # Mocks
    db = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    surrogate_id = uuid.uuid4()

    # Safe content
    safe_content = b"header1,header2\nvalue1,value2"
    file = io.BytesIO(safe_content)

    with (
        patch("app.services.attachment_service.store_file") as mock_store_file,
        patch("app.services.attachment_service.job_service.enqueue_job"),
        patch("app.services.attachment_service.audit_service.log_event"),
    ):
        # Call the function
        attachment_service.upload_attachment(
            db=db,
            org_id=org_id,
            user_id=user_id,
            filename="safe.csv",
            content_type="text/csv",
            file=file,
            file_size=len(safe_content),
            surrogate_id=surrogate_id,
        )

        # Check what was passed to store_file
        args, _ = mock_store_file.call_args
        storage_key, stored_file, content_type = args

        stored_file.seek(0)
        content = stored_file.read()

        # Expectation: Should be unchanged
        assert content == safe_content
