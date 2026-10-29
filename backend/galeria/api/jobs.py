"""Runs one indexing job at a time on a background thread and tracks its progress."""

import logging
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from galeria.core.indexer import Indexer, IndexReport, Progress

log = logging.getLogger(__name__)


class JobAlreadyRunning(RuntimeError):
    pass


@dataclass(frozen=True)
class JobStatus:
    state: Literal["idle", "running", "done", "failed"] = "idle"
    folder: str | None = None
    done: int = 0
    total: int = 0
    current: str | None = None
    report: IndexReport | None = None
    error: str | None = None


class IndexJobs:
    def __init__(self, indexer: Indexer):
        self._indexer = indexer
        self._lock = threading.Lock()
        self._status = JobStatus()
        self._thread: threading.Thread | None = None

    @property
    def status(self) -> JobStatus:
        with self._lock:
            return self._status

    def start(self, folder: Path) -> JobStatus:
        with self._lock:
            if self._status.state == "running":
                raise JobAlreadyRunning(self._status.folder)
            self._status = JobStatus(state="running", folder=str(folder))
            self._thread = threading.Thread(
                target=self._run, args=(folder,), name="galeria-index", daemon=True
            )
            self._thread.start()
            return self._status

    def wait(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread:
            thread.join(timeout)

    def _run(self, folder: Path) -> None:
        try:
            report = self._indexer.index_folder(folder, self._on_progress)
        except Exception as exc:
            log.exception("indexing %s failed", folder)
            self._update(state="failed", error=str(exc), current=None)
        else:
            self._update(state="done", report=report, current=None)

    def _on_progress(self, p: Progress) -> None:
        self._update(done=p.done, total=p.total, current=p.current)

    def _update(self, **changes) -> None:
        with self._lock:
            self._status = replace(self._status, **changes)
