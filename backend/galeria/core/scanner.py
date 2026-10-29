import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

MediaKind = Literal["photo", "video"]

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}


@dataclass(frozen=True)
class MediaFile:
    path: Path
    kind: MediaKind
    size: int
    mtime: float


def classify(path: Path) -> MediaKind | None:
    ext = path.suffix.lower()
    if ext in PHOTO_EXTENSIONS:
        return "photo"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return None


def scan(root: Path, exclude: Iterable[Path] = ()) -> Iterator[MediaFile]:
    """Yield supported media under `root`, recursively.

    Hidden files and folders are skipped, as is anything under `exclude` (our own thumbnail
    folder, if the user indexes a directory that contains the data dir).
    """
    excluded = {Path(p).resolve() for p in exclude}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if not d.startswith(".") and (Path(dirpath) / d).resolve() not in excluded
        )
        for filename in sorted(filenames):
            if filename.startswith("."):
                continue
            path = Path(dirpath) / filename
            kind = classify(path)
            if kind is None:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            yield MediaFile(path=path, kind=kind, size=stat.st_size, mtime=stat.st_mtime)
