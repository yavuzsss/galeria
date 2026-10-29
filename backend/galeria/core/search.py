"""Query path: text -> embedding -> FAISS top-k -> metadata -> one result per file."""

import time
from dataclasses import dataclass, field

from galeria.core.encoder import Encoder
from galeria.core.metadata import MetadataStore
from galeria.core.scanner import MediaKind
from galeria.core.vector_store import VectorStore


@dataclass
class Moment:
    timestamp: float
    score: float
    thumb: str


@dataclass
class SearchResult:
    file_id: int
    vector_id: int
    path: str
    kind: MediaKind
    score: float
    thumb: str
    timestamp: float | None
    width: int | None
    height: int | None
    duration: float | None
    # For videos: every matching frame of this file, best first (the first one is the result).
    moments: list[Moment] = field(default_factory=list)


@dataclass
class SearchResponse:
    query: str
    results: list[SearchResult]
    encode_ms: float
    search_ms: float
    took_ms: float
    total_vectors: int
    min_score: float | None = None


class Searcher:
    def __init__(
        self,
        encoder: Encoder,
        store: VectorStore,
        meta: MetadataStore,
        min_score: float | None = None,
    ):
        self.encoder = encoder
        self.store = store
        self.meta = meta
        self.min_score = min_score

    def search(
        self,
        query: str,
        k: int = 24,
        kind: MediaKind | None = None,
        min_score: float | None = None,
    ) -> SearchResponse:
        """Best k files for `query`. `min_score` (or the searcher's default) drops weak hits."""
        started = time.perf_counter()
        query = query.strip()
        total = len(self.store)
        cutoff = self.min_score if min_score is None else min_score
        if not query or total == 0:
            return SearchResponse(query, [], 0.0, 0.0, 0.0, total, cutoff)

        vector = self.encoder.encode_texts([query])[0]
        encoded = time.perf_counter()

        # Several hits can belong to one video and a kind filter drops some, so fetch more
        # than k and widen the window until k distinct files are found or the index runs out.
        fetch = min(total, max(k * 4, 64))
        while True:
            hits = self.store.search(vector, fetch)
            if cutoff is not None:
                hits = [(vid, score) for vid, score in hits if score >= cutoff]
            results = self._group(hits, kind)
            # Hits arrive best first, so once one falls below the cutoff, fetching further
            # cannot add anything.
            below_cutoff = len(hits) < fetch
            if len(results) >= k or fetch >= total or below_cutoff:
                break
            fetch = min(total, fetch * 4)

        finished = time.perf_counter()
        return SearchResponse(
            query=query,
            results=results[:k],
            encode_ms=(encoded - started) * 1000,
            search_ms=(finished - encoded) * 1000,
            took_ms=(finished - started) * 1000,
            total_vectors=total,
            min_score=cutoff,
        )

    def _group(self, hits: list[tuple[int, float]], kind: MediaKind | None) -> list[SearchResult]:
        rows = self.meta.vector_rows([vid for vid, _ in hits])
        by_file: dict[int, SearchResult] = {}  # insertion order == best score first
        for vid, score in hits:
            row = rows.get(vid)
            if row is None or (kind and row.kind != kind):
                continue
            result = by_file.get(row.file_id)
            if result is None:
                result = by_file[row.file_id] = SearchResult(
                    file_id=row.file_id,
                    vector_id=vid,
                    path=row.path,
                    kind=row.kind,
                    score=score,
                    thumb=row.thumb,
                    timestamp=row.timestamp,
                    width=row.width,
                    height=row.height,
                    duration=row.duration,
                )
            if row.timestamp is not None:
                result.moments.append(Moment(row.timestamp, score, row.thumb))
        return list(by_file.values())
