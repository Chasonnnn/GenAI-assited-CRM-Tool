from app.services import attachment_service

def test_validate_file_mismatch_extension_mime():
    # This currently PASSES because validation is weak
    # But it represents a security risk (content spoofing)

    # Case 1: PNG extension but PDF mime type
    filename = "image.png"
    content_type = "application/pdf"

    is_valid, error = attachment_service.validate_file(
        filename,
        content_type,
        file_size=1024,
    )
    assert not is_valid
    assert "Content type 'application/pdf' invalid for extension '.png'" in error

    # Case 2: PDF extension but PNG mime type
    filename = "doc.pdf"
    content_type = "image/png"

    is_valid, error = attachment_service.validate_file(
        filename,
        content_type,
        file_size=1024,
    )
    assert not is_valid
    assert "Content type 'image/png' invalid for extension '.pdf'" in error

    # Case 3: Valid case
    filename = "doc.pdf"
    content_type = "application/pdf"

    is_valid, error = attachment_service.validate_file(
        filename,
        content_type,
        file_size=1024,
    )
    assert is_valid
