import io
import struct
import zlib

import pytest
from PIL import Image, ImageFilter

from forge_api.services import image_analysis
from forge_api.services.dataset_service import display_filename
from forge_api.services.image_analysis import (
    BLUR_THRESHOLD,
    NEAR_DUPLICATE_BITS,
    InvalidImageError,
    analyse,
    hamming_distance,
    make_thumbnail,
    quality_flags,
)
from tests.helpers import encode, picture


@pytest.mark.parametrize(
    ("fmt", "extension"), [("PNG", ".png"), ("JPEG", ".jpg"), ("WEBP", ".webp")]
)
def test_accepts_supported_formats(fmt: str, extension: str) -> None:
    data = encode(picture(1, (640, 480)), fmt)
    facts = analyse(data)
    assert (facts.format, facts.extension) == (fmt, extension)
    assert (facts.width, facts.height) == (640, 480)
    assert len(facts.sha256) == 64
    assert len(facts.perceptual_hash) == 16


def test_rejects_unsupported_format() -> None:
    with pytest.raises(InvalidImageError) as info:
        analyse(encode(picture(1, (64, 64)), "GIF"))
    assert info.value.reason == "unsupported_format"


def test_rejects_non_image() -> None:
    with pytest.raises(InvalidImageError) as info:
        analyse(b"#!/bin/sh\necho definitely not an image\n")
    assert info.value.reason == "not_an_image"


def test_rejects_truncated_image() -> None:
    data = encode(picture(1), "PNG")
    with pytest.raises(InvalidImageError) as info:
        analyse(data[: len(data) // 2])
    assert info.value.reason == "corrupt"


PNG_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def test_rejects_decompression_bomb_from_header_alone() -> None:
    # Headers claiming 100k x 100k pixels; must be refused without decoding any pixel data.
    header = struct.pack(">IIBBBBB", 100_000, 100_000, 8, 2, 0, 0, 0)
    png = (
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(b""))
        + _png_chunk(b"IEND", b"")
    )
    with pytest.raises(InvalidImageError) as info:
        analyse(png)
    assert info.value.reason == "too_many_pixels"


def test_enforces_own_pixel_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(image_analysis, "MAX_PIXELS", 100 * 100)
    analyse(encode(picture(1, (100, 100))))  # exactly at the limit is fine
    with pytest.raises(InvalidImageError) as info:
        analyse(encode(picture(1, (101, 100))))
    assert info.value.reason == "too_many_pixels"


def test_reports_exif_oriented_size() -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # "rotate 90 CW": stored landscape, displayed portrait
    data = encode(picture(1, (600, 400)), "JPEG", exif=exif)
    facts = analyse(data)
    assert (facts.width, facts.height) == (400, 600)


def test_perceptual_hash_matches_resized_recompressed_copy() -> None:
    original = analyse(encode(picture(1), "PNG"))
    copy = analyse(encode(picture(1).resize((300, 300)), "JPEG", quality=70))
    other = analyse(encode(picture(2), "PNG"))
    assert original.sha256 != copy.sha256
    assert hamming_distance(original.perceptual_hash, copy.perceptual_hash) <= NEAR_DUPLICATE_BITS
    assert hamming_distance(original.perceptual_hash, other.perceptual_hash) > NEAR_DUPLICATE_BITS


def test_blur_score_separates_sharp_and_blurry() -> None:
    sharp = picture(3)
    assert analyse(encode(sharp)).blur_score > BLUR_THRESHOLD
    blurry = sharp.filter(ImageFilter.GaussianBlur(4))
    assert analyse(encode(blurry)).blur_score < BLUR_THRESHOLD


@pytest.mark.parametrize(
    ("size", "blur", "target", "expected"),
    [
        ((512, 512), 500.0, 512, []),
        ((400, 800), 500.0, 512, ["low_resolution"]),
        ((1100, 512), 500.0, 512, ["extreme_aspect_ratio"]),
        ((1024, 1024), 20.0, 512, ["possibly_blurry"]),
        ((512, 512), 500.0, 1024, ["low_resolution"]),
    ],
)
def test_quality_flags(
    size: tuple[int, int], blur: float, target: int, expected: list[str]
) -> None:
    assert quality_flags(size[0], size[1], blur, target) == expected


def test_thumbnail_is_small_webp() -> None:
    thumb = Image.open(io.BytesIO(make_thumbnail(encode(picture(1, (1200, 600))))))
    assert thumb.format == "WEBP"
    assert max(thumb.size) == image_analysis.THUMBNAIL_SIZE


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("cat.png", "cat.png"),
        ("../../etc/evil.png", "evil.png"),
        ("C:\\Users\\me\\photo 1.jpg", "photo 1.jpg"),
        ("", "image"),
        ("x" * 300 + ".png", "x" * 255),
    ],
)
def test_display_filename(raw: str, expected: str) -> None:
    assert display_filename(raw) == expected
