from app.services import attachment_service


def test_validate_file_prevents_mismatch():
    """
    This test verifies that the implementation prevents mismatched
    extension and MIME type.
    """
    # Mismatch case: .jpg with application/pdf
    is_valid, error = attachment_service.validate_file(
        "test.jpg",
        "application/pdf",
        file_size=1024,
    )
    assert is_valid is False
    assert "does not match content type" in error


def test_validate_file_allows_match():
    """
    Verify valid cases still work.
    """
    # Valid case: .pdf with application/pdf
    is_valid, error = attachment_service.validate_file(
        "report.pdf",
        "application/pdf",
        file_size=1024,
    )
    assert is_valid is True
    assert error is None

    # Valid case: .jpg with image/jpeg
    is_valid, error = attachment_service.validate_file(
        "photo.jpg",
        "image/jpeg",
        file_size=1024,
    )
    assert is_valid is True
    assert error is None
