"""Indexing pipeline: scan a folder, diff against what is stored, embed what changed."""

import logging
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from galeria.core.encoder import Encoder
from galeria.core.metadata import FileRecord, MetadataStore, NewVector
from galeria.core.scanner import MediaFile, scan
from galeria.core.thumbnails import load_image, save_thumbnail, thumb_name
from galeria.core.vector_store import VectorStore
from galeria.core.video import VideoReader

log = logging.getLogger(__name__)

SAVE_EVERY_UNITS = 20  # photo batches or videos between FAISS checkpoints


@dataclass
class IndexReport:
    root: str
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    vectors_added: int = 0
    frames_sampled: int = 0  # video frames embedded
    frames_kept: int = 0  # ...and stored after near-duplicate removal
    failed: list[str] = field(default_factory=list)
    seconds: float = 0.0


@dataclass(frozen=True)
class Progress:
    done: int
    total: int
    current: str | None


ProgressCallback = Callable[[Progress], None]


class Indexer:
    def __init__(
        self,
        encoder: Encoder,
        store: VectorStore,
        meta: MetadataStore,
        index_path: Path,
        thumbs_dir: Path,
        batch_size: int = 32,
        max_image_side: int = 512,
        thumb_size: int = 384,
        frame_interval: float = 2.0,
        frame_dedup_threshold: float = 0.95,
        max_frames: int | None = 900,
    ):
        self.encoder = encoder
        self.store = store
        self.meta = meta
        self.index_path = index_path
        self.thumbs_dir = thumbs_dir
        self.batch_size = batch_size
        self.max_image_side = max_image_side
        self.thumb_size = thumb_size
        self.frame_interval = frame_interval
        self.frame_dedup_threshold = frame_dedup_threshold
        self.max_frames = max_frames

    def index_folder(
        self, root: Path | str, on_progress: ProgressCallback | None = None
    ) -> IndexReport:
        started = time.perf_counter()
        root = Path(root).expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"{root} is not a directory")

        self.reconcile()
        self.meta.add_root(str(root))
        report = IndexReport(root=str(root))

        existing = self.meta.files_under(str(root))
        seen: set[str] = set()
        todo: list[tuple[MediaFile, FileRecord | None]] = []
        for media in scan(root, exclude=[self.thumbs_dir]):
            key = str(media.path)
            seen.add(key)
            old = existing.get(key)
            if old and old.size == media.size and old.mtime == media.mtime:
                report.unchanged += 1
            else:
                todo.append((media, old))

        gone = [rec.id for path, rec in existing.items() if path not in seen]
        self._remove_files(gone)
        report.removed = len(gone)

        # Changed files are dropped first and then indexed like new ones.
        self._remove_files([old.id for _, old in todo if old])

        photos = [(m, old) for m, old in todo if m.kind == "photo"]
        videos = [(m, old) for m, old in todo if m.kind == "video"]
        # Photos go in batches; a video is its own batch of frames.
        units = [
            photos[i : i + self.batch_size] for i in range(0, len(photos), self.batch_size)
        ] + [[v] for v in videos]

        total, done = len(todo), 0
        if on_progress:
            on_progress(Progress(0, total, None))
        for n, unit in enumerate(units, start=1):
            if unit[0][0].kind == "photo":
                self._index_photo_batch(unit, report)
            else:
                self._index_video(*unit[0], report)
            done += len(unit)
            if on_progress:
                on_progress(Progress(done, total, str(unit[-1][0].path)))
            if n % SAVE_EVERY_UNITS == 0:
                self.store.save(self.index_path)

        self.store.save(self.index_path)
        report.seconds = time.perf_counter() - started
        return report

    def reconcile(self) -> None:
        """Bring SQLite and FAISS back in sync after a crash between their writes.

        FAISS is saved periodically, SQLite commits per file, so after a crash SQLite can know
        about vectors FAISS lost. Those files are forgotten so the next run re-indexes them.
        """
        faiss_ids = set(self.store.ids().tolist())
        db_ids = self.meta.all_vector_ids()
        orphans = faiss_ids - db_ids
        missing = db_ids - faiss_ids
        if orphans:
            log.warning("removing %d vectors with no metadata", len(orphans))
            self.store.remove(orphans)
        if missing:
            file_ids = self.meta.file_ids_for_vectors(missing)
            log.warning("%d files lost their vectors and will be re-indexed", len(file_ids))
            self._remove_files(file_ids)

    def _index_photo_batch(
        self, batch: list[tuple[MediaFile, FileRecord | None]], report: IndexReport
    ) -> None:
        loaded = []
        for media, old in batch:
            try:
                image, size = load_image(media.path, self.max_image_side)
            except Exception as exc:  # corrupt or unreadable files must not stop the run
                log.warning("skipping %s: %s", media.path, exc)
                report.failed.append(str(media.path))
                continue
            loaded.append((media, old, image, size))
        if not loaded:
            return

        vectors = self.encoder.encode_images([image for _, _, image, _ in loaded])
        ids = []
        for (media, old, image, (width, height)), _vector in zip(loaded, vectors, strict=True):
            thumb = thumb_name(media.path, media.mtime)
            save_thumbnail(image, self.thumbs_dir / thumb, self.thumb_size)
            _, vector_ids = self.meta.add_media(
                str(media.path),
                "photo",
                media.size,
                media.mtime,
                [NewVector(timestamp=None, thumb=thumb)],
                width=width,
                height=height,
            )
            ids.extend(vector_ids)
            if old:
                report.updated += 1
            else:
                report.added += 1
        self.store.add(ids, np.asarray(vectors))
        report.vectors_added += len(ids)

    def _index_video(self, media: MediaFile, old: FileRecord | None, report: IndexReport) -> None:
        kept: list[np.ndarray] = []
        entries: list[NewVector] = []
        source_size: tuple[int, int] | None = None
        last: np.ndarray | None = None
        sampled = 0
        try:
            with VideoReader(media.path) as video:
                duration = video.duration
                frames = video.frames(self.frame_interval, self.max_image_side, self.max_frames)
                for chunk in _batched(frames, self.batch_size):
                    vectors = self.encoder.encode_images([f.image for f in chunk])
                    sampled += len(chunk)
                    for frame, vector in zip(chunk, vectors, strict=True):
                        source_size = source_size or frame.source_size
                        # Compare against the last *kept* frame, so a slow pan still adds a
                        # new frame once it has drifted far enough.
                        if last is not None and float(vector @ last) >= self.frame_dedup_threshold:
                            continue
                        last = vector
                        thumb = thumb_name(media.path, media.mtime, frame.timestamp)
                        save_thumbnail(frame.image, self.thumbs_dir / thumb, self.thumb_size)
                        kept.append(vector)
                        entries.append(NewVector(timestamp=frame.timestamp, thumb=thumb))
            if not kept:
                raise ValueError("no decodable frames")
        except Exception as exc:  # corrupt or unreadable files must not stop the run
            log.warning("skipping %s: %s", media.path, exc)
            report.failed.append(str(media.path))
            for entry in entries:
                (self.thumbs_dir / entry.thumb).unlink(missing_ok=True)
            return

        width, height = source_size or (None, None)
        _, ids = self.meta.add_media(
            str(media.path),
            "video",
            media.size,
            media.mtime,
            entries,
            width=width,
            height=height,
            duration=duration,
        )
        self.store.add(ids, np.vstack(kept))
        report.vectors_added += len(ids)
        report.frames_sampled += sampled
        report.frames_kept += len(ids)
        if old:
            report.updated += 1
        else:
            report.added += 1

    def _remove_files(self, file_ids) -> None:
        removed = self.meta.delete_files(file_ids)
        if not removed:
            return
        self.store.remove(vid for vid, _ in removed)
        for _, thumb in removed:
            (self.thumbs_dir / thumb).unlink(missing_ok=True)


def _batched(items: Iterable, size: int) -> Iterator[list]:
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
