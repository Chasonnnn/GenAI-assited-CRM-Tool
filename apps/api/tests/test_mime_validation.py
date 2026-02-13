import pytest
from app.services import attachment_service

def test_validate_file_fails_mismatch():
    # Currently this should FAIL because mismatched types are rejected
    is_valid, error = attachment_service.validate_file(
        "mismatch.pdf",
        "image/png",
        file_size=1024,
    )
    assert not is_valid, "Validate file should reject mismatched extension/MIME"
    assert "does not match extension" in error
