// Typed client for the Galeria API. Shapes mirror backend/galeria/api/schemas.py.

export type MediaKind = "photo" | "video";
export type KindFilter = "all" | MediaKind;

export interface Moment {
  timestamp: number;
  score: number;
  thumb_url: string;
}

export interface SearchResult {
  id: number;
  kind: MediaKind;
  name: string;
  path: string;
  score: number;
  thumb_url: string;
  media_url: string;
  timestamp: number | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  moments: Moment[];
}

export interface SearchResponse {
  query: string;
  took_ms: number;
  encode_ms: number;
  search_ms: number;
  total_vectors: number;
  min_score: number | null;
  results: SearchResult[];
}

export interface IndexReport {
  root: string;
  added: number;
  updated: number;
  removed: number;
  unchanged: number;
  vectors_added: number;
  frames_sampled: number;
  frames_kept: number;
  failed: string[];
  seconds: number;
}

export interface JobStatus {
  state: "idle" | "running" | "done" | "failed";
  folder: string | null;
  done: number;
  total: number;
  current: string | null;
  report: IndexReport | null;
  error: string | null;
}

export interface Stats {
  photos: number;
  videos: number;
  vectors: number;
  encoder: string;
  roots: string[];
  /** Folders the server lets you index; empty means any. */
  allowed_roots: string[];
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      // FastAPI sends {detail: string} for HTTPException and {detail: [...]} for validation.
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // not JSON; keep the status text
    }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

export function searchUrl(q: string, type: KindFilter, k = 48): string {
  const params = new URLSearchParams({ q, k: String(k) });
  if (type !== "all") params.set("type", type);
  return `/api/search?${params}`;
}

export const api = {
  search: (q: string, type: KindFilter, signal?: AbortSignal) =>
    request<SearchResponse>(searchUrl(q, type), { signal }),
  stats: () => request<Stats>("/api/stats"),
  indexStatus: () => request<JobStatus>("/api/index/status"),
  startIndex: (folder: string) =>
    request<JobStatus>("/api/index", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder }),
    }),
};

/** Media URL that makes a <video> element start at the matching second. */
export function mediaUrlAt(result: SearchResult, timestamp = result.timestamp): string {
  return timestamp == null ? result.media_url : `${result.media_url}#t=${timestamp}`;
}
