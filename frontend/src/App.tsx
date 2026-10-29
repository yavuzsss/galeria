import { useCallback, useEffect, useState } from "react";

import { api, type SearchResponse, type Stats } from "./api";
import { IndexPanel } from "./components/IndexPanel";
import { MediaViewer } from "./components/MediaViewer";
import { ResultGrid } from "./components/ResultGrid";
import { SearchBar } from "./components/SearchBar";
import { formatMs, plural } from "./format";
import { useSearch } from "./hooks/useSearch";
import { useUrlState } from "./hooks/useUrlState";

export function App() {
  const [{ q, type }, setUrl] = useUrlState();
  const [stats, setStats] = useState<Stats | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [viewer, setViewer] = useState<number | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const search = useSearch(q, type, refreshKey);

  const loadStats = useCallback(() => {
    api
      .stats()
      .then((s) => {
        setStats(s);
        setStatsError(null);
      })
      .catch((err: unknown) => setStatsError(err instanceof Error ? err.message : String(err)));
  }, []);

  useEffect(loadStats, [loadStats]);

  // While a new query loads, keep showing the previous results (dimmed) instead of flashing.
  const response: SearchResponse | null =
    search.status === "done" ? search.response : search.status === "loading" ? search.previous : null;
  const results = response?.results ?? [];
  const empty = stats !== null && stats.vectors === 0;

  return (
    <div className="app">
      <header className="header">
        <a className="brand" href="/" aria-label="Galeria home">
          <span className="brand__mark" aria-hidden="true" />
          Galeria
        </a>
        {stats && (
          <span className="header__stats">
            {plural(stats.photos, "photo")} · {plural(stats.videos, "video")}
          </span>
        )}
        <button type="button" className="secondary" onClick={() => setPanelOpen(true)}>
          Index folder
        </button>
      </header>

      <main className="main">
        <SearchBar
          query={q}
          type={type}
          onQuery={(next, commit) => {
            setViewer(null);
            setUrl({ q: next }, commit);
          }}
          onType={(next) => setUrl({ type: next }, true)}
        />

        {statsError && (
          <p className="alert" role="alert">
            Can't reach the API ({statsError}). Is <code>galeria serve</code> running?
          </p>
        )}

        {empty && (
          <section className="empty">
            <h2>Nothing indexed yet</h2>
            <p>Point Galeria at a folder of photos and videos to start searching.</p>
            <button type="button" className="primary" onClick={() => setPanelOpen(true)}>
              Index a folder
            </button>
          </section>
        )}

        {!empty && response && (
          <p className="status" aria-live="polite">
            {plural(results.length, "result")} in <strong>{formatMs(response.took_ms)}</strong>
            <span className="status__detail">
              {" "}
              (encode {formatMs(response.encode_ms)} · search {formatMs(response.search_ms)} over{" "}
              {plural(response.total_vectors, "vector")}
              {response.min_score != null && ` · cutoff ${response.min_score.toFixed(2)}`})
            </span>
          </p>
        )}

        {search.status === "error" && (
          <p className="alert" role="alert">
            Search failed: {search.message}
          </p>
        )}

        {!empty && search.status === "done" && results.length === 0 && (
          <p className="muted">
            {search.response.min_score != null
              ? `Nothing scores above the ${search.response.min_score.toFixed(2)} cutoff. Try describing it differently.`
              : "No matches."}
          </p>
        )}

        <ResultGrid results={results} dimmed={search.status === "loading"} onOpen={setViewer} />
      </main>

      {viewer !== null && results[viewer] && (
        <MediaViewer
          results={results}
          index={viewer}
          onIndex={setViewer}
          onClose={() => setViewer(null)}
        />
      )}

      {panelOpen && (
        <IndexPanel
          roots={stats?.roots ?? []}
          allowedRoots={stats?.allowed_roots ?? []}
          onClose={() => setPanelOpen(false)}
          onFinished={() => {
            loadStats();
            setRefreshKey((k) => k + 1);
          }}
        />
      )}
    </div>
  );
}
