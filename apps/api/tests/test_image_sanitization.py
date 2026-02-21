import io
import pytest
from PIL import Image
from app.services.attachment_service import strip_exif_data

def test_strip_exif_data_fail_open_vulnerability():
    """
    Test that invalid image files masquerading as images are rejected.
    """
    # Create a fake file that is NOT a valid image
    fake_image_content = b"<html><body>Not an image</body></html>"
    file = io.BytesIO(fake_image_content)

    # After fix, this MUST raise ValueError
    with pytest.raises(ValueError, match="Invalid image file"):
        strip_exif_data(file, "image/png")

def test_strip_exif_data_valid_image():
    """Test that valid images are processed correctly."""
    # Create a simple valid image
    img = Image.new('RGB', (60, 30), color = 'red')
    file = io.BytesIO()
    img.save(file, format='PNG')
    file.seek(0)

    result = strip_exif_data(file, "image/png")
    result.seek(0)

    # Should be a valid image
    processed_img = Image.open(result)
    assert processed_img.format == "PNG"
    assert processed_img.size == (60, 30)
