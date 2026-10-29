from typing import Literal

from pydantic import BaseModel, Field

from galeria.core.indexer import IndexReport
from galeria.core.search import SearchResponse, SearchResult


class MomentOut(BaseModel):
    timestamp: float
    score: float
    thumb_url: str


class ResultOut(BaseModel):
    id: int = Field(description="File id; use it with /api/media/{id}")
    kind: Literal["photo", "video"]
    name: str
    path: str
    score: float
    thumb_url: str
    media_url: str
    timestamp: float | None = Field(description="Best matching second, videos only")
    width: int | None
    height: int | None
    duration: float | None
    moments: list[MomentOut] = Field(description="All matching frames of a video, best first")

    @classmethod
    def from_result(cls, r: SearchResult) -> "ResultOut":
        return cls(
            id=r.file_id,
            kind=r.kind,
            name=r.path.rsplit("/", 1)[-1],
            path=r.path,
            score=round(r.score, 4),
            thumb_url=thumb_url(r.thumb),
            media_url=f"/api/media/{r.file_id}",
            timestamp=r.timestamp,
            width=r.width,
            height=r.height,
            duration=r.duration,
            moments=[
                MomentOut(
                    timestamp=m.timestamp, score=round(m.score, 4), thumb_url=thumb_url(m.thumb)
                )
                for m in r.moments
            ],
        )


class SearchOut(BaseModel):
    query: str
    took_ms: float
    encode_ms: float
    search_ms: float
    total_vectors: int
    min_score: float | None = Field(description="Score cutoff applied, if any")
    results: list[ResultOut]

    @classmethod
    def from_response(cls, r: SearchResponse) -> "SearchOut":
        return cls(
            query=r.query,
            took_ms=round(r.took_ms, 2),
            encode_ms=round(r.encode_ms, 2),
            search_ms=round(r.search_ms, 2),
            total_vectors=r.total_vectors,
            min_score=r.min_score,
            results=[ResultOut.from_result(x) for x in r.results],
        )


class IndexRequest(BaseModel):
    folder: str = Field(min_length=1, examples=["/Users/me/Pictures"])


class ReportOut(BaseModel):
    root: str
    added: int
    updated: int
    removed: int
    unchanged: int
    vectors_added: int
    frames_sampled: int
    frames_kept: int
    failed: list[str]
    seconds: float

    @classmethod
    def from_report(cls, r: IndexReport) -> "ReportOut":
        return cls(**{name: getattr(r, name) for name in cls.model_fields})


class JobOut(BaseModel):
    state: Literal["idle", "running", "done", "failed"]
    folder: str | None = None
    done: int = 0
    total: int = 0
    current: str | None = None
    report: ReportOut | None = None
    error: str | None = None


class StatsOut(BaseModel):
    photos: int
    videos: int
    vectors: int
    encoder: str
    roots: list[str]
    allowed_roots: list[str] = Field(description="Folders POST /api/index accepts; empty = any")


def thumb_url(name: str) -> str:
    return f"/api/thumbs/{name}"
