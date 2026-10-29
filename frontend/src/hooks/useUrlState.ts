import { useCallback, useEffect, useRef, useState } from "react";

import type { KindFilter } from "../api";

export interface UrlState {
  q: string;
  type: KindFilter;
}

function read(): UrlState {
  const params = new URLSearchParams(window.location.search);
  const type = params.get("type");
  return {
    q: params.get("q") ?? "",
    type: type === "photo" || type === "video" ? type : "all",
  };
}

/**
 * Keeps the query and filter in the address bar, so searches can be shared and the back button
 * steps through them. Typing replaces the history entry instead of adding one per keystroke.
 */
export function useUrlState(): [UrlState, (next: Partial<UrlState>, push?: boolean) => void] {
  const [state, setState] = useState<UrlState>(read);
  const current = useRef(state);
  current.current = state;

  useEffect(() => {
    const onPop = () => setState(read());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const update = useCallback((next: Partial<UrlState>, push = false) => {
    const merged = { ...current.current, ...next };
    const params = new URLSearchParams();
    if (merged.q) params.set("q", merged.q);
    if (merged.type !== "all") params.set("type", merged.type);
    const url = params.size ? `?${params}` : window.location.pathname;
    window.history[push ? "pushState" : "replaceState"](null, "", url);
    current.current = merged;
    setState(merged);
  }, []);

  return [state, update];
}
