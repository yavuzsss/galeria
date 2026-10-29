import numpy as np
import pytest

from galeria.core.encoder import l2_normalize
from galeria.core.vector_store import VectorStore


def _unit(*values: float) -> np.ndarray:
    return l2_normalize(np.array([values], dtype=np.float32))


@pytest.fixture
def store() -> VectorStore:
    s = VectorStore(dim=3)
    s.add([10, 20, 30], np.vstack([_unit(1, 0, 0), _unit(0, 1, 0), _unit(1, 1, 0)]))
    return s


def test_search_returns_ids_ranked_by_cosine(store: VectorStore):
    hits = store.search(_unit(1, 0.1, 0)[0], k=3)
    assert [vid for vid, _ in hits] == [10, 30, 20]
    assert hits[0][1] == pytest.approx(0.995, abs=1e-3)


def test_search_caps_k_and_handles_empty_store(store: VectorStore):
    assert len(store.search(_unit(1, 0, 0)[0], k=100)) == 3
    assert VectorStore(dim=3).search(_unit(1, 0, 0)[0], k=5) == []


def test_remove_drops_vectors(store: VectorStore):
    assert store.remove([10, 999]) == 1
    assert len(store) == 2
    assert sorted(store.ids().tolist()) == [20, 30]
    assert [vid for vid, _ in store.search(_unit(1, 0, 0)[0], k=3)] == [30, 20]


def test_save_and_load_roundtrip(store: VectorStore, tmp_path):
    path = tmp_path / "idx" / "index.faiss"
    store.save(path)
    assert not path.with_suffix(".faiss.tmp").exists()
    loaded = VectorStore.load(path, dim=3)
    assert len(loaded) == 3
    assert loaded.search(_unit(0, 1, 0)[0], k=1)[0][0] == 20


def test_load_rejects_dimension_mismatch(store: VectorStore, tmp_path):
    path = tmp_path / "index.faiss"
    store.save(path)
    with pytest.raises(ValueError, match="dimension"):
        VectorStore.load(path, dim=512)


def test_add_validates_shape(store: VectorStore):
    with pytest.raises(ValueError):
        store.add([1, 2], _unit(1, 0, 0))
