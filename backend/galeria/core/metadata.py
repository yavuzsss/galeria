"""SQLite metadata: which files are indexed and what each FAISS vector id points to.

One file has one vector (photo) or many (video frames). `vectors.id` is the FAISS id.
"""

import sqlite3
import threading
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from galeria.core.scanner import MediaKind

SCHEMA = """
CREATE TABLE IF NOT EXISTS roots (
    path TEXT PRIMARY KEY,
    added_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('photo', 'video')),
    size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    width INTEGER,
    height INTEGER,
    duration REAL,
    indexed_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS vectors (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    timestamp REAL,
    thumb TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vectors_file ON vectors(file_id);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class FileRecord:
    id: int
    path: str
    kind: MediaKind
    size: int
    mtime: float
    width: int | None
    height: int | None
    duration: float | None


@dataclass(frozen=True)
class VectorRecord:
    id: int
    file_id: int
    timestamp: float | None
    thumb: str
    path: str
    kind: MediaKind
    width: int | None
    height: int | None
    duration: float | None


@dataclass(frozen=True)
class NewVector:
    timestamp: float | None
    thumb: str


class MetadataStore:
    def __init__(self, path: Path | str):
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    def close(self) -> None:
        self._conn.close()

    def _fetch(self, sql: str, params: Sequence = ()) -> list[sqlite3.Row]:
        # One connection is shared by the API and the background indexer thread.
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # --- meta / roots -------------------------------------------------------------------

    def get_meta(self, key: str) -> str | None:
        rows = self._fetch("SELECT value FROM meta WHERE key = ?", (key,))
        return rows[0]["value"] if rows else None

    def set_meta(self, key: str, value: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def add_root(self, root: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO roots (path, added_at) VALUES (?, ?)", (root, time.time())
            )

    def roots(self) -> list[str]:
        return [r["path"] for r in self._fetch("SELECT path FROM roots ORDER BY path")]

    # --- files --------------------------------------------------------------------------

    def files_under(self, root: str) -> dict[str, FileRecord]:
        """All indexed files whose path is inside `root` (prefix range scan on the unique index)."""
        root = root.rstrip("/")
        # '0' is the character right after '/', so [root/, root0) is exactly the paths under root.
        rows = self._fetch(
            "SELECT * FROM files WHERE path >= ? AND path < ?", (root + "/", root + "0")
        )
        return {r["path"]: _file(r) for r in rows}

    def get_file(self, file_id: int) -> FileRecord | None:
        rows = self._fetch("SELECT * FROM files WHERE id = ?", (file_id,))
        return _file(rows[0]) if rows else None

    def add_media(
        self,
        path: str,
        kind: MediaKind,
        size: int,
        mtime: float,
        vectors: Sequence[NewVector],
        width: int | None = None,
        height: int | None = None,
        duration: float | None = None,
    ) -> tuple[int, list[int]]:
        """Insert a file and its vectors in one transaction; return (file_id, vector_ids)."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO files (path, kind, size, mtime, width, height, duration, indexed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (path, kind, size, mtime, width, height, duration, time.time()),
            )
            file_id = cur.lastrowid
            vector_ids = []
            for v in vectors:
                cur = self._conn.execute(
                    "INSERT INTO vectors (file_id, timestamp, thumb) VALUES (?, ?, ?)",
                    (file_id, v.timestamp, v.thumb),
                )
                vector_ids.append(cur.lastrowid)
        return file_id, vector_ids

    def delete_files(self, file_ids: Iterable[int]) -> list[tuple[int, str]]:
        """Delete files and their vectors; return the removed (vector_id, thumb) pairs."""
        file_ids = list(file_ids)
        if not file_ids:
            return []
        removed: list[tuple[int, str]] = []
        with self._lock, self._conn:
            for chunk in _chunks(file_ids, 500):
                marks = ",".join("?" * len(chunk))
                rows = self._conn.execute(
                    f"SELECT id, thumb FROM vectors WHERE file_id IN ({marks})", chunk
                )
                removed.extend((r["id"], r["thumb"]) for r in rows)
                self._conn.execute(f"DELETE FROM files WHERE id IN ({marks})", chunk)
        return removed

    # --- vectors ------------------------------------------------------------------------

    def vector_rows(self, vector_ids: Sequence[int]) -> dict[int, VectorRecord]:
        out: dict[int, VectorRecord] = {}
        for chunk in _chunks(list(vector_ids), 500):
            marks = ",".join("?" * len(chunk))
            rows = self._fetch(
                "SELECT v.id, v.file_id, v.timestamp, v.thumb, "
                "f.path, f.kind, f.width, f.height, f.duration "
                f"FROM vectors v JOIN files f ON f.id = v.file_id WHERE v.id IN ({marks})",
                chunk,
            )
            for r in rows:
                out[r["id"]] = VectorRecord(**dict(r))
        return out

    def all_vector_ids(self) -> set[int]:
        return {r[0] for r in self._fetch("SELECT id FROM vectors")}

    def file_ids_for_vectors(self, vector_ids: Iterable[int]) -> set[int]:
        out: set[int] = set()
        for chunk in _chunks(list(vector_ids), 500):
            marks = ",".join("?" * len(chunk))
            rows = self._fetch(f"SELECT DISTINCT file_id FROM vectors WHERE id IN ({marks})", chunk)
            out.update(r[0] for r in rows)
        return out

    def counts(self) -> dict[str, int]:
        row = self._fetch(
            "SELECT "
            "(SELECT COUNT(*) FROM files WHERE kind = 'photo') AS photos, "
            "(SELECT COUNT(*) FROM files WHERE kind = 'video') AS videos, "
            "(SELECT COUNT(*) FROM vectors) AS vectors"
        )[0]
        return dict(row)


def _file(row: sqlite3.Row) -> FileRecord:
    return FileRecord(
        id=row["id"],
        path=row["path"],
        kind=row["kind"],
        size=row["size"],
        mtime=row["mtime"],
        width=row["width"],
        height=row["height"],
        duration=row["duration"],
    )


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]
