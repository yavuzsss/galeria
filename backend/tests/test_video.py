from pathlib import Path

import av
import numpy as np
import pytest
from PIL import Image

from galeria.core.video import VideoReader, upright
from tests.conftest import COLORS, make_video


def _dominant(image: Image.Image) -> str:
    mean = np.asarray(image, dtype=np.float32).mean(axis=(0, 1))
    return min(COLORS, key=lambda name: np.abs(mean - COLORS[name]).sum())


def test_reader_reports_duration(video_path: Path):
    with VideoReader(video_path) as video:
        assert video.duration == pytest.approx(10.0, abs=0.3)


def test_frames_are_sampled_every_interval(video_path: Path):
    with VideoReader(video_path) as video:
        frames = list(video.frames(interval=2.0, max_side=512))
    assert [f.timestamp for f in frames] == pytest.approx([0, 2, 4, 6, 8], abs=0.05)
    assert [_dominant(f.image) for f in frames] == ["red", "red", "green", "green", "blue"]
    assert all(f.image.mode == "RGB" and f.source_size == (64, 48) for f in frames)


def test_frames_are_downscaled(tmp_path: Path):
    path = make_video(tmp_path / "big.mp4", [((10, 10, 10), 1)], size=(640, 360))
    with VideoReader(path) as video:
        frame = next(video.frames(interval=1.0, max_side=128))
    assert frame.image.size == (128, 72)
    assert frame.source_size == (640, 360)


def test_long_videos_are_capped_by_widening_the_interval(video_path: Path):
    with VideoReader(video_path) as video:
        frames = list(video.frames(interval=0.5, max_side=64, max_frames=4))
    assert len(frames) <= 4
    assert frames[1].timestamp == pytest.approx(2.5, abs=0.25)


def test_non_video_files_raise(tmp_path: Path):
    path = tmp_path / "fake.mp4"
    path.write_bytes(b"not a video at all")
    with pytest.raises(av.FFmpegError), VideoReader(path) as video:
        list(video.frames(interval=1.0, max_side=64))


def test_upright_rotates_counterclockwise():
    # Left half red on a landscape frame; a +90° display rotation turns it portrait with the
    # red half at the bottom.
    pixels = np.zeros((20, 40, 3), dtype=np.uint8)
    pixels[:, :20] = COLORS["red"]
    rotated = upright(Image.fromarray(pixels), 90)
    assert rotated.size == (20, 40)
    assert _dominant(rotated.crop((0, 25, 20, 40))) == "red"
    assert upright(Image.fromarray(pixels), 0).size == (40, 20)
