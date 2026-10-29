import { useEffect, useState } from "react";

import { api, type KindFilter, type SearchResponse } from "../api";

export type SearchState =
  | { status: "idle" }
  | { status: "loading"; previous: SearchResponse | null }
  | { status: "done"; response: SearchResponse }
  | { status: "error"; message: string };

const DEBOUNCE_MS = 250;

/**
 * Search as the user types. Each new query aborts the request in flight, so a slow answer to
 * an old query can never overwrite the answer to a newer one.
 */
export function useSearch(query: string, type: KindFilter, refreshKey = 0): SearchState {
  const [state, setState] = useState<SearchState>({ status: "idle" });

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setState({ status: "idle" });
      return;
    }
    setState((s) => ({
      status: "loading",
      previous: s.status === "done" ? s.response : s.status === "loading" ? s.previous : null,
    }));

    const controller = new AbortController();
    const timer = setTimeout(() => {
      api
        .search(q, type, controller.signal)
        .then((response) => setState({ status: "done", response }))
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setState({ status: "error", message: err instanceof Error ? err.message : String(err) });
        });
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, type, refreshKey]);

  return state;
}
