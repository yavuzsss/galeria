import pytest

from galeria.core.metadata import MetadataStore, NewVector


@pytest.fixture
def meta(tmp_path):
    m = MetadataStore(tmp_path / "meta.sqlite")
    yield m
    m.close()


def test_add_media_and_join_vector_rows(meta: MetadataStore):
    file_id, vids = meta.add_media(
        "/lib/clip.mp4", "video", 100, 1.5,
        [NewVector(0.0, "a.jpg"), NewVector(2.0, "b.jpg")],
        width=640, height=360, duration=4.0,
    )  # fmt: skip
    rows = meta.vector_rows(vids)
    assert [rows[v].timestamp for v in vids] == [0.0, 2.0]
    assert rows[vids[1]].path == "/lib/clip.mp4"
    assert rows[vids[1]].file_id == file_id
    assert rows[vids[1]].kind == "video"
    assert meta.counts() == {"photos": 0, "videos": 1, "vectors": 2}


def test_files_under_matches_only_that_folder(meta: MetadataStore):
    for path in ["/lib/a.jpg", "/lib/sub/b.jpg", "/library/c.jpg", "/li.jpg"]:
        meta.add_media(path, "photo", 1, 1.0, [NewVector(None, path + ".thumb")])
    assert sorted(meta.files_under("/lib")) == ["/lib/a.jpg", "/lib/sub/b.jpg"]
    assert sorted(meta.files_under("/lib/")) == ["/lib/a.jpg", "/lib/sub/b.jpg"]


def test_delete_files_cascades_and_returns_thumbs(meta: MetadataStore):
    keep, _ = meta.add_media("/a.jpg", "photo", 1, 1.0, [NewVector(None, "a.jpg")])
    gone, vids = meta.add_media("/v.mp4", "video", 1, 1.0, [NewVector(0, "v0"), NewVector(2, "v2")])
    removed = meta.delete_files([gone])
    assert sorted(removed) == sorted(zip(vids, ["v0", "v2"], strict=True))
    assert meta.get_file(gone) is None
    assert meta.get_file(keep) is not None
    assert meta.vector_rows(vids) == {}
    assert meta.delete_files([]) == []


def test_meta_and_roots(meta: MetadataStore):
    assert meta.get_meta("encoder") is None
    meta.set_meta("encoder", "x")
    meta.set_meta("encoder", "y")
    assert meta.get_meta("encoder") == "y"
    meta.add_root("/b")
    meta.add_root("/a")
    meta.add_root("/a")
    assert meta.roots() == ["/a", "/b"]


def test_file_ids_for_vectors(meta: MetadataStore):
    f1, v1 = meta.add_media("/1.jpg", "photo", 1, 1.0, [NewVector(None, "1")])
    f2, v2 = meta.add_media("/2.mp4", "video", 1, 1.0, [NewVector(0, "2a"), NewVector(1, "2b")])
    assert meta.file_ids_for_vectors(v2) == {f2}
    assert meta.file_ids_for_vectors(v1 + v2[:1]) == {f1, f2}
    assert meta.all_vector_ids() == set(v1 + v2)
