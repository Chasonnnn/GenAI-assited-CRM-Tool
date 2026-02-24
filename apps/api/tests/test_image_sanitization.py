from io import BytesIO

import pytest
from PIL import Image

from app.services.attachment_service import strip_exif_data


def _make_image_bytes(mode: str, fmt: str) -> BytesIO:
    image = Image.new(mode, (8, 8), color=(255, 0, 0, 128) if "A" in mode else 255)
    buf = BytesIO()
    image.save(buf, format=fmt)
    buf.seek(0)
    return buf


def test_strip_exif_data_rejects_invalid_image_bytes():
    payload = BytesIO(b"definitely-not-an-image")

    with pytest.raises(ValueError):
        strip_exif_data(payload, "image/jpeg")


def test_strip_exif_data_reencodes_png():
    payload = _make_image_bytes("RGB", "PNG")

    processed = strip_exif_data(payload, "image/png")
    processed.seek(0)

    assert processed.read(8) == b"\x89PNG\r\n\x1a\n"


def test_strip_exif_data_converts_rgba_for_jpeg():
    payload = _make_image_bytes("RGBA", "PNG")

    processed = strip_exif_data(payload, "image/jpeg")
    processed.seek(0)

    assert processed.read(2) == b"\xff\xd8"
