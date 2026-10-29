from pathlib import Path

import numpy as np
import pytest

from galeria.config import Settings
from galeria.core.encoder import FakeEncoder, l2_normalize
from galeria.core.metadata import NewVector
from galeria.services import EncoderMismatchError, Services, open_services


@pytest.fixture
def indexed(services: Services, photo_dir: Path) -> Services:
    services.indexer.index_folder(photo_dir)
    return services


@pytest.mark.parametrize(
    ("query", "expected"),
    [("red", "red"), ("kırmızı", "red"), ("green", "green"), ("mavi", "blue")],
)
def test_color_query_ranks_matching_photo_first(indexed: Services, query, expected):
    top = indexed.searcher.search(query, k=1).results[0]
    assert Path(top.path).stem.startswith(expected)
    assert top.kind == "photo" and top.timestamp is None and top.thumb.endswith(".jpg")


def test_results_are_sorted_and_limited(indexed: Services):
    response = indexed.searcher.search("red", k=2)
    assert len(response.results) == 2
    assert {Path(r.path).stem for r in response.results} == {"red", "red2"}
    scores = [r.score for r in response.results]
    assert scores == sorted(scores, reverse=True)
    assert response.total_vectors == 4
    assert response.took_ms >= response.encode_ms >= 0


def test_empty_index_returns_nothing(services: Services):
    response = services.searcher.search("red")
    assert response.results == [] and response.total_vectors == 0


def test_blank_query_returns_nothing(indexed: Services):
    assert indexed.searcher.search("   ").results == []


def test_kind_filter(indexed: Services):
    assert indexed.searcher.search("red", kind="video").results == []
    assert len(indexed.searcher.search("red", kind="photo").results) == 4


def test_video_frames_are_grouped_into_one_result(indexed: Services):
    # Insert a fake video with three frames directly, the way milestone 2 will.
    blue, red, green = indexed.encoder.encode_texts(["blue", "red", "green"])
    frames = l2_normalize(np.vstack([blue, red, red * 0.9 + green * 0.1]))
    _, vids = indexed.meta.add_media(
        "/videos/clip.mp4", "video", 1, 1.0,
        [NewVector(0.0, "f0.jpg"), NewVector(2.0, "f2.jpg"), NewVector(4.0, "f4.jpg")],
        duration=6.0,
    )  # fmt: skip
    indexed.store.add(vids, frames)

    results = indexed.searcher.search("red", k=10).results
    videos = [r for r in results if r.kind == "video"]
    assert len(videos) == 1
    video = videos[0]
    assert video.timestamp == 2.0 and video.thumb == "f2.jpg"
    assert [m.timestamp for m in video.moments][:2] == [2.0, 4.0]
    assert len(results) == 5  # 4 photos + 1 video, not 4 + 3 frames


def test_opening_with_a_different_encoder_is_refused(settings: Settings, services: Services):
    class OtherEncoder(FakeEncoder):
        name = "other"

    with pytest.raises(EncoderMismatchError, match="fake-color-encoder"):
        open_services(settings, encoder=OtherEncoder())


def test_min_score_hides_weak_matches(indexed: Services):
    everything = indexed.searcher.search("red", k=10).results
    assert len(everything) == 4 and everything[-1].score < 0.5  # blue and green are far away

    strong = indexed.searcher.search("red", k=10, min_score=0.9)
    assert strong.min_score == 0.9
    assert {Path(r.path).stem for r in strong.results} == {"red", "red2"}
    assert all(r.score >= 0.9 for r in strong.results)
    assert indexed.searcher.search("red", min_score=0.9999).results == []


def test_min_score_default_comes_from_the_searcher(indexed: Services):
    indexed.searcher.min_score = 0.9
    assert len(indexed.searcher.search("red", k=10).results) == 2
    # An explicit value wins over the default, including a looser one.
    assert len(indexed.searcher.search("red", k=10, min_score=-1).results) == 4
    assert indexed.searcher.search("red").min_score == 0.9
