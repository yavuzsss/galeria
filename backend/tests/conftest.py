from pathlib import Path

import av
import numpy as np
import pytest
from PIL import Image

from galeria.config import Settings
from galeria.core.encoder import FakeEncoder
from galeria.services import Services, open_services

COLORS = {"red": (220, 20, 20), "green": (20, 200, 40), "blue": (30, 40, 220)}


def make_image(path: Path, color: tuple[int, int, int], size=(64, 48)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def make_video(
    path: Path,
    segments: list[tuple[tuple[int, int, int], float]],
    fps: int = 5,
    size=(64, 48),
) -> Path:
    """Write an H.264 MP4 made of solid-color segments, e.g. [(red, 4.0), (green, 4.0)]."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height = size
        stream.pix_fmt = "yuv420p"
        for color, seconds in segments:
            pixels = np.full((size[1], size[0], 3), color, dtype=np.uint8)
            for _ in range(round(seconds * fps)):
                frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
                container.mux(stream.encode(frame))
        container.mux(stream.encode())
    return path


@pytest.fixture
def video_path(tmp_path: Path) -> Path:
    """10 s clip: red 0-4 s, green 4-8 s, blue 8-10 s."""
    return make_video(
        tmp_path / "videos" / "clip.mp4",
        [(COLORS["red"], 4), (COLORS["green"], 4), (COLORS["blue"], 2)],
    )


@pytest.fixture
def photo_dir(tmp_path: Path) -> Path:
    """A small library: one photo per color, one nested, plus noise the scanner must ignore."""
    root = tmp_path / "library"
    for name, color in COLORS.items():
        make_image(root / f"{name}.jpg", color)
    make_image(root / "nested" / "deep" / "red2.png", (200, 30, 30))
    (root / "notes.txt").write_text("not media")
    make_image(root / ".hidden" / "secret.jpg", (0, 0, 0))
    make_image(root / ".dotfile.jpg", (0, 0, 0))
    return root


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", batch_size=2)


@pytest.fixture
def services(settings: Settings):
    s: Services = open_services(settings, encoder=FakeEncoder())
    yield s
    s.close()
