"""FAISS wrapper.

`IndexFlatIP` over L2-normalized vectors is exact cosine search; brute force over ~100k
512-d vectors still answers in a few milliseconds, so an approximate index is not worth its
recall loss at this scale. `IndexIDMap2` lets us use the SQLite row id as the vector id and
remove vectors when files change or disappear.
"""

import os
import sys
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

import faiss
import numpy as np

_thread_state = threading.local()


def _pin_openmp_threads() -> None:
    """Run faiss single-threaded on macOS (see galeria/__init__.py for why).

    OpenMP thread counts are per calling thread, so this must run in every thread that uses
    faiss: the API's worker threads and the background indexer, not just the main thread.
    """
    if sys.platform == "darwin" and not getattr(_thread_state, "pinned", False):
        faiss.omp_set_num_threads(1)
        _thread_state.pinned = True


class VectorStore:
    def __init__(self, dim: int, index: faiss.Index | None = None):
        self.dim = dim
        self._index = index if index is not None else faiss.IndexIDMap2(faiss.IndexFlatIP(dim))
        self._lock = threading.RLock()  # FAISS is not safe for concurrent add + search

    @classmethod
    def load(cls, path: Path, dim: int | None = None) -> "VectorStore":
        index = faiss.read_index(str(path))
        if dim is not None and index.d != dim:
            raise ValueError(
                f"Index at {path} has dimension {index.d}, but the encoder produces {dim}. "
                "Delete the data directory and re-index."
            )
        return cls(index.d, index)

    @contextmanager
    def _guard(self) -> Iterator[None]:
        _pin_openmp_threads()
        with self._lock:
            yield

    def __len__(self) -> int:
        return self._index.ntotal

    def add(self, ids: Iterable[int], vectors: np.ndarray) -> None:
        ids = np.asarray(list(ids), dtype=np.int64)
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape != (len(ids), self.dim):
            raise ValueError(
                f"expected vectors of shape ({len(ids)}, {self.dim}), got {vectors.shape}"
            )
        with self._guard():
            self._index.add_with_ids(vectors, ids)

    def remove(self, ids: Iterable[int]) -> int:
        ids = np.asarray(list(ids), dtype=np.int64)
        if ids.size == 0:
            return 0
        with self._guard():
            return int(self._index.remove_ids(ids))

    def search(self, query: np.ndarray, k: int) -> list[tuple[int, float]]:
        """Return up to `k` (id, cosine score) pairs, best first."""
        with self._guard():
            k = min(k, self._index.ntotal)
            if k <= 0:
                return []
            query = np.ascontiguousarray(query, dtype=np.float32).reshape(1, -1)
            scores, ids = self._index.search(query, k)
        return [(int(i), float(s)) for i, s in zip(ids[0], scores[0], strict=True) if i != -1]

    def ids(self) -> np.ndarray:
        with self._guard():
            return faiss.vector_to_array(self._index.id_map).astype(np.int64)

    def save(self, path: Path) -> None:
        # Write next to the target and rename, so a crash never leaves a half-written index.
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with self._guard():
            faiss.write_index(self._index, str(tmp))
        os.replace(tmp, path)
