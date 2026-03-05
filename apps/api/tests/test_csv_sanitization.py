import pytest
from io import BytesIO
from app.services.attachment_service import sanitize_csv


def test_sanitize_csv_valid_no_injection():
    content = b"Name,Age,City\nAlice,30,New York\nBob,25,San Francisco"
    file = BytesIO(content)
    sanitized = sanitize_csv(file, "text/csv")
    assert (
        sanitized.read().decode("utf-8").replace("\r\n", "\n")
        == "Name,Age,City\nAlice,30,New York\nBob,25,San Francisco\n"
    )


def test_sanitize_csv_with_injection():
    content = (
        b"Name,Age,Formula\nAlice,30,=1+1\nBob,25,+SUM(A1:A2)\nCharlie,40,-SUBTRACT\nDavid,50,@CMD"
    )
    file = BytesIO(content)
    sanitized = sanitize_csv(file, "text/csv")
    result = sanitized.read().decode("utf-8").replace("\r\n", "\n")
    assert "Name,Age,Formula\n" in result
    assert "Alice,30,'=1+1\n" in result
    assert "Bob,25,'+SUM(A1:A2)\n" in result
    assert "Charlie,40,'-SUBTRACT\n" in result
    assert "David,50,'@CMD\n" in result


def test_sanitize_csv_non_csv_content_type():
    content = b"Some random bytes"
    file = BytesIO(content)
    sanitized = sanitize_csv(file, "image/png")
    assert sanitized == file
    assert sanitized.read() == content


def test_sanitize_csv_invalid_file_structure():
    # Attempt to trigger csv.Error or Exception to check the fail-close behavior
    # For instance, a very malformed file or closed file.
    file = BytesIO(b"data")
    file.close()
    with pytest.raises(ValueError, match="Failed to sanitize CSV file"):
        sanitize_csv(file, "text/csv")
