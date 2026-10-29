import { useEffect, useRef } from "react";

import { mediaUrlAt, type SearchResult } from "../api";
import { formatTime } from "../format";

interface Props {
  results: SearchResult[];
  index: number;
  onIndex: (index: number) => void;
  onClose: () => void;
}

export function MediaViewer({ results, index, onIndex, onClose }: Props) {
  const result = results[index];
  const video = useRef<HTMLVideoElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight" && index < results.length - 1) onIndex(index + 1);
      if (e.key === "ArrowLeft" && index > 0) onIndex(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, results.length, onIndex, onClose]);

  // Keep keyboard focus inside the dialog and stop the page behind it from scrolling.
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeButton.current?.focus();
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
      previous?.focus();
    };
  }, []);

  if (!result) return null;

  const seek = (timestamp: number) => {
    if (!video.current) return;
    video.current.currentTime = timestamp;
    void video.current.play().catch(() => {});
  };

  return (
    <div
      className="viewer"
      role="dialog"
      aria-modal="true"
      aria-label={result.name}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="viewer__bar">
        <div className="viewer__title">
          <strong>{result.name}</strong>
          <span>{result.path}</span>
        </div>
        <span className="viewer__count">
          {index + 1} / {results.length}
        </span>
        <button ref={closeButton} type="button" className="icon-button" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>

      <div className="viewer__stage" onClick={(e) => e.target === e.currentTarget && onClose()}>
        <button
          type="button"
          className="viewer__nav viewer__nav--prev"
          onClick={() => onIndex(index - 1)}
          disabled={index === 0}
          aria-label="Previous result"
        >
          ‹
        </button>
        {result.kind === "video" ? (
          <video
            key={result.id}
            ref={video}
            src={mediaUrlAt(result)}
            controls
            autoPlay
            playsInline
            poster={result.thumb_url}
          />
        ) : (
          <img key={result.id} src={result.media_url} alt={result.name} />
        )}
        <button
          type="button"
          className="viewer__nav viewer__nav--next"
          onClick={() => onIndex(index + 1)}
          disabled={index === results.length - 1}
          aria-label="Next result"
        >
          ›
        </button>
      </div>

      {result.kind === "video" && result.moments.length > 0 && (
        <div className="moments" aria-label="Matching moments">
          <span className="moments__label">Matching moments</span>
          <ol>
            {result.moments.map((m) => (
              <li key={m.timestamp}>
                <button type="button" onClick={() => seek(m.timestamp)} aria-label={`Jump to ${formatTime(m.timestamp)}`}>
                  <img src={m.thumb_url} alt="" loading="lazy" />
                  <span>
                    {formatTime(m.timestamp)} · {m.score.toFixed(3)}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
