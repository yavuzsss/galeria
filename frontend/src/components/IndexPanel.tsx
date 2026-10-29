import { useEffect, useRef, useState } from "react";

import { api, type JobStatus } from "../api";
import { plural } from "../format";

const POLL_MS = 500;

interface Props {
  roots: string[];
  allowedRoots: string[];
  onClose: () => void;
  onFinished: () => void;
}

export function IndexPanel({ roots, allowedRoots, onClose, onFinished }: Props) {
  // In Docker only the mounted media folder may be indexed, so offer it up front.
  const [folder, setFolder] = useState(roots[0] ?? allowedRoots[0] ?? "");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wasRunning = useRef(false);

  // Poll while a job runs. The first poll also picks up a job started before the page loaded.
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const status = await api.indexStatus();
        if (cancelled) return;
        setJob(status);
        if (status.state === "running") {
          wasRunning.current = true;
          timer = setTimeout(poll, POLL_MS);
        } else if (wasRunning.current) {
          wasRunning.current = false;
          onFinished();
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    };
    if (job === null || job.state === "running") void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // Re-run only on mount and when a job starts (the boolean flips to true).
  }, [job?.state === "running"]);

  const start = async (path: string) => {
    setError(null);
    try {
      setJob(await api.startIndex(path.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const running = job?.state === "running";
  const percent = job && job.total > 0 ? Math.round((job.done / job.total) * 100) : 0;

  return (
    <aside className="panel" aria-label="Index a folder">
      <div className="panel__head">
        <h2>Index a folder</h2>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close panel">
          ×
        </button>
      </div>
      <p className="muted">
        Photos and videos are embedded with multilingual CLIP. Re-running a folder only processes
        new, changed and deleted files.
      </p>

      <form
        className="panel__form"
        onSubmit={(e) => {
          e.preventDefault();
          void start(folder);
        }}
      >
        <label htmlFor="folder">Folder path on the server</label>
        <input
          id="folder"
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
          placeholder={allowedRoots[0] ?? "/Users/me/Pictures"}
          spellCheck={false}
          disabled={running}
        />
        {allowedRoots.length > 0 && (
          <p className="muted panel__hint">Allowed: {allowedRoots.join(", ")}</p>
        )}
        <button type="submit" className="primary" disabled={running || !folder.trim()}>
          {running ? "Indexing…" : "Start indexing"}
        </button>
      </form>

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}

      {running && job && (
        <div className="progress" role="status">
          <div className="progress__track">
            <div className="progress__fill" style={{ width: `${percent}%` }} />
          </div>
          <div className="progress__text">
            <span>
              {job.done} / {job.total} files
            </span>
            <span>{percent}%</span>
          </div>
          {job.current && <p className="progress__current">{job.current}</p>}
        </div>
      )}

      {job?.state === "done" && job.report && (
        <div className="report" role="status">
          <strong>Done in {job.report.seconds.toFixed(1)} s</strong>
          <ul>
            <li>{plural(job.report.added, "new file")}</li>
            {job.report.updated > 0 && <li>{plural(job.report.updated, "changed file")}</li>}
            {job.report.removed > 0 && <li>{plural(job.report.removed, "removed file")}</li>}
            <li>{job.report.unchanged} unchanged</li>
            {job.report.frames_sampled > 0 && (
              <li>
                {job.report.frames_kept} of {job.report.frames_sampled} video frames kept
              </li>
            )}
          </ul>
          {job.report.failed.length > 0 && (
            <details>
              <summary>{plural(job.report.failed.length, "file")} could not be read</summary>
              <ul className="report__failed">
                {job.report.failed.map((path) => (
                  <li key={path}>{path}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {job?.state === "failed" && (
        <p className="alert" role="alert">
          Indexing failed: {job.error}
        </p>
      )}

      {roots.length > 0 && (
        <div className="roots">
          <h3>Indexed folders</h3>
          <ul>
            {roots.map((root) => (
              <li key={root}>
                <span title={root}>
                  <bdi>{root}</bdi>
                </span>
                <button type="button" onClick={() => void start(root)} disabled={running}>
                  Re-index
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
