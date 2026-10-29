from pathlib import Path

from PIL import Image

from galeria.core.thumbnails import load_image, save_thumbnail, thumb_name


def test_load_image_downscales_and_reports_original_size(tmp_path: Path):
    path = tmp_path / "big.jpg"
    Image.new("RGB", (2000, 1000), (1, 2, 3)).save(path)
    image, size = load_image(path, max_side=512)
    assert size == (2000, 1000)
    assert max(image.size) <= 512 and image.mode == "RGB"


def test_load_image_applies_exif_rotation(tmp_path: Path):
    path = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° clockwise on display
    Image.new("RGB", (400, 200)).save(path, exif=exif)
    image, size = load_image(path, max_side=512)
    assert size == (200, 400)
    assert image.size == (200, 400)


def test_load_image_converts_mode(tmp_path: Path):
    path = tmp_path / "alpha.png"
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(path)
    image, _ = load_image(path, max_side=512)
    assert image.mode == "RGB"


def test_thumb_name_changes_with_mtime_and_timestamp():
    p = Path("/a.jpg")
    assert thumb_name(p, 1.0) == thumb_name(p, 1.0)
    assert thumb_name(p, 1.0) != thumb_name(p, 2.0)
    assert thumb_name(p, 1.0, 0.0) != thumb_name(p, 1.0, 2.0)


def test_save_thumbnail(tmp_path: Path):
    dest = tmp_path / "t" / "x.jpg"
    save_thumbnail(Image.new("RGB", (1000, 500)), dest, size=384)
    with Image.open(dest) as thumb:
        assert thumb.size == (384, 192)
