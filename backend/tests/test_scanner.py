from pathlib import Path

from galeria.core.scanner import classify, scan
from tests.conftest import make_image


def test_classify_by_extension_case_insensitive():
    assert classify(Path("a.JPG")) == "photo"
    assert classify(Path("a.webp")) == "photo"
    assert classify(Path("clip.MOV")) == "video"
    assert classify(Path("notes.txt")) is None
    assert classify(Path("no_extension")) is None


def test_scan_is_recursive_and_skips_hidden_and_unsupported(photo_dir: Path):
    names = sorted(p.path.relative_to(photo_dir).as_posix() for p in scan(photo_dir))
    assert names == ["blue.jpg", "green.jpg", "nested/deep/red2.png", "red.jpg"]


def test_scan_reports_size_and_mtime(photo_dir: Path):
    media = {m.path.name: m for m in scan(photo_dir)}
    stat = (photo_dir / "red.jpg").stat()
    assert media["red.jpg"].size == stat.st_size
    assert media["red.jpg"].mtime == stat.st_mtime
    assert media["red.jpg"].kind == "photo"


def test_scan_excludes_given_folders(tmp_path: Path):
    make_image(tmp_path / "keep.jpg", (1, 2, 3))
    make_image(tmp_path / "data" / "thumbs" / "t.jpg", (1, 2, 3))
    names = [m.path.name for m in scan(tmp_path, exclude=[tmp_path / "data" / "thumbs"])]
    assert names == ["keep.jpg"]
