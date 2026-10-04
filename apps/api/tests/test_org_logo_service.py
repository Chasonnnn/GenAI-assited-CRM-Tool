"""Database-free checks for logo image processing and storage boundaries."""

import io
import struct
import zlib
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image, JpegImagePlugin, PngImagePlugin

from app.core.config import settings
from app.jobs.handlers import storage
from app.services import org_logo_service


def _encode(image, format="PNG", **kwargs):
    output = io.BytesIO()
    image.save(output, format=format, **kwargs)
    return output.getvalue()


@pytest.mark.parametrize("extension", ["png", "webp"])
@pytest.mark.parametrize("palette", [False, True], ids=["rgba", "palette"])
def test_square_logo_preserves_transparency(extension, palette):
    if palette:
        source = Image.new("P", (128, 64), 0)
        source.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
        source.info["transparency"] = 0
        source.paste(1, (48, 16, 80, 48))
    else:
        source = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
        source.paste((255, 0, 0, 255), (48, 16, 80, 48))

    result, result_extension = org_logo_service.process_square_logo(
        _encode(source), f"logo.{extension}"
    )

    assert result_extension == extension
    with Image.open(io.BytesIO(result)) as image:
        assert image.format == extension.upper()
        assert image.size == (256, 256)
        rgba = image.convert("RGBA")
        assert rgba.getpixel((8, 8))[3] == 0
        red, green, blue, alpha = rgba.getpixel((128, 128))
        assert red > 240 and green < 15 and blue < 15
        assert alpha == 255


@pytest.mark.parametrize("mode", ["RGBA", "CMYK"])
def test_square_logo_converts_to_rgb_jpeg(mode):
    source = Image.new("RGB", (128, 64), "red").convert(mode)
    if mode == "RGBA":
        source.putalpha(128)
    content = _encode(source, "PNG" if mode == "RGBA" else "JPEG")

    result, extension = org_logo_service.process_square_logo(content, "logo.jpg")

    assert extension == "jpg"
    with Image.open(io.BytesIO(result)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert image.size == (256, 256)
        red, green, blue = image.getpixel((128, 128))
        assert red > 240 and green < 15 and blue < 15


def test_square_logo_applies_exif_rotation_before_center_crop():
    source = Image.new("RGB", (1600, 800), "red")
    source.paste("blue", (800, 0, 1600, 800))
    exif = Image.Exif()
    exif[274] = 6  # Clockwise 90 degrees: red left half becomes the top half.

    result, _ = org_logo_service.process_square_logo(
        _encode(source, "JPEG", exif=exif), "phone.jpg"
    )

    with Image.open(io.BytesIO(result)) as image:
        assert image.size == (256, 256)
        red, green, blue = image.getpixel((128, 32))
        assert red > 240 and green < 15 and blue < 15
        red, green, blue = image.getpixel((128, 224))
        assert blue > 240 and red < 15 and green < 15
        assert 274 not in image.getexif()


def test_square_logo_reduces_jpeg_decode_size(monkeypatch):
    content = _encode(Image.new("RGB", (2048, 1024), "red"), "JPEG")
    decoded_sizes = []
    original_load = JpegImagePlugin.JpegImageFile.load

    def record_decode(image):
        decoded_sizes.append(image.size)
        return original_load(image)

    monkeypatch.setattr(JpegImagePlugin.JpegImageFile, "load", record_decode)
    result, _ = org_logo_service.process_square_logo(content, "large.jpg")
    assert decoded_sizes
    assert all(width <= 512 and height <= 256 for width, height in decoded_sizes)
    with Image.open(io.BytesIO(result)) as image:
        assert image.size == (256, 256)


@pytest.mark.parametrize("size", [(4097, 4096), (9400, 9400)])
def test_square_logo_rejects_pixel_limit_before_decode(monkeypatch, size):
    # Replace only the PNG header dimensions; decoding is forbidden by this contract.
    content = bytearray(_encode(Image.new("RGBA", (64, 64))))
    content[16:24] = struct.pack(">II", *size)
    content[29:33] = struct.pack(">I", zlib.crc32(content[12:29]))

    def forbidden_decode(image):
        pytest.fail("Oversized image reached pixel decoding")

    monkeypatch.setattr(PngImagePlugin.PngImageFile, "load", forbidden_decode)
    with pytest.raises(ValueError, match="pixel"):
        org_logo_service.process_square_logo(bytes(content), "oversized.png")


def test_square_logo_uses_first_mpo_frame_as_jpeg():
    first = Image.new("RGB", (128, 64), "red")
    second = Image.new("RGB", (128, 64), "blue")
    content = _encode(first, "MPO", save_all=True, append_images=[second])
    with Image.open(io.BytesIO(content)) as source:
        assert source.format == "MPO"
        assert source.n_frames == 2

    result, extension = org_logo_service.process_square_logo(content, "phone.jpg")

    assert extension == "jpg"
    with Image.open(io.BytesIO(result)) as image:
        assert image.format == "JPEG"
        assert image.size == (256, 256)
        red, green, blue = image.getpixel((128, 128))
        assert red > 240 and green < 15 and blue < 15


@pytest.mark.parametrize("escape", ["parent", "symlink"])
def test_local_logo_delete_rejects_storage_root_escape(monkeypatch, tmp_path, escape):
    base = tmp_path / "storage"
    org_dir = base / "logos" / str(uuid4())
    org_dir.mkdir(parents=True)
    victim = tmp_path / "victim.txt"
    victim.write_text("keep")
    if escape == "parent":
        key = f"logos/{org_dir.name}/../../../victim.txt"
    else:
        (org_dir / "link").symlink_to(tmp_path, target_is_directory=True)
        key = f"logos/{org_dir.name}/link/victim.txt"
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(base))

    with pytest.raises(ValueError, match="Invalid local logo storage path"):
        org_logo_service.delete_logo_from_storage(org_logo_service.build_local_logo_url(key))

    assert victim.read_text() == "keep"


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["../../../victim.txt", "../victim.txt", "./victim.txt"])
async def test_logo_delete_job_rejects_unnormalized_keys_before_deleting_batch(
    monkeypatch, tmp_path, suffix
):
    org_id = uuid4()
    base = tmp_path / "storage"
    org_dir = base / "logos" / str(org_id)
    org_dir.mkdir(parents=True)
    valid = org_dir / "valid.png"
    valid.write_bytes(b"keep valid logo")
    victim = tmp_path / "victim.txt"
    victim.write_text("keep")
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(base))
    job = SimpleNamespace(
        organization_id=org_id,
        payload={"storage_keys": [f"logos/{org_id}/valid.png", f"logos/{org_id}/{suffix}"]},
    )

    with pytest.raises(ValueError, match="Invalid logo storage key"):
        await storage.process_storage_delete(None, job)

    assert valid.read_bytes() == b"keep valid logo"
    assert victim.read_text() == "keep"
