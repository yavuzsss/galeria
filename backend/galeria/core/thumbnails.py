import hashlib
from pathlib import Path

from PIL import Image, ImageOps

_EXIF_ORIENTATION = 0x0112
_ROTATED_ORIENTATIONS = {5, 6, 7, 8}  # orientations that swap width and height


def load_image(path: Path, max_side: int) -> tuple[Image.Image, tuple[int, int]]:
    """Open an image upright and downscaled to `max_side`; also return its original size.

    `draft` lets the JPEG decoder skip full-resolution decoding, which is the main cost when
    indexing large camera photos.
    """
    with Image.open(path) as image:
        width, height = image.size
        if image.getexif().get(_EXIF_ORIENTATION) in _ROTATED_ORIENTATIONS:
            width, height = height, width
        image.draft("RGB", (max_side, max_side))
        upright = ImageOps.exif_transpose(image).convert("RGB")
    upright.thumbnail((max_side, max_side))
    return upright, (width, height)


def thumb_name(path: Path, mtime: float, timestamp: float | None = None) -> str:
    # mtime is part of the key so an edited file gets a new URL and stale browser caches miss.
    key = f"{path}|{mtime}|{timestamp}"
    return hashlib.sha1(key.encode()).hexdigest()[:20] + ".jpg"


def save_thumbnail(image: Image.Image, dest: Path, size: int) -> None:
    thumb = image.copy()
    thumb.thumbnail((size, size))
    dest.parent.mkdir(parents=True, exist_ok=True)
    thumb.save(dest, "JPEG", quality=82, optimize=True)
