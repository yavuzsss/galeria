import type { SearchResult } from "../api";
import { formatTime } from "../format";

interface Props {
  result: SearchResult;
  rank: number;
  onOpen: () => void;
}

export function ResultCard({ result, rank, onOpen }: Props) {
  const isVideo = result.kind === "video";
  const label = isVideo
    ? `${result.name}, video, best match at ${formatTime(result.timestamp ?? 0)}`
    : result.name;

  return (
    <button type="button" className="card" onClick={onOpen} aria-label={`Open ${label}`}>
      <img src={result.thumb_url} alt="" loading={rank < 12 ? "eager" : "lazy"} decoding="async" />
      {isVideo && (
        <span className="card__badge">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M8 5v14l11-7z" />
          </svg>
          {formatTime(result.timestamp ?? 0)}
          {result.moments.length > 1 && (
            <span className="card__more">+{result.moments.length - 1}</span>
          )}
        </span>
      )}
      <span className="card__meta">
        <span className="card__name" title={result.path}>
          {result.name}
        </span>
        <span className="card__score" title="Cosine similarity between query and image">
          {result.score.toFixed(3)}
        </span>
      </span>
    </button>
  );
}
