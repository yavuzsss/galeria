import os
from pathlib import Path

import pytest

from galeria.services import Services
from tests.conftest import make_image, make_video


def _thumbs(services: Services) -> set[str]:
    return {p.name for p in services.settings.thumbs_dir.iterdir()}


def test_first_run_indexes_all_photos(services: Services, photo_dir: Path):
    progress = []
    report = services.indexer.index_folder(photo_dir, progress.append)

    assert (report.added, report.updated, report.removed, report.unchanged) == (4, 0, 0, 0)
    assert report.vectors_added == 4
    assert len(services.store) == 4
    assert len(_thumbs(services)) == 4
    assert services.settings.index_path.exists()
    assert progress[0].done == 0 and progress[-1].done == progress[-1].total == 4
    assert services.meta.roots() == [str(photo_dir.resolve())]


def test_second_run_skips_unchanged_files(services: Services, photo_dir: Path):
    services.indexer.index_folder(photo_dir)
    report = services.indexer.index_folder(photo_dir)
    assert (report.added, report.unchanged, report.vectors_added) == (0, 4, 0)
    assert len(services.store) == 4


def test_changed_file_is_reindexed_and_old_thumb_removed(services: Services, photo_dir: Path):
    services.indexer.index_folder(photo_dir)
    before = _thumbs(services)

    path = photo_dir / "blue.jpg"
    make_image(path, (240, 10, 10), size=(80, 80))  # now red, new size
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + 10))

    report = services.indexer.index_folder(photo_dir)
    assert (report.updated, report.unchanged) == (1, 3)
    assert len(services.store) == 4
    after = _thumbs(services)
    assert len(after) == 4 and len(before - after) == 1

    top = services.searcher.search("red", k=4).results
    assert path.resolve().as_posix() in {r.path for r in top[:3]}


def test_deleted_file_is_removed(services: Services, photo_dir: Path):
    services.indexer.index_folder(photo_dir)
    (photo_dir / "green.jpg").unlink()

    report = services.indexer.index_folder(photo_dir)
    assert report.removed == 1
    assert len(services.store) == 3
    assert len(_thumbs(services)) == 3
    assert all("green" not in r.path for r in services.searcher.search("green", k=10).results)


def test_corrupt_file_is_reported_not_fatal(services: Services, photo_dir: Path):
    (photo_dir / "broken.jpg").write_bytes(b"definitely not a jpeg")
    report = services.indexer.index_folder(photo_dir)
    assert report.added == 4
    assert report.failed == [str((photo_dir / "broken.jpg").resolve())]


def test_video_frames_are_sampled_and_deduplicated(services: Services, video_path: Path):
    report = services.indexer.index_folder(video_path.parent)

    assert report.added == 1
    # Frames at 0, 2, 4, 6, 8 s; the repeats at 2 s (red) and 6 s (green) are dropped.
    assert (report.frames_sampled, report.frames_kept) == (5, 3)
    assert len(services.store) == 3 and len(_thumbs(services)) == 3

    rec = next(iter(services.meta.files_under(str(video_path.parent.resolve())).values()))
    assert rec.kind == "video" and (rec.width, rec.height) == (64, 48)
    assert rec.duration == pytest.approx(10.0, abs=0.3)


@pytest.mark.parametrize(("query", "second"), [("red", 0.0), ("yeşil", 4.0), ("blue", 8.0)])
def test_video_search_returns_the_matching_moment(
    services: Services, video_path: Path, query: str, second: float
):
    services.indexer.index_folder(video_path.parent)
    top = services.searcher.search(query, k=1).results[0]
    assert top.kind == "video"
    assert top.timestamp == pytest.approx(second, abs=0.05)
    assert top.moments[0].timestamp == top.timestamp and len(top.moments) == 3


def test_dedup_threshold_above_one_keeps_every_frame(settings, video_path: Path):
    from galeria.core.encoder import FakeEncoder
    from galeria.services import open_services

    settings.frame_dedup_threshold = 1.01
    services = open_services(settings, encoder=FakeEncoder())
    try:
        report = services.indexer.index_folder(video_path.parent)
    finally:
        services.close()
    assert report.frames_kept == report.frames_sampled == 5


def test_changed_video_replaces_all_its_frames(services: Services, video_path: Path):
    services.indexer.index_folder(video_path.parent)
    before = _thumbs(services)

    make_video(video_path, [((30, 40, 220), 3)])  # now a 3 s blue clip
    stat = video_path.stat()
    os.utime(video_path, (stat.st_atime, stat.st_mtime + 10))
    report = services.indexer.index_folder(video_path.parent)

    assert report.updated == 1 and report.frames_kept == 1
    assert len(services.store) == 1
    assert _thumbs(services).isdisjoint(before)


def test_deleted_video_removes_all_its_frames(services: Services, video_path: Path):
    services.indexer.index_folder(video_path.parent)
    video_path.unlink()
    report = services.indexer.index_folder(video_path.parent)
    assert report.removed == 1
    assert len(services.store) == 0 and _thumbs(services) == set()


def test_corrupt_video_is_reported_not_fatal(services: Services, photo_dir: Path):
    (photo_dir / "broken.mp4").write_bytes(b"\x00" * 64)
    report = services.indexer.index_folder(photo_dir)
    assert report.added == 4
    assert report.failed == [str((photo_dir / "broken.mp4").resolve())]
    assert len(_thumbs(services)) == 4


def test_photos_and_videos_together(services: Services, photo_dir: Path, video_path: Path):
    video = photo_dir / "clip.mp4"
    video_path.rename(video)
    progress = []
    report = services.indexer.index_folder(photo_dir, progress.append)
    assert report.added == 5 and len(services.store) == 4 + 3
    assert [p.done for p in progress] == [0, 2, 4, 5]  # two photo batches of 2, then the video
    kinds = {r.kind for r in services.searcher.search("red", k=10).results}
    assert kinds == {"photo", "video"}


def test_photo_dimensions_are_stored(services: Services, photo_dir: Path):
    services.indexer.index_folder(photo_dir)
    rec = services.meta.files_under(str(photo_dir.resolve()))[
        str((photo_dir / "red.jpg").resolve())
    ]
    assert (rec.width, rec.height) == (64, 48)


def test_reconcile_recovers_from_lost_vectors(services: Services, photo_dir: Path):
    services.indexer.index_folder(photo_dir)
    # Simulate a crash where SQLite committed but FAISS lost two vectors.
    services.store.remove(services.store.ids()[:2].tolist())

    report = services.indexer.index_folder(photo_dir)
    assert report.added == 2 and report.unchanged == 2
    assert len(services.store) == 4
    assert set(services.store.ids().tolist()) == services.meta.all_vector_ids()


def test_own_thumbnails_are_not_indexed(services: Services, tmp_path: Path):
    # The data dir lives inside the indexed folder here.
    make_image(tmp_path / "photo.jpg", (10, 10, 10))
    services.indexer.index_folder(tmp_path)
    report = services.indexer.index_folder(tmp_path)
    assert report.added == 0 and report.unchanged == 1
