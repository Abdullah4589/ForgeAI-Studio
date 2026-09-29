"""Inspection of untrusted image uploads: validation, fingerprints and quality heuristics.

Everything here works on bytes in memory and never trusts the filename or extension.
"""

import hashlib
import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

# Canonical extension per accepted format; the stored file always gets the one matching its content.
ALLOWED_FORMATS = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}

# Refuse images whose decoded size could exhaust memory (decompression bombs). 50 MP is far above
# any sensible training image while staying well below what a small machine can decode.
MAX_PIXELS = 50_000_000

THUMBNAIL_SIZE = 256

# Edge-variance below this suggests a blurry image. Calibrated on 512 px generations: sharp images
# scored 1100-2600, a 1 px Gaussian blur 240-560, a 2 px blur 30-80.
BLUR_THRESHOLD = 100.0
# Longest side / shortest side above this is awkward to train on without heavy cropping.
MAX_ASPECT_RATIO = 2.0
# Perceptual hashes within this many differing bits are treated as near-duplicates.
NEAR_DUPLICATE_BITS = 5


class InvalidImageError(Exception):
    """The upload is not an acceptable image; `reason` is a stable code, `message` user-facing."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class ImageFacts:
    format: str
    extension: str
    width: int
    height: int
    sha256: str
    perceptual_hash: str
    blur_score: float


def analyse(data: bytes) -> ImageFacts:
    """Validate an uploaded image and compute the facts used for duplicates and quality flags."""
    image = _open_checked(data)
    fmt = str(image.format)
    try:
        # Measure what a viewer sees: phone photos often store rotation in EXIF only.
        oriented = ImageOps.exif_transpose(image)
        oriented.load()
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidImageError("corrupt", "The image data is damaged or incomplete.") from exc
    return ImageFacts(
        format=fmt,
        extension=ALLOWED_FORMATS[fmt],
        width=oriented.width,
        height=oriented.height,
        sha256=hashlib.sha256(data).hexdigest(),
        perceptual_hash=difference_hash(oriented),
        blur_score=blur_score(oriented),
    )


def _open_checked(data: bytes) -> Image.Image:
    try:
        with warnings.catch_warnings():
            # Pillow only warns between 1x and 2x its own limit; we enforce ours explicitly below.
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            probe = Image.open(io.BytesIO(data))
            if probe.format not in ALLOWED_FORMATS:
                raise InvalidImageError(
                    "unsupported_format", "Only PNG, JPEG and WebP images are supported."
                )
            if probe.width * probe.height > MAX_PIXELS:
                raise InvalidImageError(
                    "too_many_pixels",
                    f"The image is too large ({probe.width}x{probe.height} pixels).",
                )
            # verify() checks integrity without decoding, but leaves the object unusable.
            probe.verify()
            return Image.open(io.BytesIO(data))
    except InvalidImageError:
        raise
    except Image.DecompressionBombError as exc:
        # Pillow refuses absurd dimensions on its own, before our check can run.
        raise InvalidImageError("too_many_pixels", "The image has too many pixels.") from exc
    except UnidentifiedImageError as exc:
        raise InvalidImageError("not_an_image", "The file is not a readable image.") from exc
    except (OSError, SyntaxError, ValueError) as exc:
        # Pillow reports truncated or malformed data through these.
        raise InvalidImageError("corrupt", "The image data is damaged or incomplete.") from exc


def difference_hash(image: Image.Image) -> str:
    """64-bit dHash as 16 hex chars; survives resizing and re-compression of the same picture."""
    small = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def hamming_distance(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def blur_score(image: Image.Image) -> float:
    """Variance of an edge map: sharp images have many strong edges, blurry ones few."""
    gray = image.convert("L")
    gray.thumbnail((512, 512))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    if edges.width > 4 and edges.height > 4:
        # The edge filter leaves artefacts along the border that would mask real blur.
        edges = edges.crop((2, 2, edges.width - 2, edges.height - 2))
    return round(float(ImageStat.Stat(edges).var[0]), 2)


def quality_flags(width: int, height: int, blur: float, target: int) -> list[str]:
    """Flags that depend only on the image itself and the dataset's target resolution."""
    flags: list[str] = []
    if min(width, height) < target:
        flags.append("low_resolution")
    if max(width, height) / min(width, height) > MAX_ASPECT_RATIO:
        flags.append("extreme_aspect_ratio")
    if blur < BLUR_THRESHOLD:
        flags.append("possibly_blurry")
    return flags


def make_thumbnail(data: bytes) -> bytes:
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
    image.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
    out = io.BytesIO()
    image.save(out, format="WEBP", quality=80)
    return out.getvalue()
