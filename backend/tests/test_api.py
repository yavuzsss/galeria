import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from galeria.api.main import create_app
from galeria.config import Settings
from galeria.core.encoder import FakeEncoder


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings, encoder=FakeEncoder())) as c:
        yield c


def _index(client: TestClient, folder: Path) -> dict:
    response = client.post("/api/index", json={"folder": str(folder)})
    assert response.status_code == 202, response.text
    assert response.json()["state"] == "running"
    client.app.state.jobs.wait(timeout=10)
    return client.get("/api/index/status").json()


def test_health_and_empty_stats(client: TestClient):
    assert client.get("/api/health").json() == {"status": "ok"}
    stats = client.get("/api/stats").json()
    assert stats == {
        "photos": 0, "videos": 0, "vectors": 0, "encoder": "fake-color-encoder", "roots": [],
        "allowed_roots": [],
    }  # fmt: skip
    assert client.get("/api/index/status").json()["state"] == "idle"


def test_index_then_search(client: TestClient, photo_dir: Path, video_path: Path):
    video_path.rename(photo_dir / "clip.mp4")
    status = _index(client, photo_dir)
    assert status["state"] == "done"
    assert (status["done"], status["total"]) == (5, 5)
    assert status["report"]["added"] == 5 and status["report"]["frames_kept"] == 3

    body = client.get("/api/search", params={"q": "kırmızı", "k": 3}).json()
    assert body["query"] == "kırmızı" and body["total_vectors"] == 7
    assert body["took_ms"] >= 0
    names = [r["name"] for r in body["results"]]
    assert len(names) == 3 and set(names) == {"red.jpg", "red2.png", "clip.mp4"}

    video = client.get("/api/search", params={"q": "green", "type": "video"}).json()["results"]
    assert len(video) == 1
    assert video[0]["timestamp"] == pytest.approx(4.0, abs=0.05)
    assert video[0]["media_url"] == f"/api/media/{video[0]['id']}"
    assert [m["timestamp"] for m in video[0]["moments"]][0] == video[0]["timestamp"]
    assert video[0]["duration"] == pytest.approx(10.0, abs=0.3)

    stats = client.get("/api/stats").json()
    assert (stats["photos"], stats["videos"], stats["vectors"]) == (4, 1, 7)


def test_thumbnails_are_served_with_long_cache(client: TestClient, photo_dir: Path):
    _index(client, photo_dir)
    result = client.get("/api/search", params={"q": "blue"}).json()["results"][0]
    response = client.get(result["thumb_url"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert "immutable" in response.headers["cache-control"]


@pytest.mark.parametrize("name", ["..%2Fmeta.sqlite", "meta.sqlite", "0" * 20 + ".png", "x.jpg"])
def test_thumbnail_names_are_validated(client: TestClient, name: str):
    assert client.get(f"/api/thumbs/{name}").status_code == 404


def test_media_supports_range_requests(client: TestClient, video_path: Path):
    _index(client, video_path.parent)
    result = client.get("/api/search", params={"q": "red"}).json()["results"][0]
    size = video_path.stat().st_size

    full = client.get(result["media_url"])
    assert full.status_code == 200 and full.headers["content-type"] == "video/mp4"
    assert len(full.content) == size

    part = client.get(result["media_url"], headers={"Range": "bytes=0-99"})
    assert part.status_code == 206
    assert part.headers["content-range"] == f"bytes 0-99/{size}"
    assert part.content == full.content[:100]


def test_media_errors(client: TestClient, photo_dir: Path):
    assert client.get("/api/media/999").status_code == 404
    _index(client, photo_dir)
    result = client.get("/api/search", params={"q": "red"}).json()["results"][0]
    Path(result["path"]).unlink()
    assert client.get(result["media_url"]).status_code == 404


@pytest.mark.parametrize(
    "params",
    [{"q": ""}, {"q": "x", "k": 0}, {"q": "x", "k": 1000}, {"q": "x", "type": "audio"}, {}],
)
def test_search_validation(client: TestClient, params: dict):
    assert client.get("/api/search", params=params).status_code == 422


def test_index_rejects_missing_folder(client: TestClient, tmp_path: Path):
    response = client.post("/api/index", json={"folder": str(tmp_path / "nope")})
    assert response.status_code == 400


def test_index_respects_allowed_roots(settings: Settings, photo_dir: Path, tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    settings.allowed_roots = [allowed]
    with TestClient(create_app(settings, encoder=FakeEncoder())) as client:
        assert client.get("/api/stats").json()["allowed_roots"] == [str(allowed)]
        assert client.post("/api/index", json={"folder": str(photo_dir)}).status_code == 403
        assert client.post("/api/index", json={"folder": str(allowed)}).status_code == 202


def test_second_index_request_while_running_is_rejected(settings: Settings, photo_dir: Path):
    release = threading.Event()

    class SlowEncoder(FakeEncoder):
        def encode_images(self, images):
            release.wait(timeout=10)
            return super().encode_images(images)

    with TestClient(create_app(settings, encoder=SlowEncoder())) as client:
        assert client.post("/api/index", json={"folder": str(photo_dir)}).status_code == 202
        second = client.post("/api/index", json={"folder": str(photo_dir)})
        assert second.status_code == 409
        # Search keeps working while the indexer is busy.
        assert client.get("/api/search", params={"q": "red"}).status_code == 200
        release.set()
        client.app.state.jobs.wait(timeout=10)
        assert client.get("/api/index/status").json()["state"] == "done"


def test_failed_job_reports_error(settings: Settings, photo_dir: Path):
    class BrokenEncoder(FakeEncoder):
        def encode_images(self, images):
            raise RuntimeError("GPU on fire")

    with TestClient(create_app(settings, encoder=BrokenEncoder())) as client:
        status = _index(client, photo_dir)
    assert status["state"] == "failed" and "GPU on fire" in status["error"]


def test_search_min_score_param(client: TestClient, photo_dir: Path):
    _index(client, photo_dir)
    loose = client.get("/api/search", params={"q": "red"}).json()
    assert loose["min_score"] is None and len(loose["results"]) == 4
    strict = client.get("/api/search", params={"q": "red", "min_score": 0.9}).json()
    assert strict["min_score"] == 0.9
    assert {r["name"] for r in strict["results"]} == {"red.jpg", "red2.png"}
    assert client.get("/api/search", params={"q": "red", "min_score": 2}).status_code == 422


def test_search_min_score_default_from_settings(settings: Settings, photo_dir: Path):
    settings.min_score = 0.9
    with TestClient(create_app(settings, encoder=FakeEncoder())) as client:
        _index(client, photo_dir)
        body = client.get("/api/search", params={"q": "red"}).json()
    assert body["min_score"] == 0.9 and len(body["results"]) == 2
