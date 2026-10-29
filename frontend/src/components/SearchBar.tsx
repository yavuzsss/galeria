import { useEffect, useRef } from "react";

import type { KindFilter } from "../api";

const EXAMPLES = [
  "kumsalda gün batımı",
  "kedi kutuda",
  "dağlarda kıvrımlı bir yol",
  "a red plant at night",
  "rocks in the ocean",
];

const FILTERS: { value: KindFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "photo", label: "Photos" },
  { value: "video", label: "Videos" },
];

interface Props {
  query: string;
  type: KindFilter;
  onQuery: (q: string, commit?: boolean) => void;
  onType: (type: KindFilter) => void;
}

export function SearchBar({ query, type, onQuery, onType }: Props) {
  const input = useRef<HTMLInputElement>(null);

  // "/" focuses search from anywhere, like most search-first apps.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (e.key === "/" && !["INPUT", "TEXTAREA"].includes(target.tagName)) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="search">
      <form
        className="search__box"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          onQuery(query, true);
        }}
      >
        <svg className="search__icon" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <input
          ref={input}
          type="search"
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          placeholder="Describe what you're looking for — in any language"
          aria-label="Search photos and videos"
          autoFocus
          spellCheck={false}
        />
        {query && (
          <button
            type="button"
            className="search__clear"
            onClick={() => {
              onQuery("", true);
              input.current?.focus();
            }}
            aria-label="Clear search"
          >
            ×
          </button>
        )}
      </form>

      <div className="search__row">
        <div className="segmented" role="radiogroup" aria-label="Media type">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              role="radio"
              aria-checked={type === f.value}
              className={type === f.value ? "active" : ""}
              onClick={() => onType(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
        {!query && (
          <div className="examples">
            <span>Try</span>
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                className="chip"
                onClick={() => onQuery(example, true)}
              >
                {example}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
