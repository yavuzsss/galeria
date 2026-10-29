"""Video frame sampling with PyAV (bundles its own FFmpeg, so no system ffmpeg is needed)."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import av
from PIL import Image


@dataclass(frozen=True)
class Frame:
    timestamp: float  # seconds from the start of the video, as a <video> element counts it
    image: Image.Image  # upright, downscaled to max_side
    source_size: tuple[int, int]  # upright full-resolution size


def upright(image: Image.Image, rotation: int) -> Image.Image:
    """Apply a display-matrix rotation (degrees counterclockwise, as PyAV reports it).

    Phones store portrait video as landscape frames plus this rotation.
    """
    if rotation % 360 == 0:
        return image
    return image.rotate(rotation, expand=True)


class VideoReader:
    def __init__(self, path: Path):
        self._container = av.open(str(path))
        if not self._container.streams.video:
            self._container.close()
            raise ValueError(f"{path} has no video stream")
        self._stream = self._container.streams.video[0]
        self._stream.thread_type = "AUTO"

        stream_start = self._stream.start_time
        self._start = float(stream_start * self._stream.time_base) if stream_start else 0.0
        if self._stream.duration:
            self.duration: float | None = float(self._stream.duration * self._stream.time_base)
        elif self._container.duration:
            self.duration = self._container.duration / av.time_base
        else:
            self.duration = None

    def __enter__(self) -> "VideoReader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._container.close()

    def frames(
        self, interval: float, max_side: int, max_frames: int | None = None
    ) -> Iterator[Frame]:
        """Yield the first frame at or after every multiple of `interval` seconds.

        Decoding is sequential: it costs the same for any interval and never decodes a frame
        twice, unlike seeking, which re-decodes up to a full keyframe interval per sample.
        Long videos are capped at `max_frames` by widening the interval.
        """
        if max_frames and self.duration:
            interval = max(interval, self.duration / max_frames)
        next_at = 0.0
        for frame in self._container.decode(self._stream):
            if frame.time is None:
                continue
            t = max(frame.time - self._start, 0.0)
            if t + 1e-6 < next_at:
                continue
            while next_at <= t + 1e-6:
                next_at += interval

            rotation = frame.rotation
            image = upright(frame.to_image(), rotation)
            image.thumbnail((max_side, max_side))
            size = (frame.width, frame.height)
            if abs(rotation) == 90:
                size = (frame.height, frame.width)
            yield Frame(timestamp=round(t, 3), image=image, source_size=size)
